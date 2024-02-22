from config import *
from libeconpod import *
import glob
import requests

def cron():

    current_issue=get_current_issue_from_db(PICKLE_PATH)

    if current_issue is None:
        # This is the cold start logic. If you are unable to warm start with a valid issue.

        current_issue=cold_start(PICKLE_PATH)
        if not isinstance(current_issue, Podcast):
            print('[!] Error: no state found and unable to cold start')
            return

    elif not isinstance(current_issue, Podcast):
        print('cron got bad data')
        return
    else:
        print('Found issue {} ({}) in database, resuming'.format(current_issue.publication_date,current_issue.issue_number))

    try:
        r=requests.get('https://econpod-23523.ue.r.appspot.com') #econissuebot (Beep!)
        if r.json()['success']:
            print( '[DEBUG] econissuebot reports: {} ({})'.format(r.json()['issue'], r.json()['published_date']))
        else:
            print( '[DEBUG] econissuebot failed with: {}'.format(r.json()['error']))
    except:
        print('[DEBUG] econissuebot failed')

    print( '[*] Scheduled check ({}) ...'.format(datetime.datetime.now()) )

    print('\t [] Current issue: {0}, (ready={1})'.format( current_issue.publication_date,current_issue.is_published) )
    n=next_issue(current_issue)
    # debug: use this to force an update
    # n=current_issue
    # if its false it may or may not have been checked. If it is True then it definitely has been checked and you don't have to recehck'
    if not n.is_published:
        ready=n.issue_ready()
    print( '\t [] Next issue: {0}, (ready={1})'.format( n.publication_date,n.is_published ) )

    if n.is_published:
        publish(baseUrl,n,PODCAST_BASE_PATH,JINJA_TEMPLATE_PATH,TEMPLATE_FILE)
        gotify_push(gotify_host,gotify_token,'Cron: New episode ({}) is ready!'.format(n.publication_date.strftime("%Y/%m/%d")))
        if len(EMAIL_NOTIFICATION)>0:
            email_push(smtp_user,smtp_pw,EMAIL_NOTIFICATION,'New episode ({}) is ready!'.format(n.publication_date.strftime("%Y/%m/%d")))
        try:
            put_current_issue_to_db(n,PICKLE_PATH)
        except:
            print('error updating DB')
            return
    else:
        if not valid_podcast_available(PODCAST_BASE_PATH):
            print('[*] Current issue does not appear to be available in {}'.format(PODCAST_BASE_PATH))
            publish(baseUrl,current_issue,PODCAST_BASE_PATH,JINJA_TEMPLATE_PATH,TEMPLATE_FILE)

if __name__ == "__main__":

    # config is no longer here, see config.py

    if not os.path.isfile('./config.py'):
        print('[*] Error: unable to read {}'.format('config.py'))
        sys.exit(2)

    print('[Debug] Base url: {}'.format(baseUrl))

    gotify_host=gotify_host.rstrip('/') # no trailing slash

    thesecrets=get_secrets( {GOTIFY_TOKEN_SECRET:'GOTIFY_TOKEN', SMTP_SECRET:'RELAY_PASSWORD'} )
    if len(thesecrets) == 0:
        print('[!] Warning: no valid secrets found. Notifications will not work.')
    else:
        gotify_token=thesecrets[0]
        smtp_pw=thesecrets[1]

    #
    #
    # python won't write to a path that doesn't exist (which will fail on first rwrite)
    #
    PICKLE_DIRNAME = os.path.dirname(PICKLE_PATH)
    if not os.path.isdir(PICKLE_DIRNAME):
        os.makedirs(PICKLE_DIRNAME)

    if not os.path.isdir(PODCAST_BASE_PATH):
        os.makedirs(PODCAST_BASE_PATH)

    if not os.path.isdir(os.path.join(PODCAST_BASE_PATH,'audios')):
        os.makedirs(os.path.join(PODCAST_BASE_PATH,'audios'))

    #
    # Need templates/base.xml
    #

    if not os.path.isfile(os.path.join(JINJA_TEMPLATE_PATH,TEMPLATE_FILE)):
        print('[*] Error: template file {} does not exist'.format(os.path.join(JINJA_TEMPLATE_PATH,TEMPLATE_FILE)))
        sys.exit(2)

    if not os.access(os.path.join(JINJA_TEMPLATE_PATH,TEMPLATE_FILE), os.R_OK):
        print('[*] Error: template file {} cannot be read'.format(os.path.join(JINJA_TEMPLATE_PATH,TEMPLATE_FILE)))
        sys.exit(2)

    print('pickle path',PICKLE_PATH)


    #z=Podcast(publication_date=datetime.datetime( 2023,9,30,0,0,0 ), is_published=True, issue_number=9365)
    #put_current_issue_to_db(z,PICKLE_PATH)
    #sys.exit(5)

    cron()
