FROM python:3.14-slim
RUN apt-get update && apt-get install -y --no-install-recommends cron vim \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY crontab /etc/cron.d/fp-stats
COPY src/*.py /app/
COPY src/static/ /app/static/
COPY src/requirements.txt /app/requirements.txt

RUN pip3 install -r /app/requirements.txt
# /etc/cron.d entries must be root-owned and not group/world-writable, or cron
# refuses to load them. cron reads this file directly (no `crontab` install and
# no /etc/cron.d duplicate — that combination logged a parse error every scan).
RUN chmod 0644 /etc/cron.d/fp-stats

# run cron in the foreground as the container's main process
CMD ["cron", "-f"]


