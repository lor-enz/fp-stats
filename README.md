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

## Automatic builds and dependency updates

**Docker image.** GitHub Actions (`.github/workflows/docker-publish.yml`) builds the image and runs `tests/smoke.py` inside it, which renders the whole site from sample data. Pull requests are only checked. Pushes to `main`, a weekly run (Mondays) and manual runs also push `nicepenguin/fp-stats:latest` and `:<commit>` to Docker Hub. The weekly run picks up base-image fixes without code changes. The image is never built on the server. A server stays current if it regularly pulls `:latest` and recreates the container, e.g. with a daily `docker compose pull && docker compose up -d`.

**Dependabot** (`.github/dependabot.yml`) opens grouped pull requests for the pinned Python packages, the base image and GitHub Actions: monthly, security fixes immediately. Since every package is pinned, nothing updates without these pull requests.

**Maintenance**
- Merge Dependabot pull requests once their checks are green. Don't merge red ones; check the failing step first.
- Updates to matplotlib or pandas can pass the smoke test and still change how the charts look. Preview the charts before merging those.
- Pushing needs the repository secrets `DOCKERHUB_USERNAME` and `DOCKERHUB_TOKEN`. Renew the token before it expires.
- Check now and then that the weekly build is green. A failing run means updates have stopped.

## Development

### Deploy flow

1. Make changes and push them to `main`.
2. Wait for the Docker Hub build action to complete.
3. A server that pulls new images regularly picks the change up on its own. To deploy right away instead, pull the new image, restart the container, and trigger a run immediately on the server:

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
