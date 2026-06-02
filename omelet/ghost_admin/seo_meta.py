"""Bulk SEO metadata operations for Ghost posts/pages.

Reads/writes the standard Ghost SEO surface: meta_title, meta_description,
og_*, twitter_*, feature_image, etc. Optional `og_mirror` fills empty
og_*/twitter_* fields from the canonical title/description/feature_image.
"""
from pathlib import Path
from typing import Optional

from .client import GhostAdmin


SEO_FIELDS = (
    'title', 'slug', 'custom_excerpt',
    'meta_title', 'meta_description',
    'og_title', 'og_description', 'og_image',
    'twitter_title', 'twitter_description', 'twitter_image',
    'feature_image', 'feature_image_alt',
)


def parse_frontmatter(path: Path) -> dict:
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

    clean = {k: v for k, v in fields.items() if k in SEO_FIELDS and v not in (None, '')}

    if excerpt_from_meta and 'custom_excerpt' not in clean and clean.get('meta_description'):
        clean['custom_excerpt'] = clean['meta_description']

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
