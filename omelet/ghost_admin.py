"""
Ghost CMS admin operations — bulk tag cleanup, noindex, AI ending detection.

Powers `omelet ghost` subcommands. See docstrings for usage from Python.
"""
import re
import time
from typing import Optional

import jwt
import requests


NOINDEX_TAG = '<meta name="robots" content="noindex,follow">'

VN_AI_ENDING_PATTERNS = [
    re.compile(r'^Tóm lại[,\s]', re.I),
    re.compile(r'^Hy vọng (bài viết|qua bài|qua đây|qua đó)', re.I),
    re.compile(r'Chúc (các bạn|bạn|các em|các anh em).*vui vẻ', re.I),
    re.compile(r'Chúc.*(outsourcing|truy vấn|query|build|deploy).*vui vẻ', re.I),
    re.compile(r'^Vậy là (đã )?xong với.*Chúc', re.I | re.DOTALL),
]

VN_AI_HEADING_PATTERN = re.compile(
    r'<h[1-6][^>]*>\s*(?:Tổng kết|Kết luận|Tóm tắt)\s*</h[1-6]>.*$',
    re.IGNORECASE | re.DOTALL,
)

VN_KEEP_SIGNALS = [
    re.compile(r'^Bình\.?$'),
    re.compile(r'(References?|Tài liệu tham khảo|Bài viết gốc|Nguồn):', re.I),
    re.compile(r'(giáo dục|nâng cao nhận thức|vi phạm pháp luật)', re.I),
    re.compile(r'^P\.?S\.?\s', re.I),
    re.compile(r'^Bài tiếp theo|Tiếp theo trong series|Follow series', re.I),
    re.compile(r'^The Hacker News|^Anthropic Engineering', re.I),
]


class GhostAdmin:
    """Thin wrapper around Ghost Admin API for bulk operations.

    Reuses credentials from Config (api_url + admin_api_key). Generates
    a fresh JWT per request — Ghost tokens expire in 5 minutes.
    """

    def __init__(self, api_url: str, admin_api_key: str):
        self.api_url = api_url.rstrip('/')
        key_id, secret = admin_api_key.split(':')
        self.key_id = key_id
        self.secret = secret

    def _token(self) -> str:
        iat = int(time.time())
        return jwt.encode(
            {'iat': iat, 'exp': iat + 300, 'aud': '/admin/'},
            bytes.fromhex(self.secret),
            algorithm='HS256',
            headers={'alg': 'HS256', 'typ': 'JWT', 'kid': self.key_id},
        )

    def _headers(self, json_body: bool = False) -> dict:
        h = {'Authorization': f'Ghost {self._token()}'}
        if json_body:
            h['Content-Type'] = 'application/json'
        return h

    def get_post_or_page(self, slug: str, formats: str = '') -> Optional[tuple]:
        """Find post or page by slug. Returns (object, kind) or None."""
        params = f'?formats={formats}' if formats else ''
        for kind in ('posts', 'pages'):
            r = requests.get(
                f'{self.api_url}/ghost/api/admin/{kind}/slug/{slug}/{params}',
                headers=self._headers(),
            )
            if r.ok:
                return r.json()[kind][0], kind
        return None

    def update(self, kind: str, obj_id: str, updated_at: str, **fields) -> requests.Response:
        body = {kind: [{'id': obj_id, 'updated_at': updated_at, **fields}]}
        url = f'{self.api_url}/ghost/api/admin/{kind}/{obj_id}/'
        if 'html' in fields:
            url += '?source=html'
        return requests.put(url, headers=self._headers(json_body=True), json=body)

    def list_all(self, endpoint: str, params: str = '', limit: int = 100) -> list:
        """Paginate through all items at endpoint (e.g. 'posts', 'tags')."""
        all_items = []
        page = 1
        while True:
            sep = '&' if params else ''
            r = requests.get(
                f'{self.api_url}/ghost/api/admin/{endpoint}/?{params}{sep}limit={limit}&page={page}',
                headers=self._headers(),
            )
            if not r.ok:
                break
            data = r.json()
            all_items.extend(data[endpoint])
            if not data['meta']['pagination']['next']:
                break
            page += 1
        return all_items

    def delete(self, endpoint: str, obj_id: str) -> requests.Response:
        return requests.delete(
            f'{self.api_url}/ghost/api/admin/{endpoint}/{obj_id}/',
            headers=self._headers(),
        )


def add_noindex(admin: GhostAdmin, slug: str, undo: bool = False) -> tuple[str, str]:
    """Add or remove noindex meta on a post/page. Returns (status, message)."""
    found = admin.get_post_or_page(slug)
    if not found:
        return 'NOT_FOUND', f'no post or page with slug {slug!r}'
    obj, kind = found
    head = obj.get('codeinjection_head') or ''
    if undo:
        if 'noindex' not in head:
            return 'SKIP', f'no noindex tag to remove'
        new_head = re.sub(re.escape(NOINDEX_TAG) + r'\n?', '', head).strip()
    else:
        if 'noindex' in head:
            return 'SKIP', f'already has noindex'
        new_head = (head.strip() + '\n' + NOINDEX_TAG).strip()
    r = admin.update(kind, obj['id'], obj['updated_at'], codeinjection_head=new_head)
    if r.ok:
        return 'OK', f'{kind}/{slug} → noindex {"removed" if undo else "added"}'
    return 'FAIL', f'{r.status_code}: {r.text[:200]}'


def set_status(admin: GhostAdmin, slug: str, status: str) -> tuple[str, str]:
    """Set status (draft/published) on a post/page."""
    found = admin.get_post_or_page(slug)
    if not found:
        return 'NOT_FOUND', f'no post or page with slug {slug!r}'
    obj, kind = found
    if obj['status'] == status:
        return 'SKIP', f'already {status}'
    r = admin.update(kind, obj['id'], obj['updated_at'], status=status)
    if r.ok:
        return 'OK', f'{kind}/{slug} → {status} (was: {obj["status"]})'
    return 'FAIL', f'{r.status_code}: {r.text[:200]}'


def find_ai_endings(admin: GhostAdmin, include_drafts: bool = False) -> list[dict]:
    """Scan published posts for VN AI-template closings.

    Returns list of dicts with keys: slug, title, last_para, id, html, ending_kind.

    A post is flagged when EITHER:
    - Last 500 chars match an AI paragraph template (Tóm lại / Hy vọng / Chúc vui vẻ), OR
    - HTML ends with a "Tổng kết|Kết luận|Tóm tắt" heading whose section is short
      (<300 chars after stripping tags) AND its last paragraph also matches an AI pattern.

    Posts whose last paragraph matches a KEEP_SIGNAL (citation, Bình signature,
    series cliffhanger, legal disclaimer) are filtered out as false positives.
    """
    filter_param = '' if include_drafts else 'filter=status:published&'
    posts = admin.list_all('posts', params=f'{filter_param}formats=html,plaintext', limit=50)

    candidates = []
    for p in posts:
        pt = (p.get('plaintext') or '').strip()
        if not pt:
            continue
        html = p.get('html') or ''

        last_500 = pt[-500:]
        para_match = any(pat.search(last_500) for pat in VN_AI_ENDING_PATTERNS)

        heading_match = False
        if not para_match:
            m = VN_AI_HEADING_PATTERN.search(html)
            if m:
                # Strip tags and check section length + last paragraph
                section_text = re.sub(r'<[^>]+>', '', m.group()).strip()
                if len(section_text) < 300:
                    last_para_html = pt.split('\n')[-1].strip()
                    if any(pat.search(last_para_html) for pat in VN_AI_ENDING_PATTERNS):
                        heading_match = True

        if not (para_match or heading_match):
            continue

        paras = [par.strip() for par in pt.split('\n') if par.strip()]
        last_para = paras[-1] if paras else ''
        if any(pat.search(last_para) for pat in VN_KEEP_SIGNALS):
            continue

        candidates.append({
            'id': p['id'],
            'slug': p['slug'],
            'title': p['title'],
            'updated_at': p['updated_at'],
            'last_para': last_para,
            'html': html,
            'ending_kind': 'paragraph' if para_match else 'heading',
        })
    return candidates


def remove_ai_ending(admin: GhostAdmin, post: dict) -> tuple[str, str]:
    """Remove AI-template ending from post. post is item from find_ai_endings()."""
    html = post['html']
    if post['ending_kind'] == 'heading':
        m = VN_AI_HEADING_PATTERN.search(html)
        if not m:
            return 'SKIP', 'heading pattern no longer matches'
        new_html = html[:m.start()].rstrip()
    else:
        paras = list(re.finditer(r'<p[^>]*>.*?</p>', html, re.DOTALL))
        if not paras:
            return 'SKIP', 'no <p> blocks found'
        last = paras[-1]
        last_text = re.sub(r'<[^>]+>', '', last.group()).strip()
        if not any(pat.search(last_text) for pat in VN_AI_ENDING_PATTERNS):
            return 'SKIP', 'last paragraph no longer matches'
        new_html = (html[:last.start()] + html[last.end():]).rstrip()

    r = admin.update('posts', post['id'], post['updated_at'], html=new_html)
    if r.ok:
        return 'OK', post['slug']
    return 'FAIL', f'{r.status_code}: {r.text[:200]}'


def cleanup_tags(
    admin: GhostAdmin,
    strategy: str = 'safe',
    threshold: int = 2,
    dry_run: bool = False,
) -> dict:
    """Delete orphan tags + (aggressive) set thin tags to internal.

    Returns summary dict: {orphans, thin, deleted, internalized, errors}.
    """
    tags = admin.list_all('tags', params='include=count.posts')
    orphans = [t for t in tags if t['count']['posts'] == 0]
    thin = [
        t for t in tags
        if 0 < t['count']['posts'] < threshold and t.get('visibility', 'public') == 'public'
    ]

    summary = {
        'total_tags': len(tags),
        'orphans': len(orphans),
        'thin': len(thin),
        'deleted': 0,
        'internalized': 0,
        'errors': [],
    }
    if dry_run:
        return summary

    # Delete orphans
    for t in orphans:
        r = admin.delete('tags', t['id'])
        if r.status_code in (200, 204):
            summary['deleted'] += 1
        else:
            summary['errors'].append(f'delete {t["name"][:40]}: {r.status_code}')

    # Set thin → internal (aggressive only)
    if strategy == 'aggressive':
        for t in thin:
            new_name = t['name'] if t['name'].startswith('#') else f'#{t["name"]}'
            r = admin.update(
                'tags', t['id'], t['updated_at'],
                name=new_name, visibility='internal',
            )
            if r.ok:
                summary['internalized'] += 1
            else:
                summary['errors'].append(f'internal {t["name"][:40]}: {r.status_code}')

    return summary
