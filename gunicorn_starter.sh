#!/bin/sh
rm -f /app/static/podcast1/audios/* # clear out old podcast on start
gunicorn rssServer:app -w 1 --threads 1 -b 0.0.0.0:5500
