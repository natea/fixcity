# XXX I feel kinda icky importing settings during test

from django.test import TestCase

from fixcity.bmabr.management.commands import handle_mailin
from fixcity.bmabr.management.commands.utils import SERVER_TEMP_FAILURE, SERVER_ERROR


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


class TestMailinRackMaker(TestCase):

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
        maker = handle_mailin.RackMaker(mock_notifier(), {}, handle_mailin.ErrorAdapter())

        content = maker.do_post('http://example.com', 'test body')
        self.assertEqual(content, 'hello POST world')
        self.failIf(notifier.bounce.call_count)


    @mock.patch('httplib2.Response')
    @mock.patch('httplib2.Http.request')
    @mock.patch('logging.Logger.debug')
    @mock.patch('fixcity.bmabr.management.commands.handle_mailin.Notifier')
    def test_do_post__500_error(self, mock_notifier, mock_debug,  mock_request,
                                mock_response):
        # XXX testing some innards of utils.FixcityHttp; factor out test?
        response = mock_response()
        notifier = mock_notifier()
        response.status = 500
        mock_request.return_value = (response, 'hello POST world')
        maker = handle_mailin.RackMaker(notifier, {}, handle_mailin.ErrorAdapter())

        content = maker.do_post('http://example.com', 'test body')
        self.assertEqual(content, SERVER_ERROR)
        self.assertEqual(notifier.bounce.call_count, 1)
        bounce_kwargs = notifier.bounce.call_args[-1]
        self.assertEqual(bounce_kwargs, {'notify_admin_body': 'hello POST world', 
                                         'notify_admin': '500 Server error'})



    @mock.patch('httplib2.Http.request')
    @mock.patch('logging.Logger.debug')
    @mock.patch('fixcity.bmabr.management.commands.handle_mailin.Notifier')
    def test_do_post__socket_error(self, mock_notifier, mock_debug,
                                   mock_request):
        # XXX testing some innards of utils.FixcityHttp; factor out test?
        import socket
        notifier = mock_notifier()
        mock_request.side_effect = socket.error("kaboom")
        maker = handle_mailin.RackMaker(notifier, {}, handle_mailin.ErrorAdapter())

        content = maker.do_post('http://example.com', 'test body')
        self.assertEqual(content, SERVER_TEMP_FAILURE)
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
        maker = handle_mailin.RackMaker(mock_notifier(), {}, handle_mailin.ErrorAdapter())

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
        maker = handle_mailin.RackMaker(mock_notifier(), {}, handle_mailin.ErrorAdapter())

        content = maker.do_post_json('http://example.com',
                                     "{'some key': 'some value'}")
        self.assertEqual(content, None)
        self.assertEqual(notifier.bounce.call_count, 1)


    @mock.patch('logging.Logger.debug')
    def test_submit__dry_run(self, mock_debug):
        maker = handle_mailin.RackMaker(None, {'dry-run': True}, None)
        self.assertEqual(maker.submit({}), None)
        
    @mock.patch('httplib2.Response')
    @mock.patch('httplib2.Http.request')
    @mock.patch('logging.Logger.debug')
    @mock.patch('fixcity.bmabr.management.commands.handle_mailin.Notifier')
    def test_submit__successful_empty_result(self, mock_notifier, mock_debug,
                                             mock_request, mock_response):
        response = mock_response()
        notifier = mock_notifier()
        response.status = 200
        mock_request.return_value = (response, '{}')
        maker = handle_mailin.RackMaker(notifier, {}, handle_mailin.ErrorAdapter())
        self.assertEqual(maker.submit({}), {})

    @mock.patch('httplib2.Response')
    @mock.patch('fixcity.bmabr.management.commands.utils.FixcityHttp.do_post')
    @mock.patch('logging.Logger.debug')
    @mock.patch('fixcity.bmabr.management.commands.handle_mailin.Notifier')
    def test_submit__with_photos_and_user(self, mock_notifier, mock_debug,
                                          mock_do_post,
                                          mock_response):
        # XXX Most of this functionality is now in utils. MOve test 
        # somewhere more appropriate.

        # Mock typically uses side_effect() to specify multiple return
        # value; clunky API but works fine.
        do_post_return_values = [
            '''{
            "user": "bob",
            "photo_post_url": "/photos/",
            "rack_url": "/racks/1"
            }''',
            'OK']
        def side_effect(*args, **kw):
            return do_post_return_values.pop(0)
        mock_do_post.side_effect = side_effect
        notifier = mock_notifier()
        maker = handle_mailin.RackMaker(notifier, {}, handle_mailin.ErrorAdapter())
        # Mock photo needs to be just file-like enough.
        mock_photo_file = mock.Mock()
        mock_photo_file.name = 'foo.jpg'
        mock_photo_file.fileno.side_effect = AttributeError()
        mock_photo_file.tell.return_value = 12345
        mock_photo_file.read.return_value = ''

        self.assertEqual(maker.submit({'photos': {'photo': mock_photo_file}}),
                         None)
        self.assertEqual(notifier.on_submit_success.call_count, 1)
        vars = notifier.on_submit_success.call_args[0][0]
        self.assert_(vars.has_key('rack_url'))
        self.assert_(vars.has_key('rack_user'))


class TestMailinNotifier(TestCase):

    @staticmethod
    def _make_one():
        msg = open(os.path.join(HERE, 'files', 'test-mailin-no-address.txt'))
        import email
        from fixcity.bmabr.management.commands.handle_mailin import Notifier
        notifier = Notifier()
        notifier.msg = email.message_from_string(msg.read())
        return notifier

    @mock.patch('fixcity.bmabr.management.commands.handle_mailin.send_mail')
    def test_reply(self, mock_send_mail):
        notifier = self._make_one()
        notifier.reply('reply subject', 'reply body')
        self.assertEqual(
            mock_send_mail.call_args,
            (('reply subject', 'reply body', '<racks@fixcity.org>',
              ['Paul Winkler <pw@example.org>']),
             {'fail_silently': False}))

    @mock.patch('logging.Logger.debug')
    @mock.patch('fixcity.bmabr.management.commands.handle_mailin.send_mail')
    def test_bounce(self, mock_send_mail, mock_debug):
        notifier = self._make_one()
        notifier.bounce('bounce subject', 'bounce body')
        args, kwargs = mock_send_mail.call_args
        self.assertEqual(args[0], 'bounce subject')
        self.assert_(args[1].startswith('bounce body'))
        self.assert_(args[1].endswith(notifier.msg.as_string()))
        self.assertEqual(args[2], '<racks@fixcity.org>')
        self.assertEqual(args[3], ['Paul Winkler <pw@example.org>'])
        self.assertEqual(kwargs, {'fail_silently': False})

    @mock.patch('logging.Logger.debug')
    @mock.patch('fixcity.bmabr.management.commands.handle_mailin.send_mail')
    def test_bounce__notify_admin(self, mock_send_mail, mock_debug):
        notifier = self._make_one()
        notifier.bounce('bounce subject', 'bounce body', notify_admin='NOTIFY')
        self.assertEqual(mock_send_mail.call_count, 2)
        admin_args, user_args = mock_send_mail.call_args_list
        admin_args, admin_kw_args = admin_args
        self.assertEqual(admin_args[0], 'FixCity handle_mailin bounce! NOTIFY')
        self.assert_(admin_args[1].startswith("Bouncing to: "))
        self.assertEqual(admin_args[2], "<racks@fixcity.org>")
        self.assertEqual(admin_args[3], ['pw+admin@openplans.org'])

        # The user gets the same email whether you notify the admin or not.
        notifier.bounce('bounce subject', 'bounce body')
        self.assertEqual(mock_send_mail.call_args_list[-1],
                         mock_send_mail.call_args_list[-2])
