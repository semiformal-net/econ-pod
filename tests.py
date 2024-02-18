import pickle
import sys
import datetime
import os
import glob
import jinja2
import random

PICKLE_PATH='/tmp/current_issue.pkl'


from libeconpod import Podcast
# an arbitrary (but valid) issue
current_issue_pickle_binary=b'\x80\x04\x95+\x01\x00\x00\x00\x00\x00\x00\x8c\nlibeconpod\x94\x8c\x07Podcast\x94\x93\x94)\x81\x94}\x94(\x8c\x03url\x94\x8c\x7fhttp://audiocdn.economist.com/sites/default/files/AudioArchive/2023/20231014/Issue_9367_20231014_The_Economist_Full_edition.zip\x94\x8c\x10publication_date\x94\x8c\x1epandas._libs.tslibs.timestamps\x94\x8c\x13_unpickle_timestamp\x94\x93\x94(\x8a\x08\x00\x00\x04*>\xd0\x8d\x17NNK\nt\x94R\x94\x8c\x0cis_published\x94\x88\x8c\x0cissue_number\x94M\x97$ub.'

current_issue=pickle.loads(current_issue_pickle_binary)
if not isinstance(current_issue, Podcast):
    print('[!] Error: blob is not a Podcast instance')
    sys.exit(1)

#
#
if not os.path.isfile('config.py'):
    print('[*] Error: unable to read {}'.format('config.py'))
    sys.exit(2)
from config import GOTIFY_TOKEN_SECRET,SMTP_SECRET

#
#
from libeconpod import get_secrets
thesecrets=get_secrets( {GOTIFY_TOKEN_SECRET:'GOTIFY_TOKEN', SMTP_SECRET:'RELAY_PASSWORD'} )
gotify_token=thesecrets[0]
smtp_pw=thesecrets[1]
print('[!] DEBUG: secrets:  ',thesecrets)

#
#
from libeconpod import gotify_push

gotify_push(gotify_host,gotify_token,'Econpod (cron) test: {}'.format(current_issue.publication_date.strftime("%Y/%m/%d")))
#
#
try:
    z=Podcast(publication_date=datetime.datetime( 2023,9,30,0,0,0 ), is_published=True, issue_number=9365)
except:
    print('[!] Error: class malfunction, Podcast()')

#
#
from libeconpod import put_current_issue_to_db
try:
    put_current_issue_to_db(current_issue,PICKLE_PATH)
except:
    print('[!] Error: cant save db')

#
#
from libeconpod import get_current_issue_from_db
try:
    c=get_current_issue_from_db(PICKLE_PATH)
except:
    print('[!] Error: cant fetch db')
if not current_issue.__dict__ == c.__dict__:
    print('[!] Error: state doesnt match expectation')


#
#
from libeconpod import next_issue
a=next_issue(current_issue)
print('[DEBUG] The next issue is {}'.format(a.publication_date))
#if not a.publication_date == datetime.datetime( 2023,10,21,0,0,0 ):
#    print('[!] Error next issue gave wrong date', a.publication_date)

#
#
from libeconpod import build_schedule,build_issues,cold_start
try:
    cold_issue=cold_start('/tmp/current_issue_brrrr.pkl')
except:
    print('[!] Error in cold start')
if not os.path.isfile('/tmp/current_issue_brrrr.pkl'):
    print('[!] Error: cold start didt make a file')

print('[DEBUG] The cold start found issue: {}'.format(cold_issue.publication_date))


try:
    c=get_current_issue_from_db(PICKLE_PATH)
except:
    print('[!] Error: cant fetch cod start from db')

if not isinstance(c, Podcast):
    print('[!] Error: cold start loaded but it isnt a podcast obj')

#
#
from libeconpod import dl_issue
# python won't write to a path that doesn't exist (which will fail on first rwrite)
#
if not os.path.isdir('/tmp/audios'):
    os.makedirs('/tmp/audios')
try:
    dl_issue(current_issue.url,'/tmp')
except:
    print('[!] Error: dlissue error')

if not os.path.isdir(os.path.join('/tmp','audios')):
    print('[!] Error: unzip didnt work')

mp3counter = len(glob.glob1(os.path.join('/tmp/','audios'),"*.mp3"))
if mp3counter<5:
    print('[!] Error: unzip didnt work. no mp3s?')

#
#
from libeconpod import valid_podcast_available

randomdir=os.path.join('/tmp',str(random.randint(0,1e6)))

if not os.path.isdir(randomdir):
    os.makedirs(randomdir)
else:
    print('[!] Error: randomdir exists!: {}'.format(randomdir))

if valid_podcast_available(randomdir):
    print('[!] Error: {} does contains a valid podcast (and should not)'.format(randomdir))

#
#
from libeconpod import audiodir_scan
try:
    counter, sizecounter, audios=audiodir_scan('/tmp')
    current_issue.articles=counter
    current_issue.totalsize=sizecounter
except:
    print('[!] Error: audio scandir failed')
#
#
from libeconpod import build_json, base_podcasts
try:
    podcasts = build_json('http://localhost',audios)
except:
    print('[!] Error: failed to build json')
# we expect ./templates/base.xml to contain jinja template for rss
templateLoader = jinja2.FileSystemLoader(searchpath='./templates')
templateEnv = jinja2.Environment(loader=templateLoader)
template = templateEnv.get_template('base.xml')
rendered = template.render(podcast=podcasts['podcast'], baseUrl=podcasts['baseUrl'])
with open(os.path.join('/tmp','feed'),'w') as f:
    f.write(rendered)
print('wrote /tmp/feed')

#
#
from libeconpod import publish
# python won't write to a path that doesn't exist (which will fail on first rwrite)
#
if not os.path.isdir('/tmp/testeco'):
    os.makedirs('/tmp/testeco')

if not valid_podcast_available('/tmp'):
    print('[!] Error: /tmp does not contain a valid podcast')

# python won't write to a path that doesn't exist (which will fail on first rwrite)
#
if not os.path.isdir('/tmp/testeco/audios'):
    os.makedirs('/tmp/testeco/audios')
try:
    publish('http://localhost',current_issue,'/tmp/testeco','/home/pedwards/econpod-cron/templates/','base.xml')
except:
    print('[!] Error: publish failed')

print(current_issue)
