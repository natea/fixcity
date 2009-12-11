
# XXX I feel kinda icky importing settings during test
from django.conf import settings

from django.contrib.gis.geos.point import Point
from django.core.cache import cache        

from django.utils import simplejson as json

from django.test import TestCase

from fixcity.bmabr.management.commands import tweeter
from fixcity.bmabr.views import SRID
from fixcity.bmabr.views import _preprocess_rack_form

import lxml.objectify

import datetime
import mock
import unittest

# Stupid monkeypatch to enable Mock to patch open().  It doesn't like
# patching __builtins__ for some reason.
#tweeter.open = __builtins__.open

def clear_cache():
    for key in cache._expire_info.keys():
        cache.delete(key)

class TestSourceFactory(unittest.TestCase):

    def test_existing_source(self):
        from fixcity.bmabr.models import Source, TwitterSource
        from fixcity.bmabr.views import source_factory
        existing = Source()
        existing.name = 'misc source'
        existing.save()
        dupe = source_factory({'source': existing.id})
        self.assertEqual(dupe, existing)

        # It should work also with subclasses of Source...
        twit = TwitterSource(status_id=12345, name='twitter')
        twit.save()
        self.assertEqual(twit, source_factory({'source': twit.id}))
        

    def test_twitter_source(self):
        from fixcity.bmabr.views import source_factory
        twit = source_factory({'source_type': 'twitter',
                               'twitter_user': 'bob',
                               'twitter_id': 123})
        self.assertEqual(twit.user, 'bob')
        self.assertEqual(twit.status_id, 123)
        self.assertEqual(twit.get_absolute_url(), 'http://twitter.com/bob/123')

    def test_unknown_source(self):
        from fixcity.bmabr.views import source_factory
        source = source_factory({'source_type': 'anything else'})
        self.assertEqual(source, None)


class TestUtilFunctions(unittest.TestCase):

    def setUp(self):
        clear_cache()
        super(TestUtilFunctions, self).setUp()
        
    def tearDown(self):
        clear_cache()
        super(TestUtilFunctions, self).tearDown()

    def test_api_factory(self):
        import tweepy
        from fixcity.bmabr.management.commands.tweeter import api_factory
        api = api_factory(settings)
        self.assert_(isinstance(api, tweepy.API))
                     
    def test_preprocess_rack_form__noop(self):
        orig_data = {'geocoded': '1'}
        data = orig_data.copy()
        _preprocess_rack_form(data)
        self.assertEqual(data, orig_data)

    @mock.patch('geopy.geocoders.Google.geocode')
    def test_preprocess_rack_form__address_but_no_matching_user(self,
                                                                mock_geocode):
        address = '148 Lafayette St, New York, NY'
        mock_geocode.return_value = [(address, (20, 40))]
        data = {'geocoded': '0', 'email': 'foo@bar.com', 'address': address}
        _preprocess_rack_form(data)
        self.failIf(data.has_key('user'))
        self.assertEqual(data['location'],
                         'POINT (40.0000000000000000 20.0000000000000000)')

    @mock.patch('geopy.geocoders.Google.geocode')
    def test_preprocess_rack_form__no_location(self, mock_geocode):
        address = '148 Lafayette St, New York, NY'
        mock_geocode.return_value = []
        data = {'geocoded': '0', 'address': address}
        _preprocess_rack_form(data)
        self.assertEqual(data['location'], u'')

    def test_preprocess_rack_form__with_user(self):
        from fixcity.bmabr.views import _preprocess_rack_form
        data = {'geocoded': '1', 'email': 'foo@bar.com'}
        from django.contrib.auth.models import User
        bob = User(username='bob', email='foo@bar.com')
        bob.save()
        _preprocess_rack_form(data)
        self.assertEqual(data['user'], 'bob')

        
    def test_newrack_no_data(self):
        from fixcity.bmabr.views import _newrack
        from fixcity.bmabr.models import NEED_SOURCE_OR_EMAIL
        result = _newrack({}, {})
        self.failUnless(result.has_key('errors'))
        self.assertEqual(result['errors']['title'],
                         [u'This field is required.'])
        self.assertEqual(result['errors']['address'],
                         [u'This field is required.'])
        self.assertEqual(result['errors']['date'],
                         [u'This field is required.'])
        self.assertEqual(result['errors']['__all__'], [NEED_SOURCE_OR_EMAIL])
        self.assertEqual(result['rack'], None)

    def test_newrack_with_email_but_no_source(self):
        from fixcity.bmabr.views import _newrack
        result = _newrack({'email': 'joe@blow.com'}, {})
        self.assertEqual(result['errors'].get('email'), None)
        self.assertEqual(result['errors'].get('__all__'), None)
        self.assertEqual(result['errors'].get('source'), None)

    def test_newrack_with_bad_source_but_no_email(self):
        from fixcity.bmabr.views import _newrack
        from fixcity.bmabr.models import NEED_SOURCE_OR_EMAIL
        from fixcity.bmabr.models import NEED_LOGGEDIN_OR_EMAIL
        result = _newrack({'source': 999999999}, {})
        self.assertEqual(
            result['errors'].get('source'),
            [u'Select a valid choice. That choice is not one of the available choices.'])
        self.assertEqual(result['errors'].get('email'), [NEED_LOGGEDIN_OR_EMAIL])
        self.assertEqual(result['errors'].get('__all__'), [NEED_SOURCE_OR_EMAIL])

    def test_newrack_working(self):
        from fixcity.bmabr.views import _newrack
        from fixcity.bmabr.models import Source
        source = Source()
        source.name = 'unknown source type'
        source.save() # needed to get an ID
        result = _newrack({'title': 'footitle',
                           'address': '123 W 12th st, New York, NY',
                           'date': '2009-11-18 12:33',
                           'source': source.id,
                           'location': Point(20.0, 20.0, srid=SRID),
                           }, {})
        self.assertEqual(result['errors'], {})
        self.failUnless(result.get('message'))
        self.failUnless(result.get('rack'))


class TestActivation(TestCase):

    def test_activate__malformed_key(self):
        response = self.client.get('/accounts/activate/XYZPDQ/')
        self.assertEqual(response.status_code, 200)
        self.failUnless(response.context['key_status'].count('Malformed'))

    # lots more to test in this view!


class TestTweeter(unittest.TestCase):

    username = 'fixcity_testing'

    class StubTweet:
        # for something this trivial, the Mock API is more trouble.
        text = '@fixcity_testing an address #bikerack a title'
        created_at = datetime.datetime.utcfromtimestamp(0)
        id = 123
        class user:
            screen_name = 'bob'

    def test_parse(self):
        fetcher = tweeter.TwitterFetcher(None, self.username)
        self.assertEqual(fetcher.parse(self.StubTweet),
                         {'date': datetime.datetime(1970, 1, 1, 0, 0),
                          'address': 'an address',
                          'tweetid': 123,
                          'user': 'bob',
                          'title': 'a title'})

    @mock.patch('logging.Logger.warn')
    def test_parse_invalid(self, mock_logger_warn):
        fetcher = tweeter.TwitterFetcher(None, self.username)
        self.StubTweet.text = 'invalid format'
        self.assertEqual(fetcher.parse(self.StubTweet), None)
        
    def test_newrack_json_twitter(self):
        from fixcity.bmabr.views import newrack_json

        class MockRequest:

            method = 'POST'
            POST = {}
            raw_post_data = json.dumps(dict(
                title='foo title',
                description='foo description',
                date='2009-11-18 15:14',
                address='148 Lafayette St, New York, NY',
                geocoded=1,  # Skip server-side geocoding.
                location=str(Point(-73.999548, 40.719545, srid=SRID)),
                source_type='twitter',
                twitter_user='TwitterJoe',
                twitter_id=456,
                ))

        response = newrack_json(MockRequest)
        data = json.loads(response._get_content())
        self.failUnless(data.has_key('photo_post_url'))
        self.failUnless(type(data.get('rack')) == int)
        self.failUnless(data.has_key('user'))
        self.failUnless(data.has_key('message'))
        
    @mock.patch('tweepy.API.mentions')
    def test_get_tweets__server_error(self, mock_mentions):
        import tweepy
        mock_mentions.side_effect = tweepy.error.TweepError('500 or something')
        fetcher = tweeter.TwitterFetcher(tweepy.API(), self.username)
        self.assertEqual(fetcher.get_tweets(), [])


    @mock.patch('tweepy.API.mentions')
    def test_get_tweets__empty(self, mock_mentions):
        import tweepy
        mock_mentions.return_value = []
        fetcher = tweeter.TwitterFetcher(tweepy.API(), self.username)
        self.assertEqual(fetcher.get_tweets(), [])

    @mock.patch('tweepy.API.mentions')
    def test_get_tweets__pages(self, mock_mentions):
        import tweepy

        class StubTweet:
            def __init__(self, id):
                self.id = id

        def get_mock_tweet_results(count=1, page=1, *args, **kw):
            # A little helper to simulate the twitter mentions()
            # API.  We'll arbitrarily say that there are 207 total
            # results; 200 in the first page, 7 in the second.
            start = count * (page - 1)
            if page == 2:
                count = 7
            elif page > 2:
                return []
            results = [StubTweet(i) for i in range(start, start + count)]
            return results
                
        mock_mentions.side_effect = get_mock_tweet_results
        fetcher = tweeter.TwitterFetcher(tweepy.API(), self.username)
        results = fetcher.get_tweets()
        self.assertEqual(len(results), 207)
        self.assertEqual(mock_mentions.call_count, 2)

    @mock.patch('tweepy.API')
    @mock.patch('__builtin__.open')
    def test_load_last_status(self, mock_open, MockTweepyAPI):
        import StringIO, pickle
        mock_open.return_value = StringIO.StringIO(
            pickle.dumps({'last_processed_id': 99}))
        builder = tweeter.RackBuilder(settings, MockTweepyAPI())
        self.assertEqual(builder.load_last_status(True), 99)
        self.assertEqual(builder.load_last_status(False), None)

        mock_open.side_effect = IOError("no such file")
        self.assertEqual(builder.load_last_status(True), None)
        
    @mock.patch('tweepy.API')
    def test_main__twitter_down(self, MockTweepyAPI):
        import tweepy
        tweepy_mock = MockTweepyAPI()
        tweepy_mock.rate_limit_status.side_effect = tweepy.error.TweepError(
            "server down?")
        builder = tweeter.RackBuilder(settings, tweepy_mock)
        builder.main()
        self.assertEqual(tweepy_mock.get_tweets.call_count, 0)

    @mock.patch('tweepy.API')
    def test_main__over_limit(self, MockTweepyAPI):
        tweepy_mock = MockTweepyAPI()
        tweepy_mock.rate_limit_status.return_value = {
            'remaining_hits': 0, 'reset_time': 'tomorrow'}
        builder = tweeter.RackBuilder(settings, tweepy_mock)
        self.assertRaises(Exception, builder.main)

    @mock.patch('fixcity.bmabr.management.commands.tweeter.RackBuilder.new_rack')
    @mock.patch('tweepy.API')
    def test_main(self, MockTweepyAPI, mock_new_rack):
        tweepy_mock = MockTweepyAPI()
        user = settings.TWITTER_USER
        builder = tweeter.RackBuilder(settings, tweepy_mock)
        # The Mock API works OK but setting attrs is a bit tedious...
        # i wish you could pass a dict as the spec argument.
        status = mock.Mock(['id', 'text', 'user', 'created_at'])
        status.id = 1
        status.text = '@%s 13 thames st, brooklyn, ny #bikerack mention ' % user
        status.user = mock.Mock(['screen_name'])
        status.user.screen_name = 'some twitter user'
        status.created_at = datetime.datetime.utcfromtimestamp(0)
        tweepy_mock.mentions.return_value = [status]
        tweepy_mock.direct_messages.return_value = []
        tweepy_mock.rate_limit_status.return_value = {'remaining_hits': 999}

        builder.main(False)
        self.assertEqual(mock_new_rack.call_count, 1)
        self.assertEqual(mock_new_rack.call_args,
                         ((),
                          {'address': '13 thames st, brooklyn, ny',
                           'date': datetime.datetime(1970, 1, 1, 0, 0),
                           'title': 'mention',
                           'tweetid': 1,
                           'user': 'some twitter user',
                           }))

    @mock.patch('tweepy.API')
    def test_bounce(self, MockTweepyAPI):
        tweepy_mock = MockTweepyAPI()
        builder = tweeter.RackBuilder(settings, tweepy_mock)
        builder.bounce('somebody', 'an interesting message')
        self.assertEqual(tweepy_mock.update_status.call_args,
                         (('@somebody an interesting message',), {})) 

    @mock.patch('tweepy.API')
    def test_bounce__twitter_down(self, MockTweepyAPI):
        tweepy_mock = MockTweepyAPI()
        builder = tweeter.RackBuilder(settings, tweepy_mock)
        import tweepy
        tweepy_mock.update_status.side_effect = tweepy.error.TweepError(
            "server down?")
        builder.bounce('somebody else', 'twitter down?')
        # ... umm... nothing interesting to test here?

    @mock.patch('logging.Logger.info')
    @mock.patch('fixcity.bmabr.management.commands.tweeter.send_mail')
    @mock.patch('tweepy.API')
    def test_bounce__notify_admin(self, MockTweepyAPI, mock_send_mail,
                                  mock_info):
        tweepy_mock = MockTweepyAPI()
        builder = tweeter.RackBuilder(settings, tweepy_mock)
        message = 'a message!'
        subject = 'this is not my day.'
        builder.bounce('somebody', message, notify_admin=subject)
        args = mock_send_mail.call_args
        self.assertEqual(args[0][0], 'FixCity tweeter bounce! %s' % subject)
        self.failUnless(args[0][1].count('Bouncing to: somebody'))

        builder.bounce('somebody', message, notify_admin=subject,
                       notify_admin_body='more body')
        args = mock_send_mail.call_args
        self.failUnless(args[0][1].count('more body'))



    @mock.patch('fixcity.bmabr.management.commands.tweeter.shorten_url')
    @mock.patch('logging.Logger.info')
    @mock.patch('fixcity.bmabr.management.commands.tweeter.http')
    @mock.patch('tweepy.API')
    def test_new_rack(self, MockTweepyAPI, mock_http, mock_info, mock_shorten):
        tweepy_mock = MockTweepyAPI()
        builder = tweeter.RackBuilder(settings, tweepy_mock)
        class StubResponse:
            status = 200
        mock_http.request.return_value = (StubResponse(), '{"rack": 99}')
        mock_shorten.return_value = 'http://short_url/'
        builder.new_rack('TITLE', 'ADDRESS', 'USER', 'DATE', 123)

        self.assertEqual(mock_http.request.call_count, 1)
        args = mock_http.request.call_args
        self.assert_(args[0][0].startswith('http'))
        self.assertEqual(args[0][1], 'POST')
        self.assertEqual(args[1]['headers'],
                         {'Content-type': 'application/json'})
        from django.utils import simplejson as json
        decoded = json.loads(args[1]['body'])
        self.assertEqual(decoded['address'], 'ADDRESS')
        self.assertEqual(decoded['date'], 'DATE')
        self.assertEqual(decoded['description'], '')
        self.assertEqual(decoded['geocoded'], 0)
        self.assertEqual(decoded['source_type'], 'twitter')
        self.assertEqual(decoded['title'], 'TITLE')
        self.assertEqual(decoded['twitter_id'], 123)
        self.assertEqual(decoded['twitter_user'], 'USER')

        # We notified the user too.
        self.assertEqual(tweepy_mock.update_status.call_count, 1)


    @mock.patch('fixcity.bmabr.management.commands.tweeter.shorten_url')
    @mock.patch('logging.Logger.info')
    @mock.patch('fixcity.bmabr.management.commands.tweeter.http')
    @mock.patch('tweepy.API')
    def test_new_rack__errors(self, MockTweepyAPI, mock_http, mock_info,
                              mock_shorten):
        tweepy_mock = MockTweepyAPI()
        builder = tweeter.RackBuilder(settings, tweepy_mock)
        class StubResponse:
            status = 200
        mock_http.request.return_value = (StubResponse(), '{"errors": "any"}')
        mock_shorten.return_value = 'http://short_url/'
        builder.new_rack('TITLE', 'ADDRESS', 'USER', 'DATE', 123)

        self.assertEqual(mock_http.request.call_count, 1)

        # We notified the user too.
        self.assertEqual(tweepy_mock.update_status.call_count, 1)
        notify_args = tweepy_mock.update_status.call_args
        self.assert_(notify_args[0][0].count('something went wrong'))

    @mock.patch('logging.Logger.info')
    @mock.patch('fixcity.bmabr.management.commands.tweeter.RackBuilder.bounce')
    @mock.patch('fixcity.bmabr.management.commands.tweeter.http')
    @mock.patch('tweepy.API')
    def test_new_rack__server_error(self, MockTweepyAPI, mock_http,
                                    mock_bounce, mock_info):
        tweepy_mock = MockTweepyAPI()
        builder = tweeter.RackBuilder(settings, tweepy_mock)
        class StubResponse:
            status = 500
        mock_http.request.return_value = (StubResponse(), 'content')
        builder.new_rack('TITLE', 'ADDRESS', 'USER', 'DATE', 123)
        self.assertEqual(mock_bounce.call_count, 1)

    @mock.patch('logging.Logger.info')
    @mock.patch('fixcity.bmabr.management.commands.tweeter._notify_admin')
    @mock.patch('fixcity.bmabr.management.commands.tweeter.http')
    @mock.patch('tweepy.API')
    def test_new_rack__network_error(self, MockTweepyAPI, mock_http,
                                     mock_notify_admin, mock_info):
        tweepy_mock = MockTweepyAPI()
        builder = tweeter.RackBuilder(settings, tweepy_mock)
        import socket
        mock_http.request.side_effect = socket.error('oops')
        self.assertRaises(socket.error, builder.new_rack,
                          'TITLE', 'ADDRESS', 'USER', 'DATE', 123)
        self.assertEqual(mock_notify_admin.call_count, 1)

    @mock.patch('fixcity.bmabr.management.commands.tweeter.api_factory')
    @mock.patch('fixcity.bmabr.management.commands.tweeter.RackBuilder.main')
    def test_command(self, mock_main, mock_api_factory):
        from fixcity.bmabr.management.commands.tweeter import Command
        c = Command()
        c.handle()
        self.assertEqual(mock_main.call_count, 1)


class TestKMLViews(TestCase):

        
    def tearDown(self):
        super(TestKMLViews, self).tearDown()
        clear_cache()
                
    def test_rack_requested_kml__empty(self):
        kml = self.client.get('/rack/requested.kml').content
        # This is maybe a bit goofy; we parse the output to test it
        tree = lxml.objectify.fromstring(kml)
        placemarks = tree.Document.getchildren()
        self.assertEqual(len(placemarks), 0)

        
    def test_rack_requested_kml__one(self):
        from fixcity.bmabr.models import Rack
        rack = Rack(address='148 Lafayette St, New York NY',
                    title='TOPP', date=datetime.datetime.utcfromtimestamp(0),
                    email='john@doe.net', location=Point(20.0, 20.0, srid=SRID),
                    )
        rack.save()
        kml = self.client.get('/rack/requested.kml').content
        tree = lxml.objectify.fromstring(kml)
        placemarks = tree.Document.getchildren()
        self.assertEqual(len(placemarks), 1)
        placemark = tree.Document.Placemark
        self.assertEqual(placemark.name, rack.title)
        self.assertEqual(placemark.address, rack.address)
        self.assertEqual(placemark.description, '')
        
        self.assertEqual(placemark.Point.coordinates, '20.0,20.0,0')

        # Argh. Searching child elements for specific attribute values
        # is making my head hurt. xpath should help, but I couldn't
        # find the right expression. Easier to extract them into a
        # dict.
        data = {}
        for d in placemark.ExtendedData.Data:
            data[d.attrib['name']] = d.value

        self.assertEqual(data['page_number'], 1)
        self.assertEqual(data['num_pages'], 1)
        self.assertEqual(data['source'], 'web')
        self.assertEqual(data['date'], 'Jan. 1, 1970')
        self.assertEqual(data['votes'], 0)

