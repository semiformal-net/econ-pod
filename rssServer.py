from flask import Flask, render_template, make_response, send_from_directory, send_file, url_for
import json
import os
import datetime

app = Flask(__name__, static_url_path='', static_folder='static', template_folder='templates')

#
# 1. We build a json called podcasts which contains info about the files
#
podcasts={
"baseUrl" : "http://192.168.2.245:5500/",
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
# 2. to complete the podcasts json we scan the static/podcast1/audios/ directory and gather info about each mp3 file
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

print('Processed {} file of {}MB size'.format( counter,sizecounter/1024/1024  ))

# this file is not used, but written for lols
with open("podcasts.json", "w") as outfile:
    json.dump(podcasts, outfile)

#
# 3. finally we serve the rss using a template
#

@app.route('/<podcast>/rss')
def rss(podcast):
    template =  render_template('base.xml', podcast=podcasts['podcasts'][podcast], baseUrl=podcasts['baseUrl'])
    response = make_response(template)
    response.headers['Content-Type'] = 'application/rss+xml'
    return response
