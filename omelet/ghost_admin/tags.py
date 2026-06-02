"""Bulk tag cleanup — delete orphans and internalize low-usage tags."""

from .client import GhostAdmin


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

    for t in orphans:
        r = admin.delete('tags', t['id'])
        if r.status_code in (200, 204):
            summary['deleted'] += 1
        else:
            summary['errors'].append(f'delete {t["name"][:40]}: {r.status_code}')

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
