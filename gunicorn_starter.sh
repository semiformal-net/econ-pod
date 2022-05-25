#!/bin/sh
gunicorn rssServer:app -w 1 --threads 1 -b 0.0.0.0:5500
