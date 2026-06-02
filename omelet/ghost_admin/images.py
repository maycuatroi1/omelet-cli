"""Migrate inline post images to GCS: download → strip metadata → upload → rewrite src."""
import json
import re
from pathlib import Path
from typing import Optional
from urllib.parse import urljoin

import requests

from .client import GhostAdmin


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
    from ..config import Config
    from ..gcs_uploader import GCSUploader
    from ..gcloud_auth import GCloudAuth
    from ..image_metadata import strip_image_metadata, scrub_watermark

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
