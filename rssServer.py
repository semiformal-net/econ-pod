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

##
#  FUNCTIONS
#
##
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
        print('Error: fetching {}: {}'.format(issuezip,e))
    else:
        issue_ready=True

    return issue_ready, issuezip

def dl_issue(issuezip):

    #
    # assumes that url has been checked
    #

    now = datetime.datetime.now()
    print('Fetching {}'.format(issuezip))

    # unzip on the fly
    with urlopen(issuezip) as zipresp:
        with ZipFile(BytesIO(zipresp.read())) as zfile:
            zfile.extractall('/app/static/podcast1/audios') # put unzipped files into the podcast static dir

    now2 = datetime.datetime.now()
    dltime=(now2-now).total_seconds()

    return dltime

#
#
#
#

baseUrl = os.getenv('BASE_URL')
if baseUrl is None:
    baseUrl='http://127.0.0.1:5500/'
app = Flask(__name__, static_url_path='', static_folder='static', template_folder='templates')

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

#
# 2. loop, looking for a valid issue
#
for i in list(zip( schedule_day[:-3:-1], issues[:-3:-1])): # last two items in list, in reverse order
    ready, issuezip=issue_ready(i[0],i[1])
    if ready:
        dltime=dl_issue(issuezip)
        break

if not ready:
    print("Error: Unable to get an issue")
    sys.exit(4)
#
# 3a. We build a json called podcasts which contains info about the files
#
podcasts={
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

#
# 3b. to complete the podcasts json we scan the static/podcast1/audios/ directory and gather info about each mp3 file
#
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

filesize_mb=sizecounter/1024/1024
print('Downloaded {:.1f}MB ({} files) in {:.1f}s ({:.1f} MB/s)'.format( filesize_mb , counter, dltime , filesize_mb/dltime  ))

#
# 4. finally we serve the rss using a template
#

@app.route('/<podcast>/rss')
def rss(podcast):
    template =  render_template('base.xml', podcast=podcasts['podcasts'][podcast], baseUrl=podcasts['baseUrl'])
    response = make_response(template)
    response.headers['Content-Type'] = 'application/rss+xml'
    return response
