from libeconpod import *
import jinja2

app = Flask(__name__, static_url_path='', static_folder='static', template_folder='templates')
app.config.from_object(Config())

scheduler = APScheduler()
# Shut down the scheduler when exiting the app
atexit.register(lambda: scheduler.shutdown())

@scheduler.task('interval', id='cron', hours=1, misfire_grace_time=900)
def cron():
    try:
        current_issue=get_current_issue_from_db()
    except:
        print('unable to load current issue from DB')
    if not isinstance(current_issue, Podcast):
        print('cron got bad data')

    print( '[*] Scheduled check ({}) ...'.format(datetime.datetime.now()) )

    print('\t [] Current issue: {0}, (ready={1})'.format( current_issue.publication_date,current_issue.is_published) )
    n=next_issue(current_issue)
    # if its false it may or may not have been checked. If it is True then it definitely has been checked and you don't have to recehck'
    if not n.is_published:
        ready=n.issue_ready()
    print( '\t [] Next issue: {0}, (ready={1})'.format( n.publication_date,ready ) )

    if n.is_published:
        put_current_issue_to_db(n)
        delete_files_in_directory(os.path.join(PODCAST_BASE_PATH,'audios'))
        #os.system('rm -rf /app/static/podcast1/audios/*') # assume unix host
        dltime=dl_issue(n.url) # download and extract the issue
        # I don't get how the main flask app has the context of podcasts but this seems to work?'
        counter, sizecounter, podcasts = build_json(base_podcasts)

        filesize_mb=sizecounter/1024/1024
        print('[*] Downloaded {:.1f}MB ({} files) in {:.1f}s ({:.1f} MB/s)'.format( filesize_mb , counter, dltime , filesize_mb/dltime  ))
        #shutil.copyfile(LOGO_PATH, os.path.join(PODCAST_BASE_PATH,os.path.split(LOGO_PATH)[-1]))
        gotify_push('New episode ({}) is ready!'.format(n.publication_date.strftime("%Y/%m/%d")))

@app.route('/<podcast>/rss')
def rss(podcast):
    # note that the <podcast> arguement is ignored, but allowed for backward compatibility
    template =  render_template('base.xml', podcast=podcasts['podcast'], baseUrl=podcasts['baseUrl'])
    response = make_response(template)
    response.headers['Content-Type'] = 'application/rss+xml'
    return response

#
# to manually check a current_issue.pkl file:
#   from libeconpod import *
#   current_issue=get_current_issue_from_db('/tmp/current_issue.pkl')
#   print('Date: {}\nIssue: {}\nURL: {}'.format(current_issue.publication_date.date(),current_issue.issue_number,current_issue.url))
#


#if __name__ == "__main__":

scheduler.init_app(app)

current_issue = init_current_issue()
# DEBUG force warm start with old issue
#current_issue=Podcast(publication_date=datetime.datetime( 2023,5,13,0,0,0 ), is_published=True, issue_number=9346)
put_current_issue_to_db(current_issue)
#scheduler.add_job(func=cron, trigger="interval", seconds=30) # hours=1
scheduler.start()

dltime=dl_issue(current_issue.url) # download and extract the issue
counter, sizecounter, podcasts = build_json(base_podcasts)

# write a copy of the rss feed to a file
templateLoader = jinja2.FileSystemLoader(searchpath="./templates/")
templateEnv = jinja2.Environment(loader=templateLoader)
TEMPLATE_FILE = "base.xml"
template = templateEnv.get_template(TEMPLATE_FILE)
rendered = template.render(podcast=podcasts['podcast'], baseUrl=podcasts['baseUrl'])
with open(os.path.join(PODCAST_BASE_PATH,'feed'),'w') as f:
    f.write(rendered)

filesize_mb=sizecounter/1024/1024
print('[*] Downloaded {:.1f}MB ({} files) in {:.1f}s ({:.1f} MB/s)'.format( filesize_mb , counter, dltime , filesize_mb/dltime  ))
#shutil.copyfile(LOGO_PATH, os.path.join(PODCAST_BASE_PATH,os.path.split(LOGO_PATH)[-1]))
gotify_push('New episode ({}) is ready!'.format(current_issue.publication_date.strftime("%Y/%m/%d")))

#app.run()
