"""
proof-of-concept twitter bot
"""

from datetime import datetime
from django.conf import settings
from django.core.mail import send_mail
from django.core.management.base import BaseCommand
from fixcity.bmabr.fixcity_bitly import shorten_url
import httplib2
import logging
import pickle
import socket
import tweepy


logger = logging.getLogger('tweeter')

http = httplib2.Http()

SUCCESS = 'success'
PARSE_ERROR = 'parse error'
SERVER_ERROR = 'server error'
SERVER_TEMP_FAILURE = 'server temp failure'

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
        # XXX We should lock the status file in case this script
        # ever takes so long that it overlaps with the next
        # run. Or something.
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
                self.notifier.on_parse_error(user)            
            #     self.save_last_status(tweet.id)
            #     continue
            # if submit_result is SERVER_TEMP_FAILURE:
            #     # Leave it in the queue for the next run.
            #     self.notifier.on_server_failure(user)
            #     continue
            # elif submit_result is SERVER_ERROR:
            #     # No point retrying.
            #     self.notifier.on_server_error(user)
            # else:
            #     self.notifier.on_submit_success(user) # XXX FixcityHttp does this already

            if self.notifier.last_status in (SERVER_ERROR, SUCCESS):
                self.save_last_status(tweet.id)


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
        result = FixcityHttp(self.notifier, ErrorAdapter()).submit(data)
        return result


class Notifier(object):

    def __init__(self, twitter_api):
        self.twitter_api = twitter_api
        self.last_status = None

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
        # XXX feels like the expected data should be cleaner.
        self.last_status = SUCCESS
        user = vars['data']['twitter_user']
        shortened_url = shorten_url(vars['rack_url'])
        self.bounce(
            user,
            "Thank you! Here's the rack request %s; now you can register "
            "to verify your request "
            % shortened_url)

    def on_parse_error(self, user):
        self.last_status = PARSE_ERROR
        return self.bounce(user, ErrorAdapter().general_error_message)

    def on_server_error(self, user):
        # XXX make this part of the API and have FixcityHttp call it?
        self.last_status = SERVER_ERROR
        return self.bounce(user, ErrorAdapter().server_error_permanent)

    def on_server_temp_failure(self, user):
        # Don't bother the user, we'll just retry.
        self.last_status = SERVER_TEMP_FAILURE


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

    server_error_permanent = ("Thanks, but something went wrong! "
                              "Server error on our side, we'll look into it. "
                              "Retrying probably wouldn't help.")


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
