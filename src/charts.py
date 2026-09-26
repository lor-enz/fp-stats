import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.ticker import MaxNLocator, AutoMinorLocator, FuncFormatter
import pandas as pd

from atomic import atomic_write
from data import creator_filename

# Match the page font: keep SVG text as real text (not paths) so the browser
# renders it in the same sans-serif as the surrounding HTML.
matplotlib.rcParams['svg.fonttype'] = 'none'
matplotlib.rcParams['font.family'] = 'sans-serif'
matplotlib.rcParams['font.sans-serif'] = ['Helvetica', 'Arial', 'DejaVu Sans', 'sans-serif']

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


def plot_creator(name, df, out_dir):
    """Render plot_<slug>.svg (for the page) and .png (for og:image) into out_dir.

    Returns the gap caption from plot_series, or None.
    """
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
    with atomic_write(f'{out_dir}/plot_{slug}.svg') as tmp:
        fig.savefig(tmp, format='svg')
    # Also a raster copy for og:image link previews (messengers rarely render
    # SVG). 12x5in at 100 dpi -> OG_IMAGE_W x OG_IMAGE_H, white background.
    with atomic_write(f'{out_dir}/plot_{slug}.png') as tmp:
        fig.savefig(tmp, format='png', dpi=100, facecolor='white')
    plt.close(fig)
    return gap_note
