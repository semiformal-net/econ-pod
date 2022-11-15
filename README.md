# Simple Python Economist Podcast RSS Server

Podcast RSS server based in Python Flask server. This is meant to run in a container and server a directory containing recent Economist episodes.

The server scans the `/app/static/podcast1/audios` on start and serves all the mp3s that it finds.

## Requirements

Python, Flask and gunicorn. See `requirements.txt`

## Quick start

Build the container and set the BASE_URL environment variable to suit your network,

```
docker build -t econpod .
docker run -it -p 5500:5500 -e BASE_URL=https://myrss.com/ econpod
```

Now point your podcasting software to `BASE_URL/podcast1/rss`

## Credit

Adapted from [archidemus/Simple-Podcast-RSS-Feed-Server](https://github.com/archidemus/Simple-Podcast-RSS-Feed-Server)
