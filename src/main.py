import requests
import csv
import time
import os

DEV_DATA_FOLDER = "~/projects/floatplane-watch/data"
DOCKER_DATA_FOLDER = "/configdata"

is_dev = False

DATA_FOLDER = DEV_DATA_FOLDER if is_dev else DOCKER_DATA_FOLDER

headers = {
    "Host": "www.floatplane.com",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/116.0",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    # "Accept-Encoding": "gzip, deflate, br", # Don't accept this as it will require additional code to decompress
    "Referer": "https://www.google.com/",
    "DNT": "1",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "cross-site",
    "Sec-GPC": "1",
    "Pragma": "no-cache",
    "Cache-Control": "no-cache"
}

API_URL = "https://www.floatplane.com/api/v2/plan/info?creatorId={}"


def get_current_time_formatted():
    return time.strftime("%Y-%m-%d_%H-%M-%S", time.gmtime())


def load_creators(path):
    creators = []
    with open(path, newline='') as f:
        for row in csv.reader(f):
            name, creator_id, skip = row[0].strip(), row[1].strip(), row[2].strip()
            if skip == 'False':
                creators.append((name, creator_id))
    return creators


def fetch_sub_count(creator_id):
    response = requests.get(API_URL.format(creator_id), headers=headers)
    if response.status_code == 200:
        return response.json()['totalSubscriberCount']
    raise Exception(f"Status code: {response.status_code}")


def save_data_to_file(path, row):
    with open(path, 'a', newline='') as f:
        csv.writer(f).writerow(row)


def creator_filename(name):
    return name.replace(' ', '-')


if __name__ == "__main__":
    print(f"Starting script at {get_current_time_formatted()}")
    creators = load_creators(f'{DATA_FOLDER}/creators.csv')
    current_time = get_current_time_formatted()

    for name, creator_id in creators:
        try:
            sub_count = fetch_sub_count(creator_id)
            path = f'{DATA_FOLDER}/data_{creator_filename(name)}.csv'
            save_data_to_file(path, [name, current_time, sub_count, 'fp-stats'])
            print(f"{name}: {sub_count}")
        except Exception as e:
            print(f"Error fetching {name}: {e}")

    from plot import create_plot
    create_plot()
    print(f"DONE at {get_current_time_formatted()}")
