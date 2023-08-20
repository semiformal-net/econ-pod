from flask import Flask, render_template, make_response, send_from_directory, send_file, url_for
import json
import os
import sys
import datetime
import sqlite3
import pandas as pd
# for zip file download and extract
from urllib.request import urlopen
from urllib.error import HTTPError
from zipfile import ZipFile
from io import BytesIO
import pickle
#from apscheduler.schedulers.background import BackgroundScheduler
from flask_apscheduler import APScheduler
import atexit
import requests

###############################################################
#
# CONSTANTS
#
###############################################################


#prod
PICKLE_PATH='/data/current_issue.pkl'
# base for audio files, jpg, feed, etc.
PODCAST_BASE_PATH='/app/static/'

#debug
#PICKLE_PATH='/tmp/econpoddata/current_issue.pkl'
#PODCAST_BASE_PATH='/tmp/econpodstatic/'

LOGO_PATH='static/economist_logo.png'
baseUrl = os.getenv('BASE_URL')
if baseUrl is None:
    baseUrl='http://127.0.0.1:5500/'
gotify_host = os.getenv('GOTIFY_HOST')
if gotify_host is None:
    gotify_host='http://127.0.0.1:8008'
gotify_host=gotify_host.rstrip('/') # no trailing slash
gotify_token = os.getenv('GOTIFY_TOKEN')
if gotify_token is None:
    gotify_token='SeCrEt'

###############################################################
#
# CLASSES
#
###############################################################

# set configuration values
class Config:
    SCHEDULER_API_ENABLED = True

class Podcast:
    def __init__(self, publication_date=None, is_published: bool=False, issue_number: int=0):
        self.url = self.date_issue_to_url(publication_date,issue_number)
        self.publication_date = publication_date
        self.is_published = is_published
        self.issue_number = issue_number

    def date_issue_to_url(self,date,issue):
        year = date.strftime('%Y')
        month = date.strftime('%m')
        day = date.strftime('%d')
        date = date.strftime('%Y%m%d')
        issuezip="http://audiocdn.economist.com/sites/default/files/AudioArchive/{0}/{2}/Issue_{1}_{2}_The_Economist_Full_edition.zip".format(year, issue, date)
        return issuezip

    def issue_ready(self):
        if self.url is None:
            self.is_published = False
            return False
        try:
            a=urlopen(self.url)
        except HTTPError as e:
            # "e" can be treated as a http.client.HTTPResponse object
            #print('Error: fetching {}: {}'.format(issuezip,e))
            self.is_published=False
        else:
            self.is_published=True

        return self.is_published

base_podcasts={
"baseUrl" : baseUrl,
"podcast" : {
    "title": "econpod",
    "author" : "stickygecko",
    "contactEmail" : "econpod@podcast.com",
    "contactName" : "Anonymous",
    "description" : "The current audio edition of the Economist",
    "languaje" : "en-us",
    "coverFilename" : "economist_logo.png",
    "rssUrl" : "feed"
}
}

###############################################################
#
# FUNCTIONS
#
###############################################################

def get_current_issue_from_db():
    #
    # The rule is that the DB shall always store the last available (is_published=True) issue
    #

    if not os.path.isfile(PICKLE_PATH):
        print('[*] Warning: state file {} does not exist'.format(PICKLE_PATH))
        return None

    if not os.access(PICKLE_PATH, os.R_OK):
        print('[*] Warning: state file {} cannot be read'.format(PICKLE_PATH))
        return None

    with open(PICKLE_PATH, 'rb') as f:
        current_issue=pickle.load(f)
    return current_issue

def put_current_issue_to_db(current_issue):
    #
    # The rule is that the DB shall always store the last available (is_published=True) issue
    #

    with open(PICKLE_PATH, 'wb') as f:
        pickle.dump(current_issue, f)

def same_week_as_xmas(date):
    # Get the week number of Christmas for the given year
    xmas_year = date.year
    xmas_week_num = datetime.date(xmas_year, 12, 25).isocalendar()[1]

    # Get the week number of the given date
    input_week_num = date.isocalendar()[1]

    # Check if the week numbers are the same
    return input_week_num == xmas_week_num

def next_issue(current_issue):
    if not isinstance(current_issue, Podcast):
        return None

    now=datetime.datetime.now()

    if now <= (current_issue.publication_date + datetime.timedelta(7)):
        return Podcast(publication_date=current_issue.publication_date + datetime.timedelta(7), is_published=False, issue_number=current_issue.issue_number+1)
    else:
        # there are one or more saturdays between the current issue and the next issue, so scan. This can arise for two reasons:
        #   - the 'current issue' is way out of date, perhaps because the app has an old state
        #   - we are at one of the times of the year when econ skip an issue (xmas or summer break)
        # to find out what is happening you have to do two passes:
        #  1. test all of the possible saturdays
        #  2. figure out which one to return

        d = datetime.date.today()
        t = datetime.timedelta((12 - d.weekday()) % 7)
        if t.days == 0: # if today is a saturday jump ahead a week
            t=datetime.timedelta(days=7)
        next_next_next_saturday=d + t + datetime.timedelta(days=21)
        saturdays=pd.date_range(current_issue.publication_date , next_next_next_saturday.strftime('%Y%m%d') ,freq='W-SAT') # a list of saturdays, starting with current issue, ending with saturday in about three weeks

        issue_list=[]
        i=1
        base_issue_number=current_issue.issue_number+1
        while ( i<len(saturdays) ):
            next_issue = Podcast(publication_date=saturdays[i], is_published=False, issue_number=base_issue_number)
            issue_list.append(next_issue)
            ready=next_issue.issue_ready()
            print('[DEBUG] Next issue ({}): {} || {}'.format(saturdays[i],ready,next_issue.url))
            i=i+1
            if ready:
                # each time you encounter a valid issue, increment the issue number
                base_issue_number=base_issue_number+1

        # The last issue is published, return it
        if issue_list[-1].is_published:
            return issue_list[-1]

        # all the tested issues are ready=False return the first upcoming one (after now())
        i_ready=[ x.is_published for x in issue_list ]
        if not all(i_ready):
            dd=[ i for i in issue_list if i.publication_date>now ]
            return dd[0]

        # now it is weird. if a long time has past you can get a bunch of issues, some ready=True, some ready=False
        # return the last one that is ready
        dd=[ i for i in issue_list[::-1] if i.is_published ]
        return dd[0]

    return None

def init_current_issue():

    current_issue=get_current_issue_from_db()
    if current_issue is None:
        # This is the cold start logic. If you are unable to warm start with a valid issue.
        schedule_day=build_schedule()
        issues=build_issues(schedule_day)
        valid_day, issuezip=find_valid_issue(schedule_day,issues) # the zip file to grab
        current_issue = Podcast(publication_date=valid_day[0], is_published=True, issue_number=valid_day[1])
        print('[*] Warning: Cold start, detected issue {} ({})'.format(current_issue.publication_date,current_issue.issue_number))
    else:
        print('Found issue {} ({}) in database, resuming'.format(current_issue.publication_date,current_issue.issue_number))

    return current_issue

def dl_issue(issuezip):

    #
    # assumes that url has been checked
    #

    now = datetime.datetime.now()
    print('[*] Fetching {}'.format(issuezip))

    # unzip on the fly
    with urlopen(issuezip) as zipresp:
        with ZipFile(BytesIO(zipresp.read())) as zfile:
            zfile.extractall(os.path.join(PODCAST_BASE_PATH,'audios')) # put unzipped files into the podcast static dir

    now2 = datetime.datetime.now()
    dltime=(now2-now).total_seconds()

    return dltime

def build_schedule():
    #
    # Build schedule_day[] and issues[] lists: code courtesy of https://github.com/evmn/the-economist
    #
    # next_saturday
    d = datetime.date.today()
    t = datetime.timedelta((12 - d.weekday()) % 7)
    if t.days == 0: # if today is a saturday jump ahead a week
        t=datetime.timedelta(days=7)
    next_saturday=d + t
    schedule_day = pd.date_range('20120101',next_saturday.strftime('%Y%m%d'),freq='W-SAT') # a long list of saturdays
    return schedule_day

def build_issues(schedule_day):
    # issue number can becomputed from a date.
    # build a list of issues corresonding to each date in the schedules
    issues=[]
    weeks=0
    for i in schedule_day:
        year = i.strftime('%Y')
        month = i.strftime('%m')
        day = i.strftime('%d')
        date = i.strftime('%Y%m%d')
        issue = 8766+weeks
        issue = issue - 2 # issue got out of sync
        issues.append(issue)
        if (int(month) != 12) or (int(day) < 25): # no issue near xmas
            weeks=weeks+1
    return issues

def issue_ready(date,issue):
    issue_ready=False
    year = date.strftime('%Y')
    month = date.strftime('%m')
    day = date.strftime('%d')
    date = date.strftime('%Y%m%d')

    issuezip="http://audiocdn.economist.com/sites/default/files/AudioArchive/{0}/{2}/Issue_{1}_{2}_The_Economist_Full_edition.zip".format(year, issue, date)
    try:
        a=urlopen(issuezip)
    except HTTPError as e:
        # "e" can be treated as a http.client.HTTPResponse object
        pass #print('Error: fetching {}: {}'.format(issuezip,e))
    else:
        issue_ready=True

    return issue_ready, issuezip

def find_valid_issue(schedule_day,issues):
    for i in list(zip( schedule_day[:-4:-1], issues[:-4:-1])): # last three (!) items in list, in reverse order
        ready, issuezip=issue_ready(i[0],i[1])
        if ready:
            return i,issuezip

    if not ready:
        print("Error: Unable to get an issue")
    sys.exit(4)

def build_json(base_json):
    podcasts = base_json # copy
    audios=[]
    adir=os.path.join(PODCAST_BASE_PATH,'audios')
    counter=0
    sizecounter=0
    # iterate over files in that directory
    for filename in sorted(os.listdir( adir )):
        f = os.path.join(adir, filename)
        # checking if it is a file
        if os.path.isfile(f):
            fname=os.path.basename(f)
            pname, ext = os.path.splitext(fname)
            # only process mp3s
            if not ext.lower() == '.mp3':
                continue
            F={"title": pname,
            "description": pname,
            "filename":fname,
            "date": datetime.datetime.fromtimestamp( os.path.getmtime(f) )
                .strftime( "%a, %d %b %Y %H:%M:%S -05:00"),
            "length": os.path.getsize(f)
            }
            audios.append(F)
            counter=counter+1
            sizecounter=sizecounter+os.path.getsize(f)

    podcasts['podcast']['audios'] = audios
    return counter, sizecounter, podcasts

def gotify_push(msg):
    try:
        resp = requests.post('{}/message?token={}'.format(gotify_host,gotify_token), json={
        "message": msg, # completely uncechked input
        "priority": 2,
        "title": "Econpod"})
    except requests.exceptions.RequestException as e:
        print('Failed to push notification to {}'.format(gotify_host))
        print(e)

def delete_files_in_directory(directory_path):
   try:
     with os.scandir(directory_path) as entries:
       for entry in entries:
         if entry.is_file():
            os.unlink(entry.path)
   except OSError:
     print("Error occurred while deleting files.")

#
# END FUNCTIONS ---------------------------------------------------------------------------
#
