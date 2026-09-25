FROM python:3.10-slim
RUN apt-get update && apt-get install -y --no-install-recommends cron vim \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY crontab /etc/cron.d/crontab
COPY src/main.py /app/main.py
COPY src/plot.py /app/plot.py
COPY src/requirements.txt /app/requirements.txt
 
RUN pip3 install -r /app/requirements.txt
RUN chmod 0644 /etc/cron.d/crontab
RUN /usr/bin/crontab /etc/cron.d/crontab
RUN touch /var/log/cron.log
RUN touch /app/script.log

# run crond as main process of container
CMD ["cron", "-f"]


