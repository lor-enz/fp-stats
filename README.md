# ltt-floatplane-watch

This is the source code behind [www.fp-stats.buzz](https://fp-stats.buzz)

This repository contains python code to fetch the current LTT floatplane subscriber number and save it to a file. (src/main.py)
It then triggers a plotting function that uses all the data points in the files to create graphs. (src/plot.py)

The docker image is set up to recurringly run that script on a cronjob to regularly grab the current subscriber count and output the current plots as HTML files to the output path.

## Running the docker container

    docker run -d --name fp-watch \
     -v /hostmachine/path/configdata:/configdata \
     -v /hostmachine/path/plots:/plots -e TZ=Europe/Berlin \
     nicepenguin/fp-watch

Or use this for docker compose
```
version: '3'
services:
  fp-watch:
    image: nicepenguin/fp-watch
    container_name: fp-watch
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

## Development

### Docker

Navigate to the project directory and build the docker image with 
    
    docker build -t nicepenguin/fp-watch .

### Run python locally

Set the `is_dev` in both main.py and plot.py to `True`

Run just `plot.py` to just generate new plots or run `main.py` to both fetch new data and generate plots.

    python3 src/main.py
or

    python3 src/plot.py
