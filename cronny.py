from config import *
from libeconpod import *
import glob
import requests
import sqlite3

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

    print( '[*] Scheduled check ({}) ...'.format(datetime.datetime.now()) )

    print('\t [] Current issue: {0}, (ready={1})'.format( current_issue.publication_date,current_issue.is_published) )
    n=current_issue.next_issue()
    # debug: use this to force an update
    #n=current_issue
    # if its false it may or may not have been checked. If it is True then it definitely has been checked and you don't have to recehck'
    if not n.is_published:
        ready=n.issue_ready()
    print( '\t [] Next issue: {0}, (ready={1})'.format( n.publication_date,n.is_published ) )

    # the next issue is ready!
    if n.is_published:
        try:
            delete_files_in_directory(os.path.join(PODCAST_BASE_PATH,'audios'))
        except:
            print('unable to purge old episodes')
            return

        n.publish(baseUrl,PODCAST_BASE_PATH,JINJA_TEMPLATE_PATH,TEMPLATE_FILE)
        try:
            put_current_issue_to_db(n,PICKLE_PATH)
        except:
            print('error updating DB')

        if GOTIFY_ENABLED:
            gotify_push(gotify_host,gotify_token,'Cron: New episode ({}) is ready!'.format(n.publication_date.strftime("%Y/%m/%d")))
        if SMTP_ENABLED:
            email_push(smtp_user,smtp_pw,EMAIL_NOTIFICATION,'New episode ({}) is ready!'.format(n.publication_date.strftime("%Y/%m/%d")))
        if SQL_ENABLED:
            if os.path.isfile(SQL_DB):
                try:
                    conn = sqlite3.connect(SQL_DB)
                    insert_zip_info(conn, n.url.split('/')[-1], n.totalsize, n.articles)
                    # (re) scan the whole dir; the inner look in audioscan() doesn't have the zip name
                    sqldir_scan(PODCAST_BASE_PATH,conn,n)
                    insert_url(conn, n.url.split('/')[-1], n.url)
                except:
                    print('[*] SQL is unhappy!')
    else: # the next issue is not ready
        if not valid_podcast_available(PODCAST_BASE_PATH): #... but the current issue is broken
            print('[*] Current issue does not appear to be available in {}'.format(PODCAST_BASE_PATH))
            current_issue.publish(baseUrl,PODCAST_BASE_PATH,JINJA_TEMPLATE_PATH,TEMPLATE_FILE)
            # design choice: the current issue will not be written to the db and no announcement will be made.
            # I assume the announcement already happeend and the files got deleted somehow

if __name__ == "__main__":

    # config is no longer here, see config.py

    if not os.path.isfile(os.path.join(os.path.dirname(__file__), 'config.py') ):
        print('[*] Error: unable to read {}'.format( os.path.join(os.path.dirname(__file__), 'config.py')  ))
        sys.exit(2)

    print('[Debug] Base url: {}'.format(baseUrl))

    # Figure out the gotify secret
    GOTIFY_ENABLED=False
    try: gotify_host
    except NameError: gotify_host = None

    try: GOTIFY_TOKEN_SECRET
    except NameError: GOTIFY_TOKEN_SECRET = None

    if gotify_host is not None and GOTIFY_TOKEN_SECRET is not None:
        gotify_host=gotify_host.rstrip('/') # no trailing slash
        thesecrets=get_secrets( {GOTIFY_TOKEN_SECRET:'GOTIFY_TOKEN'} )
        if len(thesecrets) == 0:
            print('[!] Warning: gotify secrets not found. Notifications will not work.')
        else:
            gotify_token=thesecrets[0]
            GOTIFY_ENABLED=True
    else:
        print('[!] Warning: gotify secrets not found. Notifications disabled.')

    # Figure out the smtp secret
    SMTP_ENABLED=False
    try: smtp_user
    except NameError: smtp_user = None

    try: SMTP_SECRET
    except NameError: SMTP_SECRET = None

    try: EMAIL_NOTIFICATION
    except NameError: EMAIL_NOTIFICATION = None

    if smtp_user is not None and SMTP_SECRET is not None and EMAIL_NOTIFICATION is not None:
        thesecrets=get_secrets( {SMTP_SECRET:'RELAY_PASSWORD'})
        if len(thesecrets) == 0:
            print('[!] Warning: smtp secrets not found. Notifications will not work.')
        else:
            smtp_pw=thesecrets[0]
            SMTP_ENABLED=True
    else:
        print('[!] Warning: smtp secrets not found. Notifications disabled.')

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

    # check that SQL is happy

    SQL_ENABLED=False
    try: SQL_DB
    except NameError: SQL_DB = None

    if SQL_DB is not None and len(SQL_DB)>0:
        if os.path.isfile(SQL_DB):
            conn = None
            try:
                conn = sqlite3.connect(SQL_DB)
            except Error as e:
                print(f"[!] Error while connecting to database: {e}")
            if conn:
                for tbl in ['economist_zip_info','economist_article_info','economist_issue_covers','economist_urls']:
                    cursor = conn.cursor()
                    cursor.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{tbl}';")
                    table_exists = cursor.fetchone()
                    if not table_exists:
                        print(f"[!] Table not found in database: {tbl}")
                    else:
                        SQL_ENABLED=True
                conn.close()

    z=Podcast(publication_date=datetime.datetime( 2023,9,30,0,0,0 ), is_published=True, issue_number=9365)
    put_current_issue_to_db(z,PICKLE_PATH)
    #sys.exit(5)

    cron()
