"""Detect & remove AI-template closings (VN) from Ghost posts.

Heuristic patterns match common phrasings produced by LLM-assisted drafts
("Tóm lại", "Hy vọng…", "Chúc bạn vui vẻ", etc.). KEEP_SIGNALS suppress
false positives like citations and the editorial "Bình." signature.
"""
import re

from .client import GhostAdmin


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
