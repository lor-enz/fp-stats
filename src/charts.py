import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.ticker import MaxNLocator
import pandas as pd

from atomic import atomic_write
from data import creator_filename

# Match the page font: keep SVG text as real text (not paths) so the browser
# renders it in the same sans-serif as the surrounding HTML.
matplotlib.rcParams['svg.fonttype'] = 'none'
matplotlib.rcParams['font.family'] = 'sans-serif'
matplotlib.rcParams['font.sans-serif'] = ['Helvetica', 'Arial', 'DejaVu Sans', 'sans-serif']
matplotlib.rcParams['font.size'] = 13

ORANGE = '#f64b00'
DOT_GREY = '#c8c8c8'       # background dot grid
BASELINE_GREY = '#999'     # the zero line, year ticks
TICK_GREY = '#bbb'         # quarter ticks
LABEL_GREY = '#666'        # axis numbers, subtitle

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


def plot_series(ax, df):
    """Draw the subscriber line so gaps in the data are visible.

    Returns a caption explaining the markings, or None if there's nothing to explain.

    Readings at most MAX_GAP apart get a solid line. Longer gaps (early LTT data
    gathered from Reddit/archives, scraper outages) get a thin dashed line, so
    the chart doesn't pretend to know what happened in between. Readings next to
    such a gap get a dot; estimated ("Guestimate") readings get a hollow dot.
    Only one reading per CHART_FREQ window is drawn.
    """
    color = ORANGE
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

    # Faint fill under the whole line, gaps included.
    ax.fill_between(t, s, color=color, alpha=0.08, linewidth=0, zorder=1)
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


def plot_creator(name, df, out_dir):
    """Render plot_<slug>.svg (for the page) and .png (for og:image) into out_dir.

    Returns the gap caption from plot_series, or None.
    """
    fig, ax = plt.subplots(figsize=(12, 5))
    gap_note = plot_series(ax, df)
    # The name and site stay in the image, since charts get shared on their own.
    # Title with a subtitle under it (instead of a sideways y-axis label).
    ax.set_title(name, fontsize=20, fontweight='bold', loc='left', color='#222', pad=34)
    ax.text(0, 1.03, 'Floatplane subscribers', transform=ax.transAxes,
            ha='left', va='bottom', fontsize=12, color=LABEL_GREY)
    fig.text(0.995, 0.01, 'fp-stats.com', ha='right', va='bottom', fontsize=11, color='#aaa')

    # Dot on the latest reading, labelled with its value. Hollow if that
    # reading is an estimate, matching the estimate markers in plot_series.
    last_t, last_s = df['Time'].iloc[-1], df['Subscribers'].iloc[-1]
    if 'guestimate' in str(df['Source'].iloc[-1]).lower():
        ax.scatter([last_t], [last_s], s=50, facecolors='white', edgecolors=ORANGE, linewidths=2, zorder=5)
    else:
        ax.scatter([last_t], [last_s], s=50, color=ORANGE, edgecolors='white', linewidths=1.5, zorder=5)
    # The label goes right of the dot, where the line never is.
    ax.annotate(f'{int(last_s):,}', (last_t, last_s), xytext=(9, 0), textcoords='offset points',
                ha='left', va='center', fontsize=13, fontweight='bold', color=ORANGE, zorder=5)

    # Y axis starts at zero.
    ax.set_ylim(bottom=0)
    # Room on the right for the latest-value label, and a strip on the left
    # for the y values, so they never sit on top of the line.
    xmin, xmax = ax.get_xlim()
    ax.set_xlim(xmin - (xmax - xmin) * 0.07, xmax + (xmax - xmin) * 0.05)

    # Years along the bottom, with a tick on the zero line at each year and a
    # smaller one at each quarter, so every dot column leads down to a year.
    # Nice, round y steps that adapt to each creator's range (LTT lands on
    # 10k steps, small creators get sensibly-scaled ones).
    ax.xaxis.set_major_locator(mdates.YearLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y'))
    ax.xaxis.set_minor_locator(mdates.MonthLocator(bymonth=[4, 7, 10]))
    ax.yaxis.set_major_locator(MaxNLocator(nbins=8, steps=[1, 2, 2.5, 5, 10]))
    ax.tick_params(length=0, labelcolor=LABEL_GREY)
    ax.tick_params(axis='x', which='major', length=7, width=1.2, color=BASELINE_GREY)
    ax.tick_params(axis='x', which='minor', length=3.5, width=1, color=TICK_GREY)

    # No axis lines: a darker zero baseline, and the y values written just
    # above their row at the left edge.
    ax.spines[['left', 'bottom', 'top', 'right']].set_visible(False)
    ax.axhline(0, color=BASELINE_GREY, linewidth=1.2, zorder=2)
    ax.tick_params(axis='y', labelleft=False)
    ymax = ax.get_ylim()[1]
    rows = [y for y in ax.get_yticks() if 0 < y <= ymax]
    for y in rows:
        ax.annotate(f'{int(y):,}', (0, y), xycoords=('axes fraction', 'data'), xytext=(0, 3),
                    textcoords='offset points', ha='left', va='bottom', fontsize=12, color=LABEL_GREY)

    # Instead of gridlines: light dots at every quarter on each value row,
    # starting right of the value strip so they never touch the numbers.
    xmin, xmax = ax.get_xlim()
    x0 = xmin + (xmax - xmin) * 0.065
    quarters = mdates.MonthLocator(bymonth=[1, 4, 7, 10])
    cols = [x for x in quarters.tick_values(mdates.num2date(x0), mdates.num2date(xmax)) if x0 <= x <= xmax]
    ax.scatter([x for x in cols for _ in rows], [y for _ in cols for y in rows],
               s=9, color=DOT_GREY, edgecolors='none', zorder=0)

    plt.tight_layout()
    slug = creator_filename(name)
    with atomic_write(f'{out_dir}/plot_{slug}.svg') as tmp:
        fig.savefig(tmp, format='svg')
    # Also a raster copy for og:image link previews (messengers rarely render
    # SVG). 12x5in at 100 dpi -> OG_IMAGE_W x OG_IMAGE_H, white background.
    with atomic_write(f'{out_dir}/plot_{slug}.png') as tmp:
        fig.savefig(tmp, format='png', dpi=100, facecolor='white')
    plt.close(fig)
    return gap_note


def sparkline_svg(df, width=120, height=28, days=365):
    """Tiny inline SVG of the last `days` of readings (one point per week), for
    the creators list. Scaled to its own min..max, so it shows the trend, not
    the size. Plain SVG text: a few hundred bytes, no image file."""
    recent = df[df['Time'] >= df['Time'].iloc[-1] - pd.Timedelta(days=days)]
    s = recent.set_index('Time')['Subscribers'].resample('W').last().dropna()
    if len(s) < 2:
        return ''
    lo, hi = s.min(), s.max()
    pad = 3  # keep the stroke inside the box
    xs = [pad + i * (width - 2 * pad) / (len(s) - 1) for i in range(len(s))]
    ys = [height / 2] * len(s) if hi == lo else \
         [pad + (hi - v) * (height - 2 * pad) / (hi - lo) for v in s]
    pts = ' '.join(f'{x:.1f},{y:.1f}' for x, y in zip(xs, ys))
    return (f'<svg class="spark" width="{width}" height="{height}" viewBox="0 0 {width} {height}" '
            f'aria-hidden="true"><polyline points="{pts}" fill="none" stroke="{ORANGE}" '
            'stroke-width="1.5" stroke-linejoin="round" stroke-linecap="round"/></svg>')
