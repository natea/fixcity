"""
proof-of-concept twitter bot
"""

from datetime import datetime
from django.conf import settings
from django.core.mail import send_mail
from django.core.management.base import BaseCommand
from django.utils import simplejson as json
from fixcity.bmabr.fixcity_bitly import shorten_url
from utils import SERVER_TEMP_FAILURE, SERVER_ERROR
import httplib2
import logging
import pickle
import socket
import tweepy


logger = logging.getLogger('tweeter')

http = httplib2.Http()


class TwitterFetcher(object):

    def __init__(self, twitter_api, username, notifier):
        self.twitter_api = twitter_api
        self.username = username
        self.notifier = notifier
        
    def parse(self, tweet):
        msg = tweet.text.replace('@' + self.username, '')
        try:
            location, title = msg.split('#bikerack', 1)
            return {'title': title.strip(),
                    'address': location.strip(),
                    'date': tweet.created_at.isoformat(' '),
                    'user': tweet.user.screen_name,
                    'tweetid': tweet.id}
        except ValueError:
            logger.warn("couldn't parse tweet %r\n" % msg)
            return None

    def get_tweets(self, since_id=None):
        """
        Try to get all our mentions (and maybe direct messages?).
        Subject to Twitter's pagination limits,
        http://apiwiki.twitter.com/Things-Every-Developer-Should-Know#6Therearepaginationlimits
        """
        tweets = []
        max_pages = 16
        max_per_page = 200
        for tweet_func in (self.twitter_api.mentions,):
            # We're not doing direct messages for now.
            for page in range(1, max_pages + 1):
                try:
                    if since_id is not None:
                        more_tweets = tweet_func(count=max_per_page, page=page, since_id=since_id)
                    else:
                        more_tweets = tweet_func(count=max_per_page, page=page)
                except (socket.error, tweepy.error.TweepError):
                    # 50x errors from Twitter are not interesting.
                    # Just give up and hope Twitter's back by the next time
                    # we run.
                    more_tweets = []
                tweets += more_tweets
                if len(more_tweets) < max_per_page:
                    break
        tweets.sort(key=lambda t: t.id, reverse=True)
        return tweets


class RackMaker(object):

    def __init__(self, config, api, notifier):
        self.url = config.RACK_POSTING_URL
        self.username = config.TWITTER_USER
        self.password = config.TWITTER_PASSWORD
        self.twitter_api = api
        self.status_file_path = config.TWITTER_STATUS_PATH
        self.notifier = notifier
        self.error_adapter = ErrorAdapter()

    def load_last_status(self, recent_only):
        last_processed_id = None
        if not recent_only:
            return last_processed_id
        try:
            statusfile = open(self.status_file_path, 'r')
            status = pickle.load(statusfile)
            last_processed_id = status['last_processed_id']
            statusfile.close()
        except (IOError, EOFError):
            pass
        return last_processed_id

    def save_last_status(self, last_processed_id):
        statusfile = open(self.status_file_path, 'w')
        pickle.dump({'last_processed_id': last_processed_id}, statusfile)
        statusfile.close()
        
        
    def main(self, recent_only=True):
        last_processed_id = self.load_last_status(recent_only)
        try:
            limit_status = self.twitter_api.rate_limit_status()
            if limit_status['remaining_hits'] <= 0:
                raise Exception(
                    "We went over our twitter API rate limit. Resets at: %s"
                    % limit_status['reset_time'])
        except tweepy.error.TweepError:
            # Twitter is feeling sad again.
            # Let's bail out and hope they're back soon.
            return
        twit = TwitterFetcher(self.twitter_api, self.username, self.notifier)

        all_tweets = twit.get_tweets(last_processed_id)
        for tweet in reversed(all_tweets):
            parsed = twit.parse(tweet)

            user = tweet.user.screen_name
            success_info = None
            if parsed:
                submit_result = self.submit(**parsed)
            else:
                self.notifier.bounce(user, self.general_error_message)
            # XXX We should lock the status file in case this script
            # ever takes so long that it overlaps with the next
            # run. Or something.
            if submit_result is SERVER_TEMP_FAILURE:
                continue
            elif submit_result is SERVER_ERROR:
                # No point retrying.
                self.save_last_status(tweet.id)
            else:
                self.save_last_status(tweet.id)
                    
            # TODO: batch-notification of success to cut down on posts:
            # if success, maintain a queue of recently successful posts,
            # and every N minutes:
            # - start with a template success message like
            # 'thanks for rack suggestions, see http://bit.ly/XXX'
            # - while chars < 140:
            # -   pop a suggestion from the queue
            # -   prepend @username to the message
            # -   append &id=X to a url like http://fixcity.org/racks/by_id?...
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


    def submit(self, title, address, user, date, tweetid):
        
        url = self.url
        description = ''
        data = dict(source_type='twitter',
                    twitter_user=user,
                    twitter_id=tweetid,
                    title=title,
                    description=description,
                    date=date,
                    address=address,
                    geocoded=0,  # Do server-side geocoding.
                    )
        from utils import FixcityHttp
        result = FixcityHttp(self.notifier, self.error_adapter).submit(data)
        return result


class Notifier(object):

    def __init__(self, twitter_api):
        self.twitter_api = twitter_api

    def bounce(self, user, message, notify_admin='', notify_admin_body=''):
        """Bounce a message, with additional info for explanation.

        If the notify_admin string is non-empty, the site admin will
        be notified, with that string appended to the subject.
        If notify_admin_body is non-empty, it will be added to the body
        sent to the admin.
        """
        if message is not None:
            message = '@%s %s' % (user, message)
            message = message[:140]
            try:
                self.twitter_api.update_status(message) # XXX add in_reply_to_id?
            except tweepy.error.TweepError:
                pass

        if notify_admin:
            # XXX include the original tweet?
            admin_subject = 'FixCity tweeter bounce! %s' % notify_admin
            admin_body = 'Bouncing to: %s\n' % user
            admin_body += 'Bounce message: %r\n' % message
            admin_body += 'Time: %s\n' % datetime.now().isoformat(' ')
            if notify_admin_body:
                admin_body += 'Additional info:\n'
                admin_body += notify_admin_body
            self.notify_admin(admin_subject, admin_body)


    @staticmethod
    def notify_admin(subject, body):
        admin_email = settings.SERVICE_FAILURE_EMAIL
        from_addr = 'racks@fixcity.org'
        send_mail(subject, body, from_addr, [admin_email], fail_silently=False)
        # person receiving cron messages will get stdout
        logger.info(body)

    def on_submit_success(self, vars):
        user = vars['rack_user']
        shortened_url = shorten_url(vars['rack_url']) 
        self.bounce(
            user,
            "Thank you! Here's the rack request %s; now you can register "
            "to verify your request "
            % shortened_url)


class ErrorAdapter(object):

    general_error_message = ("Thanks, but something went wrong! Check the "
                             "format e.g. http://bit.ly/76pXSi and try again "
                             "or @ us w/questions.")
    
    def validation_errors(self, errordict):
        """Convert the form field names in the errors dict into things
        that are meaningful via the twitter workflow, and adjust error
        messages appropriately too.
        """
        return self.general_error_message

    server_error_retry = None  # don't bother the user, we'll just retry.

    server_error_permanent = general_error_message


def api_factory(settings):
     auth = tweepy.BasicAuthHandler(settings.TWITTER_USER,
                                    settings.TWITTER_PASSWORD)
     api = tweepy.API(auth)
     return api


class Command(BaseCommand):

    def handle(self, *args, **options):
        api = api_factory(settings)
        notifier = Notifier(api)
        builder = RackMaker(settings, api, notifier)
        # XXX handle unexpected errors
        builder.main(recent_only=True)
