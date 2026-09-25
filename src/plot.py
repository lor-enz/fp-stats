import csv
import os

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import pandas as pd

DEV_DATA_FOLDER = "~/projects/floatplane-watch/data"
DOCKER_DATA_FOLDER = "/configdata"
DEV_PLOT_FOLDER = "/tmp/fp-plots"
DOCKER_PLOT_FOLDER = "/plots"

is_dev = False

DATA_FOLDER = DEV_DATA_FOLDER if is_dev else DOCKER_DATA_FOLDER
PLOT_FOLDER = DEV_PLOT_FOLDER if is_dev else DOCKER_PLOT_FOLDER


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
    df = pd.read_csv(path, header=None, names=['Creator', 'Time', 'Subscribers', 'Source'])
    df['Time'] = pd.to_datetime(df['Time'], format='%Y-%m-%d_%H-%M-%S')
    df.sort_values('Time', inplace=True)
    return df


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
    creators_data = []
    for name in load_creators():
        df = load_creator_data(name)
        if df is None or df.empty:
            print(f"No data for {name}, skipping")
            continue
        plot_creator(name, df)
        creators_data.append((name, df))
        print(f"Plotted {name}")
    write_index(creators_data)
    print(f"Index written to {PLOT_FOLDER}/index.html")


if __name__ == "__main__":
    create_plot()
