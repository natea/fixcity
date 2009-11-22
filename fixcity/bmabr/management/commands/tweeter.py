"""
proof-of-concept twitter bot
"""

from datetime import datetime
from django.conf import settings
from django.core.mail import send_mail
from django.core.management.base import BaseCommand
from django.utils import simplejson as json
import httplib2
import pickle
import socket
import sys
import time
import tweepy


http = httplib2.Http()


class TwitterFetcher(object):

    def __init__(self, twitter_api, username):
        self.twitter_api = twitter_api
        self.username = username
        
    def parse(self, tweet):
        msg = tweet.text.replace('@' + self.username, '')
        # XXX what's the actual tweet format going to look like?
        try:
            location, title = msg.split('#bikerack', 1)
            return title.strip(), location.strip()
        except ValueError:
            sys.stderr.write("couldn't parse tweet %r\n" % msg)
            return None, None

    def get_tweets(self, since_id=None):
        """
        Try to get all our mentions and direct messages.
        Subject to Twitter's pagination limits,
        http://apiwiki.twitter.com/Things-Every-Developer-Should-Know#6Therearepaginationlimits
        """
        tweets = []
        max_pages = 16
        max_per_page = 200
        for tweet_func in (self.twitter_api.mentions,):
            # XXX not doing direct messages for now.
            for page in range(1, max_pages + 1):
                if since_id is not None:
                    more_tweets = tweet_func(count=max_per_page, page=page, since_id=since_id)
                else:
                    more_tweets = tweet_func(count=max_per_page, page=page)
                tweets += more_tweets
                if len(more_tweets) < max_per_page:
                    break
        tweets.sort(key=lambda t: t.id, reverse=True)
        return tweets


class RackBuilder(object):

    def __init__(self, config, api):
        self.url = config.RACK_POSTING_URL
        self.username = config.TWITTER_USER
        self.password = config.TWITTER_PASSWORD
        self.twitter_api = api
        self.status_file_path = config.TWITTER_STATUS_PATH
    
    def main(self, recent_only=True):
        last_processed_id = None
        if recent_only:
            try:
                statusfile = open(self.status_file_path, 'r')
                status = pickle.load(statusfile)
                last_processed_id = status['last_processed_id']
                statusfile.close()
            except (IOError, EOFError):
                pass
        limit_status = self.twitter_api.rate_limit_status()
        if limit_status['remaining_hits'] <= 0:
            raise Exception(
                "We went over our twitter API rate limit. Resets at: %s"
                % limit_status['reset_time'])
        twit = TwitterFetcher(self.twitter_api, self.username)

        all_tweets = twit.get_tweets(last_processed_id)
        for tweet in reversed(all_tweets):
            title, location = twit.parse(tweet)
            statusfile = open(self.status_file_path, 'w')
            # XXX don't want to do this if there's a socket error,
            # but we do if there's any other kind of error.
            pickle.dump({'last_processed_id': tweet.id}, statusfile)
            statusfile.close()
            if title and location:
                self.new_rack(title, location, tweet.user.screen_name, tweet.id)

            # TODO: batch-notification of success to cut down on posts:
            # if success, maintain a queue of recently successful posts,
            # and every N minutes:
            # - start with a template success message like
            # 'thanks for rack suggestions, see http://bit.ly/XXX'
            # - while chars < 140:
            # -   pop a suggestion from the queue
            # -   prepend @username to the message
            # -   append &id=X to a url like http://fixcity.org/rack/by_id?...
            # -   ... this would be a new view that shows all the id'd racks.
            # - build a bit.ly version of the URL and insert it in the message
            # - tweet the message
            # - repeat until we're out of users, or hit our API limit
            # ... or something.

            # XXX Also batch error messages? We might get a bunch if the server
            # goes down and cron keeps running this script...

            # XXX Or maybe we need to keep some state about tweets
            # we couldn't process in case we want to retry them
            # and notify user if they eventually succeed?


    def new_rack(self, title, address, user, tweetid):
        url = self.url
        # XXX UGH, copy-pasted from handle_mailin.py. Refactoring time!
        description = ''
        # We don't bother with microsecond precision because
        # Django datetime fields can't parse it anyway.
        now = datetime.fromtimestamp(int(time.time()))
        data = dict(source_type='twitter',
                    twitter_user=user,
                    twitter_id=tweetid,
                    title=title,
                    description=description,
                    date=now.isoformat(' '),  # XXX use the tweet's own date?
                    address=address,
                    geocoded=0,  # Do server-side geocoding.
                    )

        jsondata = json.dumps(data)
        headers = {'Content-type': 'application/json'}

        error_subject = "Unsuccessful bikerack request"
        try:
            response, content = http.request(url, 'POST',
                                             headers=headers,
                                             body=jsondata)
        except socket.error:
            _notify_admin('Server down??',
                          'Could not post some tweets, fixcity.org dead?')
            sys.exit(1)

        if response.status >= 500:
            # XXX give a URL to a help page w/ more info?
            # Maybe even a private URL to a page w/ this user's exact errors?
            err_msg = (
                "server error while handling your bike rack. Sorry!"
                )
            self.bounce(
                user, err_msg,
                notify_admin='fixcity: twitter: 500 Server error',
                notify_admin_body=content)
            return

        result = json.loads(content)
        if result.has_key('errors'):

            err_msg = (
                "Thanks for your rack suggestion, "
                "but we couldn't process your tweet. "
                "Check format and try again?"
                )
    ##         errors = adapt_errors(result['errors'])
    ##         for k, v in sorted(errors.items()):
    ##             err_msg += "%s: %s\n" % (k, '; '.join(v))

            self.bounce(user, err_msg)
            return
        else:
            self.bounce(user, "thanks! your rack request is at %s%s" %
                        (self.url, result['rack']))


    def bounce(self, user, message, notify_admin='', notify_admin_body=''):
        message = '@%s %s' % (user, message)[:140]
        self.twitter_api.update_status(message) # XXX add in_reply_to_id?

        if notify_admin:
            # XXX include the original tweet?
            admin_subject = 'FixCity tweeter bounce! %s' % notify_admin
            admin_body = 'Bouncing to: %s\n' % user
            admin_body += 'Bounce message: %r\n' % message
            admin_body += 'Time: %s\n' % datetime.now().isoformat(' ')
            if notify_admin_body:
                admin_body += 'Additional info:\n'
                admin_body += notify_admin_body
            _notify_admin(admin_subject, admin_body)


def _notify_admin(subject, body):
    admin_email = settings.SERVICE_FAILURE_EMAIL
    from_addr = 'racks@fixcity.org'
    send_mail(subject, body, from_addr, [admin_email], fail_silently=False)
    # person receiving cron messages will get stdout
    print body

def adapt_errors(adict):
    # XXX TODO
    return adict



def api_factory(settings):
     auth = tweepy.BasicAuthHandler(settings.TWITTER_USER,
                                    settings.TWITTER_PASSWORD)
     api = tweepy.API(auth)
     return api


class Command(BaseCommand):

    def handle(self, *args, **options):
        api = api_factory(settings)
        builder = RackBuilder(settings, api)
        builder.main(recent_only=True)

