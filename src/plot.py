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

# Methodology and background live in a post on Lorenz's personal blog.
BLOG_URL = "https://www.lorenz.kiwi/fp-stats/"

# og:image dimensions, kept in sync with the PNG we render in plot_creator
# (figsize 12x5 inches at 100 dpi). Facebook/messengers use these as a hint.
OG_IMAGE_W, OG_IMAGE_H = 1200, 500

# Readings further apart than this are joined by a dashed line instead of a
# solid one: we don't know what happened in between.
MAX_GAP = pd.Timedelta(days=7)

# Charts show one point per 3 days (the last reading in each window). Shorter
# than MAX_GAP, so regular data never looks like a gap. Stats and the stored
# data keep their full resolution.
CHART_FREQ = '3D'

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
<footer>Updated {last_updated.strftime('%Y-%m-%d %H:%M')} UTC &middot; <a href="/">Home</a> &middot; <a href="/creators.html">All creators</a> &middot; <a href="{BLOG_URL}">About &amp; methodology</a></footer>
</body>
</html>"""


def plot_series(ax, df):
    """Draw the subscriber line so gaps in the data are visible.

    Returns a caption explaining the markings, or None if there's nothing to explain.

    Readings at most MAX_GAP apart get a solid line. Longer gaps (early LTT data
    gathered from Reddit/archives, scraper outages) get a thin dashed line, so
    the chart doesn't pretend to know what happened in between. Readings next to
    such a gap get a dot; estimated ("Guestimate") readings get a hollow dot.
    Only one reading per CHART_FREQ window is drawn.
    """
    color = '#f64b00'
    # Gaps are found on the full data, not the thinned points: two thinned
    # points can be up to 2 * CHART_FREQ apart without any real gap between them.
    # Keep each window's last reading, plus the first reading after every gap
    # so the dashed line ends where real data resumes (e.g. the 2023 GN video
    # drop stays solid instead of being folded into a dashed step).
    df = df.reset_index(drop=True)
    df = df.assign(run=(df['Time'].diff() > MAX_GAP).cumsum())
    tails = df.groupby(pd.Grouper(key='Time', freq=CHART_FREQ)).tail(1).index
    resumes = df.index[df['run'].diff() > 0]
    df = df.loc[tails.union(resumes)]
    t, s = df['Time'].reset_index(drop=True), df['Subscribers'].reset_index(drop=True)
    gap = df['run'].reset_index(drop=True).diff() > 0  # True where the step *into* this point spans a gap

    # Solid runs: split the series at every long gap.
    run_id = gap.cumsum()
    for _, idx in t.groupby(run_id).groups.items():
        if len(idx) > 1:
            ax.plot(t[idx], s[idx], linewidth=1.5, color=color, zorder=3)
    # Dashed connectors across each long gap.
    for i in gap[gap].index:
        ax.plot(t[i - 1:i + 1], s[i - 1:i + 1], linewidth=1, color=color,
                linestyle=(0, (3, 3)), alpha=0.6, zorder=2)

    # Dots on readings bordering a long gap (sparse points stand out).
    edge = gap | gap.shift(-1, fill_value=False)
    guess = df['Source'].reset_index(drop=True).astype(str).str.contains('guestimate', case=False)
    real = edge & ~guess
    ax.scatter(t[real], s[real], s=14, color=color, edgecolors='none', zorder=4)
    ax.scatter(t[guess], s[guess], s=14, facecolors='white', edgecolors=color,
               linewidths=1, zorder=4)

    if not gap.any():
        return None
    note = (f'Dashed lines bridge gaps of more than {MAX_GAP.days} days without readings; '
            'dots mark the readings on either side.')
    if guess.any():
        note += ' Hollow dots are estimates.'
    return note


def plot_creator(name, df):
    fig, ax = plt.subplots(figsize=(12, 5))
    gap_note = plot_series(ax, df)
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
    return gap_note


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
    body = f"""<nav><a href="/">Home</a> &middot; <a href="/creators.html">All creators</a></nav>
<h1>{name}</h1>
{note_html}
<div class="stats">
  <div class="stat"><div class="value">{stats['current']:,}</div><div class="label">subscribers</div></div>
  <div class="stat"><div class="value">{stats['peak']:,}</div><div class="label">all-time peak</div></div>
  {change_html}
</div>
<img src="/plot_{slug}.svg" alt="{name} Floatplane subscriber chart">
{f'<p class="note">{gap_note}</p>' if gap_note else ''}"""
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
  <div class="stat"><div class="value">{stats['peak']:,}</div><div class="label">all-time peak</div></div>
  {change_html}
</div>
<img src="/plot_LinusTechTips.svg" alt="LTT Floatplane subscriber chart">
<p class="note">Before mid-August 2023 the data is sparse, sourced from Reddit posts and web archives.
{gap_note or ''}</p>
<p><a href="/creators.html">See all tracked creators &rarr;</a></p>
<p><a href="{BLOG_URL}">How this data is collected &rarr;</a></p>"""
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

    gap_notes = {}
    for name, df in creators_data:
        gap_notes[name] = plot_creator(name, df)
        write_creator_page(name, df, creator_last_updated(df), gap_note=gap_notes[name])
        print(f"Plotted {name}")

    techdeals_df = load_creator_data('TechDeals')
    if techdeals_df is not None and not techdeals_df.empty:
        techdeals_gap_note = plot_creator('TechDeals', techdeals_df)
        # Intentionally frozen (left Floatplane), so suppress the stale banner —
        # its footer honestly shows the April 2026 last reading.
        write_creator_page('TechDeals', techdeals_df, creator_last_updated(techdeals_df),
                           note='TechDeals left Floatplane in April 2026. Historical data is preserved here but no longer being updated.',
                           gap_note=techdeals_gap_note, show_stale=False)

    # The index isn't creator-specific: its banner signals overall pipeline health,
    # so it uses the newest reading across active creators (TechDeals excluded).
    active_last = [creator_last_updated(df) for _, df in creators_data]
    index_last_updated = max(active_last) if active_last else datetime.datetime.utcnow()
    write_creators_index(creators_data, techdeals_df, index_last_updated)

    ltt_df = next((df for name, df in creators_data if name == 'LinusTechTips'), None)
    if ltt_df is not None:
        write_front_page(ltt_df, creator_last_updated(ltt_df), gap_notes['LinusTechTips'])
    print(f"Site written to {PLOT_FOLDER}/")


if __name__ == "__main__":
    create_plot()
