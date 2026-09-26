import csv
import os

import pandas as pd

DATA_FOLDER = "/configdata"


def creator_filename(name):
    return name.replace(' ', '-')


def load_creators():
    """Return (name, left) for every creator in creators.csv.

    left is True when the skip flag is set: the creator left Floatplane, so
    they're no longer scraped, but their page stays on the site.
    """
    creators = []
    with open(f'{DATA_FOLDER}/creators.csv', newline='') as f:
        for row in csv.reader(f):
            if len(row) < 3:  # skip blank or malformed lines instead of crashing
                continue
            name, skip = row[0].strip(), row[2].strip()
            if skip in ('False', 'True'):
                creators.append((name, skip == 'True'))
    return creators


def load_creator_data(name):
    path = f'{DATA_FOLDER}/data_{creator_filename(name)}.csv'
    if not os.path.exists(path):
        return None
    try:
        df = pd.read_csv(path, header=None, names=['Creator', 'Time', 'Subscribers', 'Source'], on_bad_lines='skip')
    except pd.errors.EmptyDataError:  # zero-byte file
        return None
    df['Time'] = pd.to_datetime(df['Time'], format='%Y-%m-%d_%H-%M-%S', errors='coerce')
    df['Subscribers'] = pd.to_numeric(df['Subscribers'], errors='coerce')
    df.dropna(subset=['Time', 'Subscribers'], inplace=True)
    if df.empty:  # no readable rows
        return None
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
