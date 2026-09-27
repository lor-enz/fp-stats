import datetime
import os
import traceback

from data import load_creators, load_creator_data, compute_stats, creator_filename
from charts import plot_creator, OG_IMAGE_W, OG_IMAGE_H
from atomic import atomic_write
from favicon import write_favicons

PLOT_FOLDER = "/plots"

# Absolute base URL, needed for OpenGraph tags (they can't use relative paths).
BASE_URL = "https://fp-stats.com"

# Methodology and background live in a post on Lorenz's personal blog.
BLOG_URL = "https://www.lorenz.kiwi/fp-stats/"

# System fonts: nothing to download (fast under load, no third-party font host).
_CSS = """
body{font-family:system-ui,-apple-system,"Segoe UI",Roboto,"Helvetica Neue",Arial,sans-serif;max-width:900px;margin:auto;padding:0 1.5rem 1rem;color:#222;line-height:1.5}
a{color:#f64b00;text-decoration:none}a:hover{text-decoration:underline}
header{display:flex;align-items:center;padding:.9rem 0;margin-bottom:1.5rem;border-bottom:1px solid #eee}
header .brand{display:flex;align-items:center;gap:.5rem;font-weight:700;font-size:1.25rem;color:#222}
header .brand:hover{text-decoration:none}
h1{line-height:1.2}
.stats{margin:1.5rem 0;display:flex;gap:3rem;flex-wrap:wrap}
.stat .value{font-size:2rem;font-weight:bold;font-variant-numeric:tabular-nums}
.stat .label{font-size:.8rem;color:#666;margin-top:.2rem}
.up{color:#2a2}.down{color:#c00}
img{max-width:100%;height:auto}
.note{font-size:.85rem;color:#666;margin-top:.5rem}
footer{margin-top:3rem;padding-top:1rem;border-top:1px solid #eee;font-size:.85rem;color:#888}
#stale{display:none;background:#c00;color:#fff;padding:1rem;text-align:center;font-size:1.1rem;margin-bottom:1.5rem}
"""


def _esc(text):
    """Minimal escaping for text placed inside HTML attribute values."""
    return (text.replace('&', '&amp;').replace('<', '&lt;')
                .replace('>', '&gt;').replace('"', '&quot;'))


def og_tags(title, description, path, image):
    """OpenGraph + Twitter card tags for link previews in messengers etc.

    path is the page's absolute path (e.g. "/" or "/LinusTechTips.html");
    image is an absolute path to a PNG, or None for a text-only preview.
    """
    url = BASE_URL + path
    tags = [
        ('meta', {'name': 'description', 'content': description}),
        ('meta', {'property': 'og:type', 'content': 'website'}),
        ('meta', {'property': 'og:site_name', 'content': 'fp-stats'}),
        ('meta', {'property': 'og:title', 'content': title}),
        ('meta', {'property': 'og:description', 'content': description}),
        ('meta', {'property': 'og:url', 'content': url}),
    ]
    if image:
        img_url = BASE_URL + image
        tags += [
            ('meta', {'property': 'og:image', 'content': img_url}),
            ('meta', {'property': 'og:image:width', 'content': str(OG_IMAGE_W)}),
            ('meta', {'property': 'og:image:height', 'content': str(OG_IMAGE_H)}),
            ('meta', {'name': 'twitter:card', 'content': 'summary_large_image'}),
            ('meta', {'name': 'twitter:image', 'content': img_url}),
        ]
    else:
        tags.append(('meta', {'name': 'twitter:card', 'content': 'summary'}))
    tags += [
        ('meta', {'name': 'twitter:title', 'content': title}),
        ('meta', {'name': 'twitter:description', 'content': description}),
        ('link', {'rel': 'canonical', 'href': url}),
    ]
    lines = []
    for tag, attrs in tags:
        attr_str = ' '.join(f'{k}="{_esc(v)}"' for k, v in attrs.items())
        lines.append(f'<{tag} {attr_str}>')
    return '\n'.join(lines)


def page_shell(title, body, last_updated, description, path, image=None, show_stale=True):
    ts = last_updated.strftime('%Y-%m-%dT%H:%M:%SZ')
    # The stale banner is per-page, keyed off this page's own last_updated, so a
    # single stalled creator can't be masked by others still updating. Suppressed
    # for creators who left Floatplane: their pages are frozen on purpose.
    stale = ('<div id="stale">&#9888; Data hasn&#39;t updated in over 24&nbsp;hours.</div>\n'
             f'<script>if(Date.now()-new Date("{ts}")>864e5)'
             "document.getElementById('stale').style.display='block';</script>\n") if show_stale else ''
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title}</title>
<link rel="icon" href="/favicon.ico" sizes="32x32">
<link rel="icon" href="/favicon.svg" type="image/svg+xml">
{og_tags(title, description, path, image)}
<style>{_CSS}</style>
</head>
<body>
<header><a class="brand" href="/"><img src="/favicon.svg" alt="" width="28" height="28">fp-stats</a></header>
{stale}{body}
<footer>Updated {last_updated.strftime('%Y-%m-%d %H:%M')} UTC &middot; <a href="/">Home</a> &middot; <a href="/creators.html">All creators</a> &middot; <a href="{BLOG_URL}">About &amp; methodology</a></footer>
</body>
</html>"""


def write_creator_page(name, df, last_updated, note=None, gap_note=None, show_stale=True):
    slug = creator_filename(name)
    stats = compute_stats(df)
    change = stats['change_30d']
    if change is not None:
        sign = '+' if change >= 0 else ''
        cls = 'up' if change >= 0 else 'down'
        change_html = f'<div class="stat"><div class="value {cls}">{sign}{change:,}</div><div class="label">30-day change</div></div>'
    else:
        change_html = ''
    note_html = f'<p class="note">{note}</p>' if note else ''
    body = f"""<h1>{name}</h1>
{note_html}
<div class="stats">
  <div class="stat"><div class="value">{stats['current']:,}</div><div class="label">subscribers</div></div>
  {change_html}
</div>
<img src="/plot_{slug}.svg" alt="{name} Floatplane subscriber chart">
{f'<p class="note">{gap_note}</p>' if gap_note else ''}"""
    description = (f'{name} has {stats["current"]:,} Floatplane subscribers. '
                   'Long-term subscriber history and chart.')
    with atomic_write(f'{PLOT_FOLDER}/{slug}.html') as tmp, open(tmp, 'w') as f:
        f.write(page_shell(f'{name} — Floatplane Stats', body, last_updated,
                           description=description, path=f'/{slug}.html',
                           image=f'/plot_{slug}.png', show_stale=show_stale))


def write_creators_index(creators_data, last_updated):
    rows = []
    # Active creators first, then those who left, each in creators.csv order.
    for name, df, left in sorted(creators_data, key=lambda c: c[2]):
        slug = creator_filename(name)
        current = int(df['Subscribers'].iloc[-1])
        left_html = ' <span class="note">(left Floatplane)</span>' if left else ''
        rows.append(f'<li><a href="/{slug}.html">{name}</a> &mdash; {current:,}{left_html}</li>')
    body = f"""<h1>Floatplane Creators</h1>
<ul style="line-height:2.2">
{''.join(rows)}
</ul>"""
    with atomic_write(f'{PLOT_FOLDER}/creators.html') as tmp, open(tmp, 'w') as f:
        f.write(page_shell('Creators — Floatplane Stats', body, last_updated,
                           description='Floatplane subscriber counts for all tracked creators.',
                           path='/creators.html', image='/plot_LinusTechTips.png'))


def write_front_page(ltt_df, last_updated, gap_note=None):
    stats = compute_stats(ltt_df)
    change = stats['change_30d']
    if change is not None:
        sign = '+' if change >= 0 else ''
        cls = 'up' if change >= 0 else 'down'
        change_html = f'<div class="stat"><div class="value {cls}">{sign}{change:,}</div><div class="label">30-day change</div></div>'
    else:
        change_html = ''
    body = f"""<h1>Floatplane Subscriber Stats</h1>
<p>Long-term subscriber history for <a href="https://www.floatplane.com/channel/linustechtips/home">Linus Tech Tips</a>
on Floatplane &mdash; the only place with data going back this far.</p>
<div class="stats">
  <div class="stat"><div class="value">{stats['current']:,}</div><div class="label">subscribers</div></div>
  {change_html}
</div>
<img src="/plot_LinusTechTips.svg" alt="LTT Floatplane subscriber chart">
<p class="note">Before mid-August 2023 the data is sparse, sourced from Reddit posts and web archives.
{gap_note or ''}</p>
<p><a href="/creators.html">See all tracked creators &rarr;</a></p>
<p><a href="{BLOG_URL}">How this data is collected &rarr;</a></p>"""
    description = (f'Linus Tech Tips has {stats["current"]:,} Floatplane subscribers. '
                   'The only long-term subscriber history.')
    with atomic_write(f'{PLOT_FOLDER}/index.html') as tmp, open(tmp, 'w') as f:
        f.write(page_shell('Floatplane Subscriber Stats', body, last_updated,
                           description=description, path='/',
                           image='/plot_LinusTechTips.png'))


def attempt(what, fn, *args, **kwargs):
    """Run one build step; on failure log it and return (False, None) instead of raising.

    Each page is its own step, so one broken data file can't stop the rest of
    the site from updating. A page whose step fails keeps its previous version,
    which then ages past 24h and shows the stale banner.
    """
    try:
        return True, fn(*args, **kwargs)
    except Exception:
        print(f"FAILED: {what} (keeping the previous version)")
        traceback.print_exc()
        return False, None


def build_site():
    os.makedirs(PLOT_FOLDER, exist_ok=True)
    attempt("write favicons", write_favicons, PLOT_FOLDER)
    creators_data = []
    for name, left in load_creators():
        ok, df = attempt(f"load {name}", load_creator_data, name)
        if not ok:
            continue
        if df is None:
            if not left:  # left before we tracked them: nothing to show, nothing to report
                print(f"No data for {name}, skipping")
            continue
        creators_data.append((name, df, left))

    # Each page's last_updated must reflect the newest actual data point *for that
    # creator*, not render time and not a global max. This script re-renders hourly
    # even when scrapes fail, so keying off render time would hide the stale banner
    # during exactly the silent-failure case it exists to catch; a global max would
    # let one healthy creator mask another that has silently stopped.
    def creator_last_updated(df):
        return df.attrs['last_raw_time'].to_pydatetime()

    def render_creator(name, df, **page_args):
        gap_note = plot_creator(name, df, PLOT_FOLDER)
        write_creator_page(name, df, creator_last_updated(df), gap_note=gap_note, **page_args)
        return gap_note

    gap_notes = {}  # only creators whose chart and page were rendered
    for name, df, left in creators_data:
        # Creators who left are frozen on purpose, so no stale banner; the
        # footer still shows the date of their last reading.
        page_args = dict(note=f'{name} has left Floatplane. Historical data is preserved here '
                              'but no longer being updated.',
                         show_stale=False) if left else {}
        ok, gap_notes[name] = attempt(f"render {name}", render_creator, name, df, **page_args)
        if ok:
            print(f"Plotted {name}")
        else:
            del gap_notes[name]

    # The index isn't creator-specific: its banner signals overall pipeline health,
    # so it uses the newest reading across active creators (those who left excluded).
    active_last = [creator_last_updated(df) for _, df, left in creators_data if not left]
    index_last_updated = max(active_last) if active_last else datetime.datetime.utcnow()
    attempt("write creators index", write_creators_index, creators_data, index_last_updated)

    # Only update the front page if LTT's chart was rendered too, so it never
    # pairs fresh numbers with an old chart; otherwise it goes stale and alerts.
    ltt_df = next((df for name, df, _ in creators_data if name == 'LinusTechTips'), None)
    if ltt_df is not None and 'LinusTechTips' in gap_notes:
        attempt("write front page", write_front_page, ltt_df, creator_last_updated(ltt_df),
                gap_notes['LinusTechTips'])
    print(f"Site written to {PLOT_FOLDER}/")


if __name__ == "__main__":
    build_site()
