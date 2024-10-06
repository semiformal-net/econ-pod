# Economist Podcast RSS Server

Podcast RSS server for the Economist audio edition. This serves the Economist audio edition as a standard rss feed so you can listen to it in your preferred podcast app.

## Requirements

This is meant to be run periodically with cron. It builds a static directory containing recent Economist episodes and an rss feed and requires just Python & a web server. See `requirements.txt`

## Quick start

1. Edit `config.py`

2. Using the same `APP_ROOT` path as above

```
APP_ROOT=/scratch/econpod-cron # set according to step 1
python3 -m venv env
source env/bin/activate
pip install -r requirements.txt
mkdir -p ${APP_ROOT}/data
cp -r static $APP_ROOT
```

3. config cron with the absolute path of the .py files, and the base url as the arg

```
8 * * * 4,5 /home/econpod/econpod-cron/env/bin/python /home/econpod/econpod-cron/cronny.py >/dev/null 2>&1
```

4. serve it!

For nginx use something like,

```
location /ec/ {
            alias $APP_ROOT/static/;
	    default_type application/xml;
    }
```

See `nginx.conf`.

5. point podcast app to https://me.com/ec/feed (i.e., `baseUrl`/feed, where `baseUrl` is set in `config.py`)

Testing

run `tests.py` and watch for errors like `[!] Error...`

## Notifications

The app can notify your users by Gotify or smtp (see config.py to set usernames and tokens) when a new episode is available.
