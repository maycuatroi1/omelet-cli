"""Ghost CMS admin operations — bulk tag cleanup, noindex, SEO, image migration.

Powers `omelet ghost` subcommands. Submodules:
- client: `GhostAdmin` HTTP wrapper (JWT auth + GET/PUT/DELETE primitives)
- status: noindex meta + publish status toggles
- ai_endings: detect & remove VN AI-template closings
- tags: bulk tag cleanup (orphan delete + internalize thin tags)
- seo_meta: read/write SEO fields (meta_*, og_*, twitter_*, ...)
- images: migrate inline post images to GCS

Public API is re-exported here so callers can `from omelet.ghost_admin import X`.
"""
from .ai_endings import (
    VN_AI_ENDING_PATTERNS,
    VN_AI_HEADING_PATTERN,
    VN_KEEP_SIGNALS,
    find_ai_endings,
    remove_ai_ending,
)
from .client import GhostAdmin
from .images import migrate_images
from .seo_meta import SEO_FIELDS, parse_frontmatter, set_seo, show_seo
from .status import NOINDEX_TAG, add_noindex, set_status
from .tags import cleanup_tags

__all__ = [
    'GhostAdmin',
    'NOINDEX_TAG',
    'SEO_FIELDS',
    'VN_AI_ENDING_PATTERNS',
    'VN_AI_HEADING_PATTERN',
    'VN_KEEP_SIGNALS',
    'add_noindex',
    'cleanup_tags',
    'find_ai_endings',
    'migrate_images',
    'parse_frontmatter',
    'remove_ai_ending',
    'set_seo',
    'set_status',
    'show_seo',
]
