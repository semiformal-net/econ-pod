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
import requests
import glob
import jinja2
# for Email
from email import encoders
from email import utils # rfc 822
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import smtplib
# MP3
from mutagen.mp3 import MP3
from mutagen.id3 import ID3, TIT2, TPE1, TALB, APIC
from mutagen.id3 import ID3, ID3NoHeaderError, error
import mutagen

###############################################################
#
# CLASSES
#
###############################################################

class Podcast:
    def __init__(self, publication_date=None, is_published: bool=False, issue_number: int=0):
        self.url = self.date_issue_to_url(publication_date,issue_number)
        self.publication_date = publication_date
        self.is_published = is_published
        self.issue_number = issue_number
        self.articles=0
        self.totalsize=0

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

    def __eq__(self, other):
        # for use with `current_issue == another_issue` tests
        return self.__dict__ == other.__dict__
    def __str__(self):
        # allows print(current_issue)
        return 'Issue {} ({}): published={}\n\t{:.1f} MB ({} files)'.format(self.issue_number, self.publication_date, self.is_published, self.totalsize/1024/1024, self.articles)

class FastmailSMTP(smtplib.SMTP_SSL):
    """A wrapper for handling SMTP connections to Fastmail."""

    def __init__(self, username, password):
        super().__init__('mail.messagingengine.com', port=465)
        self.login(username, password)

    def send_message(self, *,
                     from_addr,
                     to_addrs,
                     msg,
                     subject,
                     attachments=None):
        msg_root = MIMEMultipart()
        msg_root['Subject'] = subject
        msg_root['From'] = from_addr
        msg_root['To'] = ', '.join(to_addrs)

        msg_alternative = MIMEMultipart('alternative')
        msg_root.attach(msg_alternative)
        msg_alternative.attach(MIMEText(msg))

        if attachments:
            for attachment in attachments:
                prt = MIMEBase('application', "octet-stream")
                prt.set_payload(open(attachment, "rb").read())
                encoders.encode_base64(prt)
                prt.add_header(
                    'Content-Disposition', 'attachment; filename="%s"'
                    % attachment.replace('"', ''))
                msg_root.attach(prt)

        self.sendmail(from_addr, to_addrs, msg_root.as_string())


###############################################################
#
# FUNCTIONS
#
###############################################################

def base_podcasts(baseurl):
    return {
    "baseUrl" : baseurl,
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

def get_current_issue_from_db(path):
    #
    # The rule is that the DB shall always store the last available (is_published=True) issue
    #

    if not os.path.isfile(path):
        print('[*] Warning: state file {} does not exist'.format(path))
        return None

    if not os.access(path, os.R_OK):
        print('[*] Warning: state file {} cannot be read'.format(path))
        return None

    with open(path, 'rb') as f:
        current_issue=pickle.load(f)
    return current_issue

def put_current_issue_to_db(current_issue,pth):
    #
    # The rule is that the DB shall always store the last available (is_published=True) issue
    #

    with open(pth, 'wb') as f:
        pickle.dump(current_issue, f)

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
            ready=next_issue.issue_ready()
            issue_list.append(next_issue)
            #print('[DEBUG] Next issue ({}): {} || {}'.format(saturdays[i],ready,next_issue.url))
            i=i+1
            if ready:
                # each time you encounter a valid issue, increment the issue number
                base_issue_number=base_issue_number+1

        # The last issue is published, return it
        if issue_list[-1].is_published:
            return issue_list[-1]

        # all the tested issues are ready=False return the first upcoming one (after now())
        i_ready=[ x.is_published for x in issue_list ]
        if not any(i_ready):
            dd=[ i for i in issue_list if i.publication_date>now ]
            return dd[0]

        # now it is weird. if a long time has past you can get a bunch of issues, some ready=True, some ready=False
        # return the last one that is ready
        dd=[ i for i in issue_list[::-1] if i.is_published ]
        return dd[0]

    return None

def dl_issue(issuezip,pth):

    #
    # assumes that url has been checked
    #

    now = datetime.datetime.now()
    print('[*] Fetching {}'.format(issuezip))

    # unzip on the fly
    try:
        with urlopen(issuezip) as zipresp:
            with ZipFile(BytesIO(zipresp.read())) as zfile:
                zfile.extractall(os.path.join(pth,'audios')) # put unzipped files into the podcast static dir
    except:
        return None

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

def audiodir_scan(pth):
    audios=[]
    adir=os.path.join(pth,'audios')
    counter=0
    sizecounter=0
    cover_found = False
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
            # nudge the modified time _backward_ by a second sequentially. this way if the podcast client sorts by date (instead of by name, as recommended)
            # then the articles will be in order
            file_time=datetime.datetime.fromtimestamp(os.path.getmtime(f))  - datetime.timedelta(seconds=counter)
            # date below should be RFC 822 format for atom spec.
            F={"title": pname,
            "description": pname,
            "filename":fname,
            "date": utils.format_datetime(file_time), #file_time.strftime( "%a, %d %b %Y %H:%M:%S -05:00"),
            "length": os.path.getsize(f)
            }
            audios.append(F)
            counter=counter+1
            sizecounter=sizecounter+os.path.getsize(f)

    return counter, sizecounter, audios

def build_json(baseUrl,audios):
    podcasts = base_podcasts(baseUrl)
    podcasts['podcast']['audios'] = audios
    return podcasts

def gotify_push(gotify_host,gotify_token,msg):
    try:
        resp = requests.post('{}/message?token={}'.format(gotify_host,gotify_token), json={
        "message": msg, # completely uncechked input
        "priority": 2,
        "title": "Econpod"})
    except requests.exceptions.RequestException as e:
        print('[*] Warning: gotify failed to push notification to {}'.format(gotify_host))
        print(e)

def email_push(user,pw,to,msg):
    with FastmailSMTP(user, pw) as server:
        server.send_message(from_addr='econpod@semiformal.net',
                            to_addrs=to,
                            msg=msg,
                            subject=msg)


def delete_files_in_directory(directory_path):
   try:
     with os.scandir(directory_path) as entries:
       for entry in entries:
         if entry.is_file():
            os.unlink(entry.path)
   except OSError:
     print("Error occurred while deleting files.")

def valid_podcast_available(pth):
    if not os.path.isfile(os.path.join(pth,'feed')):
        return False

    if not os.path.isdir(os.path.join(pth,'audios')):
        return False

    mp3counter = len(glob.glob1(os.path.join(pth,'audios'),"*.mp3"))
    if mp3counter<5:
        return False

    return True

def publish(baseUrl,n,pth,jpth,tpth):
    '''
    baseUrl - the location where we are publishing
    n - current_issue Podcast() instance
    pth - the static/ base path which contains the audios/ directory
    jpth - the path containing the jinja template for rss (ie, base.xml)
    tpth - the filename of the jinja template to use ('base.xml')
    '''

    if not isinstance(n, Podcast):
        print('[!] Error: publish() was not passed a valid issue')
        return

    if not os.path.isfile(os.path.join(jpth,tpth)):
        print('[!] Error: publish() was not passed a valid jinja template')
        return

    try:
        delete_files_in_directory(os.path.join(pth,'audios'))
    except:
        print('unable to purge old episodes')
        return

    try:
        dltime=dl_issue(n.url,pth) # download and extract (to PODCAST_BASE_PATH/audios) the issue
    except:
        print('failed to download')
        return
    if dltime is None:
        print('[!] Failed to download.')
        return
    try:
        counter, sizecounter, audios=audiodir_scan(pth)
        n.articles=counter
        n.totalsize=sizecounter
    except:
        print('failed to scan audio dir')

    try:
        podcasts = build_json(baseUrl,audios)
    except:
        print('failed to build json')
        return

    filesize_mb=sizecounter/1024/1024
    print('[*] Downloaded {:.1f}MB ({} files) in {:.1f}s ({:.1f} MB/s)'.format( filesize_mb , counter, dltime , filesize_mb/dltime  ))

    # write a copy of the rss feed to a file
    templateLoader = jinja2.FileSystemLoader(searchpath=jpth)
    templateEnv = jinja2.Environment(loader=templateLoader)
    template = templateEnv.get_template(tpth)
    rendered = template.render(podcast=podcasts['podcast'], baseUrl=podcasts['baseUrl'])
    with open(os.path.join(pth,'feed'),'w') as f:
        f.write(rendered)

def cold_start(PICKLE_PATH):
    # This is the cold start logic. If you are unable to warm start with a valid issue.
    #
    # I wrote a bot that reports the current issue. If that is responding, we will trust it and use that issue.
    # otherwise we can scan...

    try:
        r=requests.get('https://econpod-23523.ue.r.appspot.com') #econissuebot (Beep!)
        if r.json()['success']:
            print( '[DEBUG] econissuebot reports: {} ({})'.format(r.json()['issue'], r.json()['published_date']))
        else:
            print( '[!] Warning: econissuebot failed with: {}'.format(r.json()['error']))
    except:
        print('[!] Warning: econissuebot failed')

    if r:
        pubdate=datetime.datetime.strptime(r.json()['published_date'], '%a, %d %b %Y %X %Z')
        # published date is the day the issue was released. the date on the mag cover is always (?) a saturday, so we have to advance the published date to the following saturday
        t = datetime.timedelta((12 - pubdate.weekday()) % 7)
        if t.days == 0: # if today is a saturday jump ahead a week
            t=datetime.timedelta(days=7)
        a=Podcast(publication_date=pubdate+t, issue_number=int(r.json()['issue']))
        b=a.issue_ready()
        if a.is_published == True:
            current_issue=a
            put_current_issue_to_db(current_issue,PICKLE_PATH)
            print('[*] Warning: cold start, using econbot {} ({})'.format(current_issue.publication_date,current_issue.issue_number))
            return current_issue

    #
    # if econbot isn't working do a scan
    #
    schedule_day=build_schedule()
    issues=build_issues(schedule_day)
    current_issue=None
    for date,issue in list(zip( schedule_day[:-4:-1], issues[:-4:-1])):
        a=Podcast(publication_date=date, issue_number=issue)
        b=a.issue_ready()
        if a.is_published == True:
            current_issue=a
            print('[*] Warning: Cold start, detected issue {} ({})'.format(current_issue.publication_date,current_issue.issue_number))
            put_current_issue_to_db(current_issue,PICKLE_PATH)
            return current_issue

def get_secrets(secret_dict):
    # secret dict is: { 'filename': 'prefix', 'filename2': 'prefix2' }
    #  each file is a single line and contains the secret prefixed with the prefix and a colon(:),
    #  { '/tmp/mysecret.txt': 'SMTPPASS' }
    #  $ cat /tmp/mysecret.txt
    #  SMTPPASS:sldkgj44rfj
    secrets=[]
    #
    # get the gotify token from the secrets file
    #
    if len(secret_dict)==0:
        return secrets
    for i in secret_dict.keys():
        if not os.path.isfile(i):
            print('[*] Warning: unable to read {}'.format(i))
            secrets.append('SeCrEt')
        else:
            with open(i,'r') as f:
                r=f.readline()
            rs=r.split(':')
            if len(rs)==2 and rs[0]==secret_dict[i]:
                secrets.append(r.split(':')[1].strip())
            else:
                print('[*] Warning: secret file {} missing prefix {}'.format(i,secret_dict[i]))
                secrets.append('SeCrEt')
    return secrets

#
# SQL
#
def insert_zip_info(conn, filename, size, file_count):
    cursor = conn.cursor()
    cursor.execute('''
        REPLACE INTO economist_zip_info (filename, size, file_count)
        VALUES (?, ?, ?)
    ''', (filename, size, file_count))
    conn.commit()

def extract_id3_info(conn, zip_filename, mp3_filename, id3_data):
    cursor = conn.cursor()
    cursor.execute('''
        REPLACE INTO economist_article_info (zip_filename, mp3_filename, artist, album, title, duration, file_size)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (zip_filename, mp3_filename, id3_data['artist'], id3_data['album'], id3_data['title'], id3_data['duration'], id3_data['file_size']))
    conn.commit()

def insert_cover_info(conn, zip_filename, cover_path):
    cursor = conn.cursor()
    cursor.execute('''
        REPLACE INTO economist_issue_covers (zip_filename, cover_path)
        VALUES (?, ?)
    ''', (zip_filename, cover_path))
    conn.commit()

def insert_url(conn, zip_filename, url):
    cursor = conn.cursor()
    cursor.execute('''
        REPLACE INTO economist_urls (zip_filename, url)
        VALUES (?, ?)
    ''', (zip_filename, url))
    conn.commit()

def save_cover_art(cover_data, cover_dir, zip_filename):
    if not os.path.exists(cover_dir):
        os.makedirs(cover_dir)
    cover_art_filename = f"{os.path.splitext(zip_filename)[0]}.jpg"
    cover_art_path = os.path.join(cover_dir, cover_art_filename)
    with open(cover_art_path, 'wb') as img_file:
        img_file.write(cover_data)
    return cover_art_path

def sqldir_scan(pth,conn,current_issue):
    audios=[]
    adir=os.path.join(pth,'audios')
    #cover_found = False
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

            mp3_data = MP3(f, ID3=ID3)
            id3_data = {
                'artist': mp3_data.get('TPE1', [''])[0],
                'album': mp3_data.get('TALB', [''])[0],
                'title': mp3_data.get('TIT2', [''])[0],
                'duration': mp3_data.info.length,
                'file_size': os.path.getsize(f)
            }
            # Check for cover art and stop if found
            #if not cover_found and 'APIC:' in mp3_data:
            #    cover_art = mp3_data['APIC:'].data
            #    cover_art_path = save_cover_art(cover_art, '/tmp', os.path.basename(current_issue.url))
            #    insert_cover_info(conn, os.path.basename(current_issue.url), cover_art_path)
            #    cover_found = True

            extract_id3_info(conn, os.path.basename(current_issue.url), filename, id3_data)

#
# END FUNCTIONS ---------------------------------------------------------------------------
#
