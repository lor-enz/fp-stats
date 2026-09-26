# ltt-floatplane-watch

This is the source code behind [www.fp-stats.com](https://fp-stats.com)

This repository contains python code to fetch the current LTT floatplane subscriber number and save it to a file. (src/main.py)
It then triggers a plotting function that uses all the data points in the files to create graphs and HTML pages. (src/pages.py, with src/data.py and src/charts.py)

The docker image is set up to recurringly run that script on a cronjob to regularly grab the current subscriber count and output the current plots as HTML files to the output path.

## Running the docker container

    docker run -d --name fp-stats \
     -v /hostmachine/path/configdata:/configdata \
     -v /hostmachine/path/plots:/plots -e TZ=Europe/Berlin \
     nicepenguin/fp-stats

Or use this for docker compose
```
version: '3'
services:
  fp-stats:
    image: nicepenguin/fp-stats
    container_name: fp-stats
    environment:
      - TZ=Europe/Berlin
    volumes:
      - /hostmachine/path/configdata:/configdata
      - /hostmachine/path/plots:/plots
    restart: unless-stopped

```
### Docker Volumes

- **/configdata** is the container path where the csv files with the grabbed numbers data are saved

- **/plots** is the container path where the output plots are sent to. Choose a host path that enables publishing the html plot files in a streamlined way.

## Continuous integration

GitHub Actions (`.github/workflows/docker-publish.yml`) handle the build:

- **On every push and pull request**, a smoke check runs `python -m py_compile src/*.py` to catch syntax errors before they can reach an image.
- **On push to `main`**, once the smoke check passes, the image is built and pushed to Docker Hub as `nicepenguin/fp-stats:latest` and `nicepenguin/fp-stats:<commit-sha>`.

The image is never built on the server. Saturn only pulls the prebuilt image.

## Development

### Deploy flow

1. Make changes and push them to `main`.
2. Wait for the Docker Hub build action to complete.
3. On saturn, pull the new image, restart the container, and trigger a run immediately:

        docker compose pull fp-stats && docker compose up -d fp-stats && docker exec fp-stats python3 /app/main.py

### Build the image locally

Navigate to the project directory and build the docker image with 
    
    docker build -t nicepenguin/fp-stats .

### Run python locally

Set the `is_dev` in both main.py and pages.py to `True`

Run just `pages.py` to just generate new plots or run `main.py` to both fetch new data and generate plots.

    python3 src/main.py
or

    python3 src/pages.py
