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


class TestMailinRackMaker(TestCase):

    @mock.patch('logging.Logger.debug')
    def test_submit__dry_run(self, mock_debug):
        maker = handle_mailin.RackMaker(None, {'dry-run': True})
        self.assertEqual(maker.submit({}), None)


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
        from django.conf import settings
        settings.SERVICE_FAILURE_EMAIL = 'foo@localhost.localdomain'
        notifier.bounce('bounce subject', 'bounce body', notify_admin='NOTIFY')
        self.assertEqual(mock_send_mail.call_count, 2)
        admin_args, user_args = mock_send_mail.call_args_list
        admin_args, admin_kw_args = admin_args
        self.assertEqual(admin_args[0], 'FixCity handle_mailin bounce! NOTIFY')
        self.assert_(admin_args[1].startswith("Bouncing to: "))
        self.assertEqual(admin_args[2], "<racks@fixcity.org>")
        self.assertEqual(admin_args[3], ['foo@localhost.localdomain'])

        # The user gets the same email whether you notify the admin or not.
        notifier.bounce('bounce subject', 'bounce body')
        self.assertEqual(mock_send_mail.call_args_list[-1],
                         mock_send_mail.call_args_list[-2])


    @mock.patch('fixcity.bmabr.management.commands.handle_mailin.Notifier.reply')
    def test_on_submit_success(self, mock_reply):
        notifier = self._make_one()
        vars = {'rack_url': 'http://foo/racks/1', 'rack_user': 'bob'}
        notifier.on_submit_success(vars)
        self.assertEqual(mock_reply.call_count, 1)

    @mock.patch('fixcity.bmabr.management.commands.handle_mailin.Notifier.bounce')
    def test_on_user_error(self, mock_bounce):
        notifier = self._make_one()
        notifier.on_user_error({'title': 'required'})
        self.assertEqual(mock_bounce.call_count, 1)

    @mock.patch('fixcity.bmabr.management.commands.handle_mailin.Notifier.bounce')
    def test_on_server_error(self, mock_bounce):
        notifier = self._make_one()
        notifier.on_server_error('blech')
        self.assertEqual(mock_bounce.call_count, 1)

    @mock.patch('fixcity.bmabr.management.commands.handle_mailin.Notifier.bounce')
    def test_on_server_temp_failure(self, mock_bounce):
        notifier = self._make_one()
        notifier.on_server_temp_failure()
        self.assertEqual(mock_bounce.call_count, 1)
        self.assert_('experiencing some difficulties' in
                     mock_bounce.call_args[0][1])

