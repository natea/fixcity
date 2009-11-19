
# XXX I feel kinda icky importing settings during test
from django.conf import settings

from django.contrib.gis.geos.point import Point
from django.utils import simplejson as json
from fixcity.bmabr.management.commands import tweeter
from fixcity.bmabr.views import SRID
import mock
import tweepy

import unittest


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

        
class TestNewRack(unittest.TestCase):

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
        result = _newrack({'source': 999999999}, {})
        self.assertEqual(result['errors'].get('email'), None)
        self.assertEqual(
            result['errors'].get('source'),
            [u'Select a valid choice. That choice is not one of the available choices.'])
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



class TestTweeter(unittest.TestCase):

    def test_parse(self):
        username = 'fixcity_testing'
        class StubTweet:
            text = '@%s a title #bikerack an address' % username
        fetcher = tweeter.TwitterFetcher(None, username)
        self.assertEqual(('a title', 'an address'), fetcher.parse(StubTweet))

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
        
    
    @mock.patch('fixcity.bmabr.management.commands.tweeter.new_rack')
    @mock.patch('tweepy.API')
    def test_main(self, MockTweepyAPI, mock_new_rack):
        tweepy_mock = MockTweepyAPI()
        user = settings.TWITTER_USER
        builder = tweeter.RackBuilder('http://localhost:8000/rack/',
                                      settings, tweepy_mock)
        # The Mock API works OK but setting attrs is a bit tedious...
        # i wish you could pass a dict as the spec argument.
        status = mock.Mock(['id', 'text', 'user'])
        status.id = 1
        status.text = '@%s mention #bikerack 13 thames st, brooklyn, ny' % user
        status.user = mock.Mock(['name'])
        status.user.name = 'some twitter user'
        tweepy_mock.mentions.return_value = [status]
        tweepy_mock.direct_messages.return_value = []
        builder.main(False)
        self.assertEqual(mock_new_rack.call_count, 1)
        self.assertEqual(mock_new_rack.call_args,
                         (('mention', '13 thames st, brooklyn, ny',
                           'some twitter user', 1,
                           'http://localhost:8000/rack/'), {}))

