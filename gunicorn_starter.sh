#!/bin/sh
gunicorn rssServer:app -w 2 --threads 2 -b 0.0.0.0:5500
