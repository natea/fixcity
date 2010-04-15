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


class TestRackMaker(TestCase):

    @mock.patch('httplib2.Response')
    @mock.patch('httplib2.Http.request')
    @mock.patch('logging.Logger.debug')
    @mock.patch('fixcity.bmabr.management.commands.handle_mailin.Notifier')
    def test_do_post__success(self, mock_notifier, mock_debug,  mock_request,
                              mock_response):
        response = mock_response()
        notifier = mock_notifier()
        response.status = 200
        mock_request.return_value = (response, 'hello POST world')
        maker = handle_mailin.RackMaker(mock_notifier(), {})

        content = maker.do_post('http://example.com', 'test body')
        self.assertEqual(content, 'hello POST world')
        self.failIf(notifier.bounce.call_count)


    @mock.patch('httplib2.Response')
    @mock.patch('httplib2.Http.request')
    @mock.patch('logging.Logger.debug')
    @mock.patch('fixcity.bmabr.management.commands.handle_mailin.Notifier')
    def test_do_post__500_error(self, mock_notifier, mock_debug,  mock_request,
                                mock_response):
        response = mock_response()
        notifier = mock_notifier()
        response.status = 500
        mock_request.return_value = (response, 'hello POST world')
        maker = handle_mailin.RackMaker(notifier, {})

        content = maker.do_post('http://example.com', 'test body')
        self.assertEqual(content, None)
        self.assertEqual(notifier.bounce.call_count, 1)
        bounce_kwargs = notifier.bounce.call_args[-1]
        self.assertEqual(bounce_kwargs, {'notify_admin_body': 'hello POST world', 
                                         'notify_admin': '500 Server error'})



    @mock.patch('httplib2.Http.request')
    @mock.patch('logging.Logger.debug')
    @mock.patch('fixcity.bmabr.management.commands.handle_mailin.Notifier')
    def test_do_post__socket_error(self, mock_notifier, mock_debug,
                                   mock_request):
        import socket
        notifier = mock_notifier()
        mock_request.side_effect = socket.error("kaboom")
        maker = handle_mailin.RackMaker(notifier, {})

        content = maker.do_post('http://example.com', 'test body')
        self.assertEqual(content, None)
        self.assertEqual(notifier.bounce.call_count, 1)
        bounce_kwargs = notifier.bounce.call_args[-1]
        self.assertEqual(bounce_kwargs, {'notify_admin': 'Server down??'})


    @mock.patch('httplib2.Response')
    @mock.patch('httplib2.Http.request')
    @mock.patch('logging.Logger.debug')
    @mock.patch('fixcity.bmabr.management.commands.handle_mailin.Notifier')
    def test_do_post_json(self, mock_notifier, mock_debug, mock_request,
                          mock_response):
        response = mock_response()
        notifier = mock_notifier()
        response.status = 200
        mock_request.return_value = (response, '{"foo": "bar"}')
        maker = handle_mailin.RackMaker(mock_notifier(), {})

        content = maker.do_post_json('http://example.com',
                                     "{'some key': 'some value'}")
        self.assertEqual(content, {'foo': 'bar'})
        self.failIf(notifier.bounce.call_count)


    @mock.patch('httplib2.Response')
    @mock.patch('httplib2.Http.request')
    @mock.patch('logging.Logger.debug')
    @mock.patch('fixcity.bmabr.management.commands.handle_mailin.Notifier')
    def test_do_post_json__validation_errors(self, mock_notifier, mock_debug,
                                             mock_request, mock_response):
        response = mock_response()
        notifier = mock_notifier()
        response.status = 200
        from django.utils import simplejson as json
        error_body = json.dumps(
            {'errors': {'title': ['This field is required.']}})
        mock_request.return_value = (response, error_body)
        maker = handle_mailin.RackMaker(mock_notifier(), {})

        content = maker.do_post_json('http://example.com',
                                     "{'some key': 'some value'}")
        self.assertEqual(content, None)
        self.assertEqual(notifier.bounce.call_count, 1)


    @mock.patch('logging.Logger.debug')
    def test_submit__dry_run(self, mock_debug):
        maker = handle_mailin.RackMaker(None, {'dry-run': True})
        self.assertEqual(maker.submit({}), None)
        
    @mock.patch('httplib2.Response')
    @mock.patch('httplib2.Http.request')
    @mock.patch('logging.Logger.debug')
    @mock.patch('fixcity.bmabr.management.commands.handle_mailin.Notifier')
    def test_submit__no_result(self, mock_notifier, mock_debug,
                               mock_request, mock_response):
        response = mock_response()
        notifier = mock_notifier()
        response.status = 200
        mock_request.return_value = (response, '')
        maker = handle_mailin.RackMaker(notifier, {})

        self.assertEqual(maker.submit({}), None)

    @mock.patch('httplib2.Response')
    @mock.patch('fixcity.bmabr.management.commands.handle_mailin.RackMaker.do_post')
    @mock.patch('logging.Logger.debug')
    @mock.patch('fixcity.bmabr.management.commands.handle_mailin.Notifier')
    def test_submit__with_photos_and_user(self, mock_notifier, mock_debug,
                                          mock_do_post, mock_response):
        mock_do_post.return_value = '''{
            "user": "bob",
            "photo_post_url": "http://example.com/photos/",
            "rack_url": "http://example.com/racks/1"
            }'''
        notifier = mock_notifier()
        maker = handle_mailin.RackMaker(notifier, {})

        # Mock photo needs to be just file-like enough.
        mock_photo_file = mock.Mock()
        mock_photo_file.name = 'foo.jpg'
        mock_photo_file.fileno.side_effect = AttributeError()
        mock_photo_file.tell.return_value = 12345
        mock_photo_file.read.return_value = ''
        self.assertEqual(maker.submit({'photos': {'photo': mock_photo_file}}),
                         None)
        self.assertEqual(notifier.reply.call_args[0][0], "FixCity Rack Confirmation")
