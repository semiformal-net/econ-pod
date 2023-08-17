FROM python:3.9-slim
ENV PYTHONUNBUFFERED 1
COPY requirements.txt /
RUN pip3 install -r /requirements.txt
COPY requirements.txt /app/
COPY rssServer.py /app/
COPY libeconpod.py /app/
COPY gunicorn_starter.sh /app/
COPY templates /app/templates
COPY static /app/static
WORKDIR /app
ENTRYPOINT ["./gunicorn_starter.sh"]
