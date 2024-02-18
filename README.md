# Simple Python Economist Podcast RSS Server

Podcast RSS server based in Python Flask server. This is meant to be run preiodically with cron. It builds a static directory containing recent Economist episodes and an rss feed.

The server scans the `/app/static/podcast1/audios` on start and serves all the mp3s that it finds.

## Requirements

Python & a web server. See `requirements.txt`

## Quick start

1. Edit `config.py`

2. Using the same `APP_ROOT` path as above

```
APP_ROOT=/scratch/econpod-cron # set according to step 1
python3 -m venv env
source env/bin/activate
pip install -r requirements.txt
cp -r static $APP_ROOT
mkdir ${APP_ROOT}/data
```

3. config cron with the absolute path of the .py files, and the base url as the arg

```
* * * * 4,5 /home/econpod/econpod-cron/env/bin/python /home/econpod/econpod-cron/cronny.py >/dev/null 2>&1
```

4. serve it!

For nginx use something like,

```
location /ec/ {
            alias $APP_ROOT/static/;
    }
```

See `nginx.conf`.

5. point podcast app to https://me.com/ec/feed ([baseUrl]/feed, where baseUrl is set in config.py)

Testing

run `tests.py` and watch for errors like `[!] Error...`

## Notifications

Gotify or Fastmail smtp (see config.py to set usernames and tokens)
