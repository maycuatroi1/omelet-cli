"""
Ghost CMS admin operations — bulk tag cleanup, noindex, AI ending detection.

Powers `omelet ghost` subcommands. See docstrings for usage from Python.
"""
import json
import re
import time
from pathlib import Path
from typing import Optional
from urllib.parse import urljoin

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

    def get_post_or_page(self, slug: str, formats: str = '', include: str = '') -> Optional[tuple]:
        """Find post or page by slug. Returns (object, kind) or None."""
        params = []
        if formats:
            params.append(f'formats={formats}')
        if include:
            params.append(f'include={include}')
        qs = '?' + '&'.join(params) if params else ''
        for kind in ('posts', 'pages'):
            r = requests.get(
                f'{self.api_url}/ghost/api/admin/{kind}/slug/{slug}/{qs}',
                headers=self._headers(),
            )
            if r.ok:
                return r.json()[kind][0], kind
        return None

    def get_by_id(self, obj_id: str, formats: str = '', include: str = '') -> Optional[tuple]:
        """Find post or page by id. Returns (object, kind) or None."""
        params = []
        if formats:
            params.append(f'formats={formats}')
        if include:
            params.append(f'include={include}')
        qs = '?' + '&'.join(params) if params else ''
        for kind in ('posts', 'pages'):
            r = requests.get(
                f'{self.api_url}/ghost/api/admin/{kind}/{obj_id}/{qs}',
                headers=self._headers(),
            )
            if r.ok:
                return r.json()[kind][0], kind
        return None

    def find(self, identifier: str, formats: str = '', include: str = '') -> Optional[tuple]:
        """Resolve identifier (24-hex id OR slug) to (object, kind). Tries id first if it matches."""
        if re.fullmatch(r'[0-9a-f]{24}', identifier):
            found = self.get_by_id(identifier, formats=formats, include=include)
            if found:
                return found
        return self.get_post_or_page(identifier, formats=formats, include=include)

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


# ============================================================================
# SEO metadata bulk-set
# ============================================================================

SEO_FIELDS = (
    'title', 'slug', 'custom_excerpt',
    'meta_title', 'meta_description',
    'og_title', 'og_description', 'og_image',
    'twitter_title', 'twitter_description', 'twitter_image',
    'feature_image', 'feature_image_alt',
)


def _parse_frontmatter(path: Path) -> dict:
    """Parse YAML frontmatter from a markdown file. Returns dict or {} if none."""
    text = path.read_text(encoding='utf-8')
    if not text.startswith('---\n'):
        return {}
    end = text.find('\n---\n', 4)
    if end == -1:
        return {}
    try:
        import yaml
    except ImportError:
        return {}
    return yaml.safe_load(text[4:end]) or {}


def show_seo(admin: GhostAdmin, identifier: str) -> Optional[dict]:
    """Print current SEO fields of post/page. Returns the dict or None."""
    found = admin.find(identifier, include='tags')
    if not found:
        return None
    obj, _ = found
    out = {f: obj.get(f) for f in SEO_FIELDS}
    out['tags'] = [t['name'] for t in obj.get('tags', [])]
    out['_status'] = obj.get('status')
    out['_url'] = obj.get('url')
    return out


def set_seo(
    admin: GhostAdmin,
    identifier: str,
    *,
    fields: dict,
    tags: Optional[list[str]] = None,
    og_mirror: bool = False,
    excerpt_from_meta: bool = False,
) -> tuple[str, str, dict]:
    """Bulk-set SEO fields on a post/page. Returns (status, message, applied_dict).

    `fields` keys must be a subset of SEO_FIELDS. None/empty values are skipped.
    `tags` is a list of tag slugs/names; replaces existing tags.
    `og_mirror`: fill og_*/twitter_* from title + meta_description + feature_image.
    `excerpt_from_meta`: set custom_excerpt = meta_description if not given explicitly.
    """
    found = admin.find(identifier, include='tags')
    if not found:
        return 'NOT_FOUND', f'no post or page with id/slug {identifier!r}', {}
    obj, kind = found

    # Filter fields to known SEO fields, skip None/empty
    clean = {k: v for k, v in fields.items() if k in SEO_FIELDS and v not in (None, '')}

    # excerpt-from-meta
    if excerpt_from_meta and 'custom_excerpt' not in clean and clean.get('meta_description'):
        clean['custom_excerpt'] = clean['meta_description']

    # og-mirror — only fill blanks, don't overwrite explicit values
    if og_mirror:
        title = clean.get('title') or clean.get('meta_title') or obj.get('title')
        desc = clean.get('meta_description') or obj.get('meta_description')
        img = clean.get('feature_image') or obj.get('feature_image')
        for prefix in ('og', 'twitter'):
            if title and not clean.get(f'{prefix}_title'):
                clean[f'{prefix}_title'] = title
            if desc and not clean.get(f'{prefix}_description'):
                clean[f'{prefix}_description'] = desc
            if img and not clean.get(f'{prefix}_image'):
                clean[f'{prefix}_image'] = img

    # Tags (posts only — pages don't have tags on Ghost)
    if tags is not None and kind == 'posts':
        clean['tags'] = [{'name': t.strip()} for t in tags if t.strip()]

    if not clean:
        return 'SKIP', 'no fields to update', {}

    r = admin.update(kind, obj['id'], obj['updated_at'], **clean)
    if r.ok:
        return 'OK', f'{kind}/{obj["slug"]}: updated {len(clean)} field(s)', clean
    return 'FAIL', f'{r.status_code}: {r.text[:300]}', clean


# ============================================================================
# Image migration: download external/relative img src → GCS → replace
# ============================================================================

def _find_html_card(lex: dict) -> Optional[dict]:
    """Return the first lexical node of type 'html' in the post body. Walks tree."""
    def walk(node):
        if node.get('type') == 'html':
            return node
        for c in node.get('children', []) or []:
            r = walk(c)
            if r:
                return r
        return None
    return walk(lex['root'])


def _extract_img_srcs(html: str) -> list[str]:
    """Return list of all <img src> values in HTML, in document order."""
    return re.findall(r'<img[^>]+src="([^"]+)"', html)


def migrate_images(
    admin: GhostAdmin,
    identifier: str,
    *,
    source_base: Optional[str] = None,
    folder: Optional[str] = None,
    mirror_external: bool = False,
    bucket: Optional[str] = None,
    strip_watermark: bool = False,
    dry_run: bool = False,
    download_dir: Optional[Path] = None,
) -> dict:
    """Download all <img src> in a post, strip metadata, upload to GCS, replace src.

    - Relative paths (`images/foo.png`) need `source_base` to resolve.
    - Absolute external URLs are migrated only if `mirror_external=True`.
    - Existing GCS URLs (already under `bucket`) are skipped.

    Returns: {status, post_slug, mapping: {old: new}, skipped: [...], errors: [...]}
    """
    from .config import Config
    from .gcs_uploader import GCSUploader
    from .gcloud_auth import GCloudAuth
    from .image_metadata import strip_image_metadata, scrub_watermark

    config = Config()
    bucket = bucket or config.gcs_bucket
    if not bucket:
        return {'status': 'FAIL', 'error': 'no gcs_bucket configured (~/.omelet.json) or --bucket given'}

    found = admin.find(identifier, formats='lexical')
    if not found:
        return {'status': 'NOT_FOUND', 'error': f'no post/page with id/slug {identifier!r}'}
    obj, kind = found
    folder = folder or obj['slug']

    lex = json.loads(obj['lexical']) if obj.get('lexical') else None
    if not lex:
        return {'status': 'FAIL', 'error': 'post has no lexical body'}
    card = _find_html_card(lex)
    if not card:
        return {'status': 'FAIL', 'error': 'no html card in lexical tree'}
    html = card['html']

    srcs = _extract_img_srcs(html)
    already_ours = f'storage.googleapis.com/{bucket}/'

    to_migrate = []  # list of (src_in_html, download_url, filename)
    skipped = []
    for src in srcs:
        if src.startswith(('http://', 'https://')):
            if already_ours in src:
                skipped.append((src, 'already on our bucket'))
                continue
            if not mirror_external:
                skipped.append((src, 'external URL (use --mirror-external)'))
                continue
            fname = src.rsplit('/', 1)[-1].split('?')[0]
            to_migrate.append((src, src, fname))
        else:
            if not source_base:
                skipped.append((src, 'relative path (need --source-base)'))
                continue
            url = urljoin(source_base.rstrip('/') + '/', src)
            fname = src.rsplit('/', 1)[-1]
            to_migrate.append((src, url, fname))

    if dry_run:
        return {
            'status': 'DRY_RUN',
            'post_slug': obj['slug'],
            'would_migrate': [(s, u) for s, u, _ in to_migrate],
            'skipped': skipped,
        }

    if not to_migrate:
        return {'status': 'NOOP', 'post_slug': obj['slug'], 'mapping': {}, 'skipped': skipped}

    # Download → strip → upload
    tmpdir = download_dir or Path(f'/tmp/omelet-migrate-{obj["id"][:8]}')
    tmpdir.mkdir(parents=True, exist_ok=True)
    auth = GCloudAuth()
    if not auth.is_authenticated():
        return {'status': 'FAIL', 'error': 'gcloud not authenticated'}
    uploader = GCSUploader(bucket, auth)

    mapping = {}
    errors = []
    for src_in_html, url, fname in to_migrate:
        local = tmpdir / fname
        try:
            r = requests.get(url, headers={'User-Agent': 'Mozilla/5.0 omelet-cli'}, timeout=30)
            if not r.ok:
                errors.append((src_in_html, f'download {r.status_code}'))
                continue
            local.write_bytes(r.content)
            strip_image_metadata(local)
            if strip_watermark:
                scrub_watermark(local)
            public_url = uploader.upload_image(local, folder)
            mapping[src_in_html] = public_url
        except Exception as e:
            errors.append((src_in_html, str(e)[:200]))

    # Replace in HTML and PUT
    for old, new in mapping.items():
        html = html.replace(old, new)
    card['html'] = html

    new_lex_str = json.dumps(lex, ensure_ascii=False)
    r = admin.update(kind, obj['id'], obj['updated_at'], lexical=new_lex_str)
    if not r.ok:
        return {
            'status': 'FAIL',
            'error': f'PUT failed: {r.status_code} {r.text[:300]}',
            'post_slug': obj['slug'],
            'mapping': mapping,
            'skipped': skipped,
            'errors': errors,
        }

    return {
        'status': 'OK',
        'post_slug': obj['slug'],
        'mapping': mapping,
        'skipped': skipped,
        'errors': errors,
    }
