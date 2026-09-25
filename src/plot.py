import csv
import datetime
import os

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import pandas as pd

DATA_FOLDER = "/configdata"
PLOT_FOLDER = "/plots"

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
    df = df.set_index('Time').resample('D').last().dropna(subset=['Subscribers']).reset_index()
    return df


def compute_stats(df):
    current = int(df['Subscribers'].iloc[-1])
    peak = int(df['Subscribers'].max())
    cutoff = df['Time'].iloc[-1] - pd.Timedelta(days=30)
    past = df[df['Time'] <= cutoff]
    change_30d = (current - int(past['Subscribers'].iloc[-1])) if not past.empty else None
    return {'current': current, 'peak': peak, 'change_30d': change_30d}


def page_shell(title, body, last_updated):
    ts = last_updated.strftime('%Y-%m-%dT%H:%M:%SZ')
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title}</title>
<style>{_CSS}</style>
</head>
<body>
<div id="stale">&#9888; Data hasn&#39;t updated in over 24&nbsp;hours.</div>
<script>if(Date.now()-new Date("{ts}")>864e5)document.getElementById('stale').style.display='block';</script>
{body}
<footer>Updated {last_updated.strftime('%Y-%m-%d %H:%M')} UTC &middot; <a href="/">Home</a> &middot; <a href="/creators.html">All creators</a></footer>
</body>
</html>"""


def plot_creator(name, df):
    fig, ax = plt.subplots(figsize=(12, 5))
    ax.plot(df['Time'], df['Subscribers'], linewidth=1.5, color='#f64b00')
    ax.set_title(name, fontsize=16)
    ax.set_ylabel('Floatplane Subscribers')
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
    ax.xaxis.set_major_locator(mdates.AutoDateLocator())
    fig.autofmt_xdate()
    plt.tight_layout()
    fig.savefig(f'{PLOT_FOLDER}/plot_{creator_filename(name)}.svg', format='svg')
    plt.close(fig)


def write_creator_page(name, df, last_updated, note=None):
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
    with open(f'{PLOT_FOLDER}/{slug}.html', 'w') as f:
        f.write(page_shell(f'{name} — Floatplane Stats', body, last_updated))


def write_index(creators_data):
    rows = []
    for name, df in creators_data:
        current = int(df['Subscribers'].iloc[-1])
        slug = creator_filename(name)
        rows.append(f'<h2>{name} &mdash; {current:,}</h2><img src="plot_{slug}.svg" style="max-width:100%">')

    html = f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="utf-8"><title>Floatplane Stats</title>
<style>body{{font-family:sans-serif;max-width:1100px;margin:auto;padding:1rem}}</style>
</head>
<body>
<h1>Floatplane Subscriber Stats</h1>
{''.join(rows)}
</body>
</html>"""

    with open(f'{PLOT_FOLDER}/index.html', 'w') as f:
        f.write(html)


def create_plot():
    os.makedirs(PLOT_FOLDER, exist_ok=True)
    last_updated = datetime.datetime.utcnow()
    creators_data = []
    for name in load_creators():
        df = load_creator_data(name)
        if df is None or df.empty:
            print(f"No data for {name}, skipping")
            continue
        plot_creator(name, df)
        write_creator_page(name, df, last_updated)
        creators_data.append((name, df))
        print(f"Plotted {name}")
    write_index(creators_data)
    print(f"Site written to {PLOT_FOLDER}/")


if __name__ == "__main__":
    create_plot()
