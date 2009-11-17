
import unittest
import tweepy
import tweeter
import mock


class TestTweeter(unittest.TestCase):

    def test_new_rack(self):
        pass

    def test_parse(self):
        username = 'fixcity_testing'
        class StubTweet:
            text = '@%s a title #bikerack an address' % username
        fetcher = tweeter.TwitterFetcher(None, username)
        self.assertEqual(('a title', 'an address'), fetcher.parse(StubTweet))

    @mock.patch('fixcity.bmabr.tweeter.new_rack')
    @mock.patch('tweepy.API')
    def test_main(self, MockTweepyAPI, mock_new_rack):
        tweepy_mock = MockTweepyAPI()
        user = 'fixcity_test'
        class MockConfig(object):
            def get(self, *args, **kw):
                return user # we don't care about anything else.

        builder = tweeter.RackBuilder('http://localhost:8000/rack/',
                                      MockConfig(), tweepy_mock)
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
                           'some twitter user',
                           'http://localhost:8000/rack/'), {}))
