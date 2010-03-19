# XXX I feel kinda icky importing settings during test

from django.test import TestCase

from fixcity.bmabr.management.commands import handle_mailin


import mock
import os

HERE = os.path.abspath(os.path.dirname(__file__))


class TestMailin(TestCase):

    username = 'fixcity_testing'

    @mock.patch('logging.Logger.debug')
    @mock.patch('fixcity.bmabr.management.commands.handle_mailin.Notifier')
    def test_parse__no_data(self, mock_notifier, mock_debug):
        parser = handle_mailin.EmailParser(mock_notifier(), {})
        self.assertEqual(parser.parse(''), None)

    @mock.patch('logging.Logger.debug')
    @mock.patch('fixcity.bmabr.management.commands.handle_mailin.Notifier')
    def test_parse__no_address(self, mock_notifier, mock_debug):
        parser = handle_mailin.EmailParser(mock_notifier(), {})
        msg = open(os.path.join(HERE, 'files', 'test-mailin-no-address.txt')).read()
        parsed = parser.parse(msg)

        self.assertEqual(sorted(parsed.keys()),
                         ['address', 'date', 'description', 
                          'email', 'geocoded', 'got_communityboard', 
                          'photos', 'source_type', 'title'])
        self.assertEqual(parsed['address'], '')
        self.failUnless(isinstance(parsed.get('date'), basestring))
        self.assertEqual(parsed['description'], u'This is the body.\r\n')
        self.assertEqual(parsed['email'], u'pw@example.org')
        self.assertEqual(parsed['geocoded'], 0)
        self.assertEqual(parsed['got_communityboard'], 0)
        self.assertEqual(parsed['photos'], {})
        self.assertEqual(parsed['source_type'], 'email')
        self.assertEqual(parsed['title'], u'somewhere')


    @mock.patch('logging.Logger.debug')
    @mock.patch('fixcity.bmabr.management.commands.handle_mailin.Notifier')
    def test_parse__with_photo(self, mock_notifier, mock_debug):
        parser = handle_mailin.EmailParser(mock_notifier(), {})
        msg = open(os.path.join(HERE, 'files', 'test-mailin-with-photo.txt')).read()
        parsed = parser.parse(msg)
        photos = parsed['photos']
        self.assertEqual(len(photos), 1)
        self.assert_(photos.has_key('photo'))
        photo = photos['photo']
        # XXX not sure it's worth testing the photo very much,
        # as we don't really care about the SimpleUploadedFile API
        self.assertEqual(photo.content_type, 'image/jpeg')
        self.assertEqual(photo.name, u'IMG_0133.JPG')


    @mock.patch('logging.Logger.debug')
    @mock.patch('fixcity.bmabr.management.commands.handle_mailin.Notifier')
    def test_parse__apple_weirdness(self, mock_notifier, mock_debug):
        parser = handle_mailin.EmailParser(mock_notifier(), {})
        msg = open(os.path.join(HERE, 'files', 'test-mailin-apple-weirdness.txt')).read()
        parsed = parser.parse(msg)
        self.assert_(isinstance(parsed['description'], unicode))
        self.failIf(parsed['description'].count('<html>'))
        # What else to test??

