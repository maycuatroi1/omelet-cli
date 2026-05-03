"""
SEO audit utilities for omelet.tech (Ghost CMS).

Pulls site inventory, sitemap counts, tag pollution metrics, and AI ending
candidates. Produces a markdown report you can hand to a fix workflow.
"""
import csv
import io
import re
from datetime import datetime
from typing import Optional

import requests

from .ghost_admin import GhostAdmin, find_ai_endings


def fetch_sitemap_counts(base_url: str = 'https://www.omelet.tech') -> dict:
    """Fetch each sub-sitemap and count <loc> entries."""
    counts = {}
    for name in ('sitemap-posts.xml', 'sitemap-pages.xml', 'sitemap-tags.xml', 'sitemap-authors.xml'):
        try:
            r = requests.get(f'{base_url.rstrip("/")}/{name}', timeout=15)
            if r.ok:
                counts[name] = len(re.findall(r'<loc>([^<]+)</loc>', r.text))
            else:
                counts[name] = None
        except requests.RequestException:
            counts[name] = None
    return counts


def parse_ga4_queries_csv(csv_path: str) -> dict:
    """Parse GA4 'Queries' export CSV. Returns aggregate stats."""
    text = open(csv_path, 'r', encoding='utf-8').read()
    # GA4 exports start with comment lines (#); find header
    lines = text.split('\n')
    header_idx = None
    for i, line in enumerate(lines):
        if line.startswith('Organic Google Search query,'):
            header_idx = i
            break
    if header_idx is None:
        return {'error': 'header not found'}

    reader = csv.reader(io.StringIO('\n'.join(lines[header_idx:])))
    next(reader)  # skip header

    queries = []
    for row in reader:
        if len(row) < 5:
            continue
        try:
            queries.append({
                'query': row[0],
                'clicks': int(row[1]),
                'impressions': int(row[2]),
                'ctr': float(row[3]),
                'position': float(row[4]),
            })
        except ValueError:
            pass

    if not queries:
        return {'error': 'no queries parsed'}

    total_clicks = sum(q['clicks'] for q in queries)
    total_imp = sum(q['impressions'] for q in queries)

    # Find zero-click queries with high impressions (AI Overview signal)
    zero_click_high_imp = [
        q for q in queries
        if q['clicks'] == 0 and q['impressions'] >= 100
    ]

    return {
        'total_queries': len(queries),
        'total_clicks': total_clicks,
        'total_impressions': total_imp,
        'overall_ctr': total_clicks / total_imp if total_imp else 0,
        'top_clicks': sorted(queries, key=lambda x: -x['clicks'])[:10],
        'zero_click_high_imp': sorted(zero_click_high_imp, key=lambda x: -x['impressions'])[:15],
    }


def tag_pollution_stats(admin: GhostAdmin) -> dict:
    """Count public/internal tags and breakdown by post count."""
    tags = admin.list_all('tags', params='include=count.posts')
    public = [t for t in tags if t.get('visibility', 'public') == 'public']
    internal = [t for t in tags if t.get('visibility') == 'internal']
    orphans = [t for t in public if t['count']['posts'] == 0]
    one_post = [t for t in public if t['count']['posts'] == 1]
    two_post = [t for t in public if t['count']['posts'] == 2]
    valuable = [t for t in public if t['count']['posts'] >= 5]
    return {
        'total': len(tags),
        'public': len(public),
        'internal': len(internal),
        'orphans': len(orphans),
        'one_post': len(one_post),
        'two_post': len(two_post),
        'valuable': len(valuable),
        'valuable_names': sorted(t['name'] for t in valuable),
    }


def build_audit_report(
    admin: GhostAdmin,
    base_url: str = 'https://www.omelet.tech',
    ga4_csv: Optional[str] = None,
) -> str:
    """Build a markdown SEO audit report."""
    out = ['# SEO Audit Report\n']
    out.append(f'Generated: {datetime.now().isoformat(timespec="seconds")}\n')

    # Site inventory
    posts = admin.list_all('posts', params='filter=status:published&fields=id,slug,status', limit=200)
    drafts = admin.list_all('posts', params='filter=status:draft&fields=id', limit=200)
    out.append('## Site Inventory')
    out.append(f'- Published posts: {len(posts)}')
    out.append(f'- Draft posts: {len(drafts)}')

    # Sitemap
    sm_counts = fetch_sitemap_counts(base_url)
    out.append('\n## Sitemap')
    for name, n in sm_counts.items():
        out.append(f'- {name}: {n if n is not None else "unreachable"} URLs')

    # Tag health
    stats = tag_pollution_stats(admin)
    thin_pct = 100 * stats['one_post'] // stats['public'] if stats['public'] else 0
    out.append('\n## Tag Health')
    out.append(f'- Total tags: {stats["total"]} ({stats["public"]} public, {stats["internal"]} internal)')
    out.append(f'- Orphan tags (0 posts, public): {stats["orphans"]}')
    out.append(f'- Thin tags (1 post, public): {stats["one_post"]} ({thin_pct}% of public)')
    out.append(f'- Valuable tags (≥5 posts): {stats["valuable"]}')
    if stats['valuable']:
        out.append(f'  Names: {", ".join(stats["valuable_names"])}')
    if stats['orphans'] > 5 or thin_pct > 30:
        out.append('\n  🔴 Recommendation: `omelet ghost cleanup-tags --strategy aggressive`')

    # AI ending scan
    candidates = find_ai_endings(admin)
    out.append(f'\n## AI Ending Candidates: {len(candidates)} posts')
    if candidates:
        for c in candidates[:20]:
            preview = c['last_para'][:120].replace('\n', ' ')
            out.append(f'- **{c["slug"]}** ({c["ending_kind"]})')
            out.append(f'  > {preview}{"..." if len(c["last_para"]) > 120 else ""}')
        if len(candidates) > 20:
            out.append(f'\n  ... and {len(candidates) - 20} more.')
        out.append('\n  Fix: `omelet ghost scan-ai-endings --fix`')

    # GA4 analysis (optional)
    if ga4_csv:
        ga = parse_ga4_queries_csv(ga4_csv)
        if 'error' in ga:
            out.append(f'\n## GA4: error parsing CSV ({ga["error"]})')
        else:
            ctr_pct = ga['overall_ctr'] * 100
            out.append(f'\n## GA4 Search Console')
            out.append(f'- Total queries: {ga["total_queries"]}')
            out.append(f'- Total clicks: {ga["total_clicks"]}')
            out.append(f'- Total impressions: {ga["total_impressions"]}')
            out.append(f'- Overall CTR: {ctr_pct:.2f}%')
            out.append(f'\n### Top 10 queries by clicks')
            for q in ga['top_clicks']:
                out.append(f'- {q["clicks"]:>4} clicks, pos {q["position"]:.1f} — `{q["query"]}`')
            if ga['zero_click_high_imp']:
                out.append(f'\n### Zero-click queries (AI Overview signal)')
                out.append(f'_High impressions but 0 clicks → Google likely answered on SERP._\n')
                for q in ga['zero_click_high_imp'][:10]:
                    out.append(f'- {q["impressions"]:>5} imp, pos {q["position"]:.1f} — `{q["query"]}`')

    return '\n'.join(out) + '\n'
