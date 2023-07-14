from flask import Flask, render_template, make_response, send_from_directory, send_file, url_for
import json
import os
import sys
import datetime
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

#
# CONSTANTS
#
# build a json called podcasts which contains info about the files
#
baseUrl = os.getenv('BASE_URL')
if baseUrl is None:
    baseUrl='http://127.0.0.1:5500/'

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
"podcasts" : {
    "podcast1" : {
    "title": "podcast1",
    "author" : "podcast1",
    "contactEmail" : "podcast@podcast.com",
    "contactName" : "Podcaster name",
    "description" : "podcast1 description",
    "languaje" : "en-us",
    "coverFilename" : "podcast1/economist_logo.png",
    "rssUrl" : "podcast1/rss",
    "audiosFolder" : "podcast1/audios/"
    }
    }
}

##
#  FUNCTIONS
#
##

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
    saturdays=pd.date_range(current_issue.publication_date , current_issue.publication_date + datetime.timedelta(21) ,freq='W-SAT') # a list of saturdays, starting with current issue

    i=1
    while same_week_as_xmas(saturdays[i]):
        i=i+1

    next_issue = Podcast(publication_date=saturdays[i], is_published=False, issue_number=current_issue.issue_number+1)

    return next_issue

def init_current_issue():

    schedule_day=build_schedule()
    issues=build_issues(schedule_day)
    valid_day, issuezip=find_valid_issue(schedule_day,issues) # the zip file to grab
    current_issue = Podcast(publication_date=valid_day[0], is_published=True, issue_number=valid_day[1])
    return current_issue

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

def dl_issue(issuezip):

    #
    # assumes that url has been checked
    #

    now = datetime.datetime.now()
    print('[*] Fetching {}'.format(issuezip))

    # unzip on the fly
    with urlopen(issuezip) as zipresp:
        with ZipFile(BytesIO(zipresp.read())) as zfile:
            zfile.extractall('/app/static/podcast1/audios') # put unzipped files into the podcast static dir

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
        issue = issue - 1 # issue got out of sync
        issues.append(issue)
        if (int(month) != 12) or (int(day) < 25): # no issue near xmas
            weeks=weeks+1
    return issues

def find_valid_issue(schedule_day,issues):
    for i in list(zip( schedule_day[:-3:-1], issues[:-3:-1])): # last two items in list, in reverse order
        ready, issuezip=issue_ready(i[0],i[1])
        if ready:
            return i,issuezip

    if not ready:
        print("Error: Unable to get an issue")
    sys.exit(4)

def build_json(base_json):
    podcasts = base_json # copy
    audios=[]
    adir='static/'+podcasts['podcasts']['podcast1']['audiosFolder']
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

    podcasts['podcasts']['podcast1']['audios'] = audios
    return counter, sizecounter, podcasts

def gotify_push(msg):
    host='https://gotify.host.com' # no trailing slash
    token='A6ztifhsaj2AAS8n'
    resp = requests.post('{}/message?token={}'.format(host,token), json={
        "message": msg, # completely uncechked input
        "priority": 2,
        "title": "Econpod"
    })
#
# END FUNCTIONS ---------------------------------------------------------------------------
#

app = Flask(__name__, static_url_path='', static_folder='static', template_folder='templates')
app.config.from_object(Config())

scheduler = APScheduler()
# Shut down the scheduler when exiting the app
atexit.register(lambda: scheduler.shutdown())

@scheduler.task('interval', id='cron', hours=1, misfire_grace_time=900)
def cron():
    try:
        with open('/tmp/current_issue.pkl', 'rb') as f:
            current_issue=pickle.load(f)
    except:
        print('unable to load pickle current issue state')
    if not isinstance(current_issue, Podcast):
        print('cron got bad data')

    print( '[*] Scheduled check ({}) ...'.format(datetime.datetime.now()) )

    print('\t [] Current issue: {0}, (ready={1})'.format( current_issue.publication_date,current_issue.is_published) )
    n=next_issue(current_issue)
    ready=n.issue_ready()
    print( '\t [] Next issue: {0}, (ready={1})'.format( n.publication_date,ready ) )

    gotify_push('Check for {}; is ready={}'.format(n.publication_date,ready))

    if n.is_published:
        with open('/tmp/current_issue.pkl', 'wb') as f:
            pickle.dump(n, f)
        os.system('rm -rf /app/static/podcast1/audios/*') # assume unix host
        dltime=dl_issue(n.url) # download and extract the issue
        # I don't get how the main flask app has the context of podcasts but this seems to work?'
        counter, sizecounter, podcasts = build_json(base_podcasts)

        filesize_mb=sizecounter/1024/1024
        print('[*] Downloaded {:.1f}MB ({} files) in {:.1f}s ({:.1f} MB/s)'.format( filesize_mb , counter, dltime , filesize_mb/dltime  ))
        gotify_push('New episode ({}) is ready!'.format(current_issue.publication_date))

@app.route('/<podcast>/rss')
def rss(podcast):
    template =  render_template('base.xml', podcast=podcasts['podcasts'][podcast], baseUrl=podcasts['baseUrl'])
    response = make_response(template)
    response.headers['Content-Type'] = 'application/rss+xml'
    return response

#if __name__ == "__main__":

scheduler.init_app(app)

current_issue = init_current_issue()
current_issue=Podcast(publication_date=datetime.datetime( 2023,5,13,0,0,0 ), is_published=True, issue_number=9346)
with open('/tmp/current_issue.pkl', 'wb') as f:
    pickle.dump(current_issue, f)
#scheduler.add_job(func=cron, trigger="interval", seconds=30) # hours=1
scheduler.start()

dltime=dl_issue(current_issue.url) # download and extract the issue
counter, sizecounter, podcasts = build_json(base_podcasts)

filesize_mb=sizecounter/1024/1024
print('[*] Downloaded {:.1f}MB ({} files) in {:.1f}s ({:.1f} MB/s)'.format( filesize_mb , counter, dltime , filesize_mb/dltime  ))

gotify_push('New episode ({}) is ready!'.format(current_issue.publication_date))

#app.run()
