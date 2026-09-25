import csv
import datetime
import os

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.ticker import MaxNLocator, AutoMinorLocator, FuncFormatter
import pandas as pd

# Match the page font: keep SVG text as real text (not paths) so the browser
# renders it in the same sans-serif as the surrounding HTML.
matplotlib.rcParams['svg.fonttype'] = 'none'
matplotlib.rcParams['font.family'] = 'sans-serif'
matplotlib.rcParams['font.sans-serif'] = ['Helvetica', 'Arial', 'DejaVu Sans', 'sans-serif']

DATA_FOLDER = "/configdata"
PLOT_FOLDER = "/plots"

# Absolute base URL, needed for OpenGraph tags (they can't use relative paths).
BASE_URL = "https://fp-stats.com"

# og:image dimensions, kept in sync with the PNG we render in plot_creator
# (figsize 12x5 inches at 100 dpi). Facebook/messengers use these as a hint.
OG_IMAGE_W, OG_IMAGE_H = 1200, 500

_CSS = """
body{font-family:sans-serif;max-width:900px;margin:auto;padding:1rem 1.5rem;color:#222}
a{color:#f64b00;text-decoration:none}a:hover{text-decoration:underline}
nav{margin-bottom:2rem}nav a{margin-right:1rem}
.stats{margin:1.5rem 0;display:flex;gap:3rem;flex-wrap:wrap}
.stat .value{font-size:2rem;font-weight:bold}
.stat .label{font-size:.8rem;color:#666;margin-top:.2rem}
.up{color:#2a2}.down{color:#c00}
img{max-width:100%;height:auto}
.note{font-size:.85rem;color:#666;margin-top:.5rem}
footer{margin-top:3rem;padding-top:1rem;border-top:1px solid #eee;font-size:.85rem;color:#888}
#stale{display:none;background:#c00;color:#fff;padding:1rem;text-align:center;font-size:1.1rem;margin-bottom:1.5rem}
"""


def creator_filename(name):
    return name.replace(' ', '-')


def load_creators():
    creators = []
    with open(f'{DATA_FOLDER}/creators.csv', newline='') as f:
        for row in csv.reader(f):
            if len(row) < 3:  # skip blank or malformed lines instead of crashing
                continue
            name, skip = row[0].strip(), row[2].strip()
            if skip == 'False':
                creators.append(name)
    return creators


def load_creator_data(name):
    path = f'{DATA_FOLDER}/data_{creator_filename(name)}.csv'
    if not os.path.exists(path):
        return None
    df = pd.read_csv(path, header=None, names=['Creator', 'Time', 'Subscribers', 'Source'], on_bad_lines='skip')
    df['Time'] = pd.to_datetime(df['Time'], format='%Y-%m-%d_%H-%M-%S', errors='coerce')
    df['Subscribers'] = pd.to_numeric(df['Subscribers'], errors='coerce')
    df.dropna(subset=['Time', 'Subscribers'], inplace=True)
    df.sort_values('Time', inplace=True)
    # Keep the true last scrape time before resampling collapses it to midnight,
    # so last_updated (footer + stale banner) is accurate to the actual reading.
    raw_last_time = df['Time'].iloc[-1]
    df = df.set_index('Time').resample('D').last().dropna(subset=['Subscribers']).reset_index()
    df.attrs['last_raw_time'] = raw_last_time
    return df


def compute_stats(df):
    current = int(df['Subscribers'].iloc[-1])
    peak = int(df['Subscribers'].max())
    cutoff = df['Time'].iloc[-1] - pd.Timedelta(days=30)
    past = df[df['Time'] <= cutoff]
    change_30d = (current - int(past['Subscribers'].iloc[-1])) if not past.empty else None
    return {'current': current, 'peak': peak, 'change_30d': change_30d}


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
    # for intentionally frozen pages (TechDeals) where "over 24h" is expected.
    stale = ('<div id="stale">&#9888; Data hasn&#39;t updated in over 24&nbsp;hours.</div>\n'
             f'<script>if(Date.now()-new Date("{ts}")>864e5)'
             "document.getElementById('stale').style.display='block';</script>\n") if show_stale else ''
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title}</title>
{og_tags(title, description, path, image)}
<style>{_CSS}</style>
</head>
<body>
{stale}{body}
<footer>Updated {last_updated.strftime('%Y-%m-%d %H:%M')} UTC &middot; <a href="/">Home</a> &middot; <a href="/creators.html">All creators</a></footer>
</body>
</html>"""


def plot_creator(name, df):
    fig, ax = plt.subplots(figsize=(12, 5))
    ax.plot(df['Time'], df['Subscribers'], linewidth=1.5, color='#f64b00', zorder=3)
    ax.set_title(name, fontsize=16)
    ax.set_ylabel('Floatplane Subscribers')

    # Y axis starts at zero.
    ax.set_ylim(bottom=0)

    # Major ticks label years / 5k; small minor ticks mark every month and 1k.
    ax.xaxis.set_major_locator(mdates.YearLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y'))
    ax.xaxis.set_minor_locator(mdates.MonthLocator())
    # Nice, round y ticks that adapt to each creator's range (LTT still lands on
    # 5k steps; small creators get sensibly-scaled labels instead of only "0").
    ax.yaxis.set_major_locator(MaxNLocator(nbins=8, steps=[1, 2, 2.5, 5, 10]))
    ax.yaxis.set_minor_locator(AutoMinorLocator())
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f'{int(v):,}'))
    ax.tick_params(which='major', length=6)
    ax.tick_params(which='minor', length=3)

    # Instead of gridlines: light dots on a lattice of quarters (x) and 5k (y).
    xmin, xmax = ax.get_xlim()
    ymin, ymax = ax.get_ylim()
    quarters = mdates.MonthLocator(bymonth=[1, 4, 7, 10])
    q_ticks = quarters.tick_values(mdates.num2date(xmin), mdates.num2date(xmax))
    xs = [t for t in q_ticks if xmin <= t <= xmax]
    ys = [t for t in ax.get_yticks() if ymin <= t <= ymax]
    ax.scatter([x for x in xs for _ in ys], [y for _ in xs for y in ys],
               s=6, color='#ccc', edgecolors='none', zorder=0)

    # Drop the box (top/right spines).
    ax.spines[['top', 'right']].set_visible(False)

    fig.autofmt_xdate()
    plt.tight_layout()
    slug = creator_filename(name)
    fig.savefig(f'{PLOT_FOLDER}/plot_{slug}.svg', format='svg')
    # Also a raster copy for og:image link previews (messengers rarely render
    # SVG). 12x5in at 100 dpi -> OG_IMAGE_W x OG_IMAGE_H, white background.
    fig.savefig(f'{PLOT_FOLDER}/plot_{slug}.png', format='png', dpi=100, facecolor='white')
    plt.close(fig)


def write_creator_page(name, df, last_updated, note=None, show_stale=True):
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
    body = f"""<nav><a href="/">Home</a> &middot; <a href="/creators.html">All creators</a></nav>
<h1>{name}</h1>
{note_html}
<div class="stats">
  <div class="stat"><div class="value">{stats['current']:,}</div><div class="label">subscribers</div></div>
  <div class="stat"><div class="value">{stats['peak']:,}</div><div class="label">all-time peak</div></div>
  {change_html}
</div>
<img src="/plot_{slug}.svg" alt="{name} Floatplane subscriber chart">"""
    description = (f'{name} has {stats["current"]:,} Floatplane subscribers '
                   f'(all-time peak {stats["peak"]:,}). Long-term subscriber history and chart.')
    with open(f'{PLOT_FOLDER}/{slug}.html', 'w') as f:
        f.write(page_shell(f'{name} — Floatplane Stats', body, last_updated,
                           description=description, path=f'/{slug}.html',
                           image=f'/plot_{slug}.png', show_stale=show_stale))


def write_creators_index(creators_data, techdeals_df, last_updated):
    rows = []
    for name, df in creators_data:
        slug = creator_filename(name)
        current = int(df['Subscribers'].iloc[-1])
        rows.append(f'<li><a href="/{slug}.html">{name}</a> &mdash; {current:,}</li>')
    if techdeals_df is not None:
        current = int(techdeals_df['Subscribers'].iloc[-1])
        rows.append(f'<li><a href="/TechDeals.html">TechDeals</a> &mdash; {current:,} <span class="note">(left Floatplane April 2026)</span></li>')
    body = f"""<nav><a href="/">Home</a></nav>
<h1>Floatplane Creators</h1>
<ul style="line-height:2.2">
{''.join(rows)}
</ul>"""
    with open(f'{PLOT_FOLDER}/creators.html', 'w') as f:
        f.write(page_shell('Creators — Floatplane Stats', body, last_updated,
                           description='Floatplane subscriber counts for all tracked creators.',
                           path='/creators.html', image='/plot_LinusTechTips.png'))


def write_front_page(ltt_df, last_updated):
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
  <div class="stat"><div class="value">{stats['peak']:,}</div><div class="label">all-time peak</div></div>
  {change_html}
</div>
<img src="/plot_LinusTechTips.svg" alt="LTT Floatplane subscriber chart">
<p class="note">The August 2023 dip reflects the LTT controversy and channel hack.
Data before 2023 is sparse, sourced from Reddit posts and web archives.
Coverage through 2024 was supplemented from a second scraper.</p>
<p><a href="/creators.html">See all tracked creators &rarr;</a></p>"""
    description = (f'Linus Tech Tips has {stats["current"]:,} Floatplane subscribers '
                   f'(all-time peak {stats["peak"]:,}). The only long-term subscriber history, '
                   f'with an annotated timeline of controversies and the channel hack.')
    with open(f'{PLOT_FOLDER}/index.html', 'w') as f:
        f.write(page_shell('Floatplane Subscriber Stats', body, last_updated,
                           description=description, path='/',
                           image='/plot_LinusTechTips.png'))


def create_plot():
    os.makedirs(PLOT_FOLDER, exist_ok=True)
    creators_data = []
    for name in load_creators():
        df = load_creator_data(name)
        if df is None or df.empty:
            print(f"No data for {name}, skipping")
            continue
        creators_data.append((name, df))

    # Each page's last_updated must reflect the newest actual data point *for that
    # creator*, not render time and not a global max. This script re-renders hourly
    # even when scrapes fail, so keying off render time would hide the stale banner
    # during exactly the silent-failure case it exists to catch; a global max would
    # let one healthy creator mask another that has silently stopped.
    def creator_last_updated(df):
        return df.attrs['last_raw_time'].to_pydatetime()

    for name, df in creators_data:
        plot_creator(name, df)
        write_creator_page(name, df, creator_last_updated(df))
        print(f"Plotted {name}")

    techdeals_df = load_creator_data('TechDeals')
    if techdeals_df is not None and not techdeals_df.empty:
        plot_creator('TechDeals', techdeals_df)
        # Intentionally frozen (left Floatplane), so suppress the stale banner —
        # its footer honestly shows the April 2026 last reading.
        write_creator_page('TechDeals', techdeals_df, creator_last_updated(techdeals_df),
                           note='TechDeals left Floatplane in April 2026. Historical data is preserved here but no longer being updated.',
                           show_stale=False)

    # The index isn't creator-specific: its banner signals overall pipeline health,
    # so it uses the newest reading across active creators (TechDeals excluded).
    active_last = [creator_last_updated(df) for _, df in creators_data]
    index_last_updated = max(active_last) if active_last else datetime.datetime.utcnow()
    write_creators_index(creators_data, techdeals_df, index_last_updated)

    ltt_df = next((df for name, df in creators_data if name == 'LinusTechTips'), None)
    if ltt_df is not None:
        write_front_page(ltt_df, creator_last_updated(ltt_df))
    print(f"Site written to {PLOT_FOLDER}/")


if __name__ == "__main__":
    create_plot()
