# Simple Python Economist Podcast RSS Server

Podcast RSS server based in Python Flask server. This is meant to run in a container and server a directory containing recent Economist episodes.

The server scans the `/app/static/podcast1/audios` on start and serves all the mp3s that it finds.

## Requirements

Python, Flask, requests and gunicorn. See `requirements.txt`

## Quick start

Build the container and set the BASE_URL environment variable to suit your network,

```
docker build -t econpod .
docker run -it -p 5500:5500 -e BASE_URL=https://myrss.com/ -v /tmp/data:/data econpod
```

Now point your podcasting software to `BASE_URL/podcast1/rss`

## State

This app stores its state in a pickle file in /data. The state contains the data and issue number of a valid issue. The app will start from there and look for a new issue. The app is capable of a cold start if it does not find the right file, but the cold start logic may be flawed. To manually warm start you can try,

```
current_issue=Podcast(publication_date=datetime.datetime( 2023,5,13,0,0,0 ), is_published=True, issue_number=9346)
put_current_issue_to_db(current_issue)
```

Using a recent valid issue number and date.

## Notification

The script will push notifications to a gotify server defined using `GOTIFY_HOST` and `GOTIFY_TOKEN`. An example in docker compose is,

```
  econpod:
    build: ./econ-pod
    container_name: econpod
    environment:
      - BASE_URL=https://host.net/econpod/
      - GOTIFY_HOST=https://gotify.host.net
    env_file: secret_gotify.env
    ports:
      - 5500:5500
    restart: unless-stopped
```

Where `secret_gotify.env` contains,

```
GOTIFY_TOKEN: alkja3ra3f3AFQa
```

## Credit

Adapted from [archidemus/Simple-Podcast-RSS-Feed-Server](https://github.com/archidemus/Simple-Podcast-RSS-Feed-Server)
