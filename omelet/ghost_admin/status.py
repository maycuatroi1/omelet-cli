"""Per-post state toggles: noindex meta + publish status."""
import re

from .client import GhostAdmin


NOINDEX_TAG = '<meta name="robots" content="noindex,follow">'


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
