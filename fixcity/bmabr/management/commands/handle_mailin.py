'''
This is a manage.py command for django which handles incoming email,
typically via stdin.

To hook this up with postfix, set up an alias along the lines of:

myaddress: "|PYTHON_EGG_CACHE=/tmp/my-egg-cache /PATH/TO/VENV/bin/python /PATH/TO/VENV/src/fixcity/fixcity/manage.py handle_mailin -u http://MYDOMAIN/racks/ --debug=9 - >> /var/log/MYLOGS/mailin.log 2>&1""

You will want a cron job or something that cleans up the --debug-dir directory
(defaults to your TMP directory).

'''

# based on email2trac.py, which is Copyright (C) 2002 under the GPL v2 or later

from datetime import datetime
from optparse import make_option
from poster.encode import multipart_encode
from stat import S_IRWXU, S_IRWXG, S_IRWXO
import email.Header
import httplib2
import logging
import mimetypes
import os
import re
import socket
import string
import sys
import tempfile
import time
import traceback
import unicodedata
import urlparse

from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.mail import send_mail
from django.core.management.base import BaseCommand
from django.utils import simplejson as json

from django.conf import settings

logger = settings.LOGGER

class EmailParser(object):

    msg = None

    def __init__(self, parameters):

        # Save parameters
        #
        self.parameters = parameters

        # Some useful mail constants
        #
        self.author = None
        self.email_addr = None
        self.email_from = None
        self.id = None

        for key, default, typecast in (
            ('debug', 0, int),
            ('strip_signature', 0, int),
            ('max-attachment-size', -1, int),
            ):
            self.parameters[key] = typecast(self.parameters.get(key, default))


    def _make_logfile(self, suffix='.handle_mailin'):
        """where to put dumps of messages for debugging"""
        logdir = self.parameters.get('debug_dir') or tempfile.gettempdir()
        try:
            os.makedirs(logdir)
        except OSError:
            if not os.path.isdir(logdir):
                raise
        return tempfile.mktemp(suffix, dir=logdir)

    def email_to_unicode(self, message_str):
        """
        Email has 7 bit ASCII code, convert it to unicode with the charset
that is encoded in 7-bit ASCII code and encode it as utf-8.
        """
        results =  email.Header.decode_header(message_str)
        str = None
        for text,format in results:
            if format:
                try:
                    temp = unicode(text, format)
                except UnicodeError, detail:
                    # This always works
                    #
                    temp = unicode(text, 'iso-8859-15')
                except LookupError, detail:
                    #text = 'ERROR: Could not find charset: %s, please install' %format
                    #temp = unicode(text, 'iso-8859-15')
                    temp = message_str

            else:
                temp = string.strip(text)
                temp = unicode(text, 'iso-8859-15')

            if str:
                str = '%s %s' %(str, temp)
            else:
                str = '%s' %temp

        #str = str.encode('utf-8')
        return str

    def debug_body(self, message_body):
        body_file = self._make_logfile()

        logger.debug('writing body (%s)' % body_file)
        fx = open(body_file, 'wb')
        if not message_body:
            message_body = '(None)'

        message_body = message_body.encode('utf-8')
        #message_body = unicode(message_body, 'iso-8859-15')

        fx.write(message_body)
        fx.close()
        try:
            os.chmod(body_file,S_IRWXU|S_IRWXG|S_IRWXO)
        except OSError:
            pass

    def debug_attachments(self, message_parts):
        n = 0
        for part in message_parts:
            # Skip inline text parts
            if not isinstance(part, tuple):
                continue

            (original, filename, part) = part

            n = n + 1
            logger.debug(' part%d: Content-Type: %s' % (n, part.get_content_type()))
            logger.debug('part%d: filename: %s' % (n, part.get_filename()))

            part_file = self._make_logfile(suffix='.handle_mailin.part%d' % n)

            logger.debug('writing part%d (%s)' % (n,part_file))
            fx = open(part_file, 'wb')
            text = part.get_payload(decode=1)
            if not text:
                text = '(None)'
            fx.write(text)
            fx.close()
            try:
                os.chmod(part_file,S_IRWXU|S_IRWXG|S_IRWXO)
            except OSError:
                pass


    def get_sender_info(self):
        """
        Get the default author name and email address from the message
        """
        message = self.msg
        self.email_to = self.email_to_unicode(message['to'])
        self.to_name, self.to_email_addr = email.Utils.parseaddr (self.email_to)

        self.email_from = self.email_to_unicode(message['from'])
        self.author, self.email_addr  = email.Utils.parseaddr(self.email_from)

        # Trac can not handle author's name that contains spaces
        # XXX do we care about author's name for fixcity? prob not.
        self.author = self.email_addr


    def save_email_for_debug(self, message):
        msg_file = self._make_logfile()

        logger.debug(' saving email to %s' % msg_file)
        fx = open(msg_file, 'wb')
        fx.write('%s' % message)
        fx.close()
        try:
            os.chmod(msg_file,S_IRWXU|S_IRWXG|S_IRWXO)
        except OSError:
            pass


    def new_rack(self, title, address):
        """
        Create a new rack
        """
        msg = self.msg
        logger.debug('new rack')

        message_parts = self.get_message_parts()
        message_parts = self.unique_attachment_names(message_parts)

        description = self.description = self.body_text(message_parts)
        photos = self.get_photos(message_parts)
        # We don't bother with microsecond precision because
        # Django datetime fields can't parse it anyway.
        now = datetime.fromtimestamp(int(time.time()))
        data = dict(title=title,
                    source_type='email',
                    description=description,
                    date=now.isoformat(' '),
                    address=address,
                    geocoded=0,  # Do server-side location processing.
                    got_communityboard=0,   # Ditto.
                    email=self.email_addr,
                    )

        if self.parameters.get('dry-run') and self.parameters['debug']:
            logger.debug("would save rack here")
            return

        # This is the one thing i apparently can't do
        # when running as `nobody`.
        # And getting postfix to run this script as another user
        # seems to be a PITA.
        #rack = rackform.save()

        # So instead, let's POST our data to some URL...
        url = settings.RACK_POSTING_URL
        jsondata = json.dumps(data)
        http = httplib2.Http()
        headers = {'Content-type': 'application/json'}
        error_subject = "Unsuccessful Rack Request"
        try:
            response, content = http.request(url, 'POST',
                                             headers=headers,
                                             body=jsondata)
        except (socket.error, AttributeError):
            # it's absurd that we have to catch AttributeError here,
            # but apparently that's what httplib 0.5.0 raises because
            # the socket ends up being None. Lame!
            # Known issue: http://code.google.com/p/httplib2/issues/detail?id=62&can=1&q=AttributeError
            self.bounce(
                error_subject,
                "Thanks for trying to suggest a rack.\n"
                "We are unfortunately experiencing some difficulties at the\n"
                "moment -- please try again in an hour or two!",
                notify_admin='Server down??'
                )
            return

        logger.debug("server responded with:\n%s" % content)

        if response.status >= 500:
            err_msg = (
                "Thanks for trying to suggest a rack.\n"
                "We are unfortunately experiencing some difficulties at the\n"
                "moment. Please check to make sure your subject line follows\n"
                "this format exactly:\n\n"
                "  Key Foods @224 McGuinness Blvd Brooklyn NY\n\n"
                "If you've made an error, please resubmit. Otherwise we'll\n"
                "look into this issue and get back to you as soon as we can.\n"
                )
            admin_body = content
            self.bounce(error_subject, err_msg, notify_admin='500 Server error',
                        notify_admin_body=content)
            return

        result = json.loads(content)
        if result.has_key('errors'):

            err_msg = (
                "Thanks for trying to suggest a rack through fixcity.org,\n"
                "but it won't go through without the proper information.\n\n"
                "Please correct the following errors:\n\n")

            errors = adapt_errors(result['errors'])
            for k, v in sorted(errors.items()):
                err_msg += "%s: %s\n" % (k, '; '.join(v))

            err_msg += "\nPlease try again!\n"
            self.bounce(error_subject, err_msg)
            return

        parsed_url = urlparse.urlparse(url)
        base_url = parsed_url[0] + '://' + parsed_url[1]
        photo_url = base_url + result['photo_post_url']
        rack_url = base_url + result['rack_url']
        rack_user = result.get('user')

        if photos.has_key('photo'):
            datagen, headers = multipart_encode({'photo':
                                                 photos['photo']})
            # httplib2 doesn't like poster's integer headers.
            headers['Content-Length'] = str(headers['Content-Length'])
            body = ''.join([s for s in datagen])
            response, content = http.request(photo_url, 'POST',
                                             headers=headers, body=body)
            # XXX handle errors
            logger.debug("result from photo upload:")
            logger.debug(content)
        # XXX need to add links per
        # https://projects.openplans.org/fixcity/wiki/EmailText
        # ... will need an HTML version.
        reply = "Thanks for your rack suggestion!\n\n"
        reply += "You must verify that your spot meets DOT requirements\n"
        reply += "before we can submit it.\n"
        reply += "To verify, go to: %(rack_url)sedit/\n\n"
        if not rack_user:
            # XXX Create an inactive account and add a confirmation link.
            reply += "To create an account, go to %(base_url)s/accounts/register/ .\n\n"  % locals()
        reply += "Thanks!\n\n"
        reply += "- The Open Planning Project & Livable Streets Initiative\n"
        reply = reply % locals()
        self.reply("FixCity Rack Confirmation", reply)


    def parse(self, s):
        self.msg = email.message_from_string(s)
        if not self.msg:
            logger.debug("This is not a valid email message format")
            return

        # Work around lack of header folding in Python; see http://bugs.python.org/issue4696
        self.msg.replace_header('Subject', self.msg['Subject'].replace('\r', '').replace('\n', ''))

        message_parts = self.get_message_parts()
        message_parts = self.unique_attachment_names(message_parts)
        body_text = self.body_text(message_parts)

        if self.parameters['debug'] > 1:        # save the entire e-mail message text
            self.save_email_for_debug(self.msg)
            self.debug_body(body_text)
            self.debug_attachments(message_parts)

        self.get_sender_info()
        subject  = self.email_to_unicode(self.msg.get('Subject', ''))
        subject_re = re.compile(r'(?P<title>[^\@]*)\s*@(?P<address>.*)')
        subject_match = subject_re.search(subject)
        if subject_match:
            title = subject_match.group('title').strip()
            address = subject_match.group('address')
        else:
            address_re = re.compile(r'@(?P<address>.+)$', re.MULTILINE)
            address_match = address_re.search(body_text)
            if address_match:
                address = address_match.group('address')
            else:
                address = ''  # Let the server deal with lack of address.
            title = subject

        address = address.strip()
        self.new_rack(title, address)

    def strip_signature(self, text):
        """
        Strip signature from message, inspired by Mailman software
        """
        body = []
        for line in text.splitlines():
            if line == '-- ':
                break
            body.append(line)

        return ('\n'.join(body))


    def get_message_parts(self):
        """
        parses the email message and returns a list of body parts and attachments
        body parts are returned as strings, attachments are returned as tuples of (filename, Message object)
        """
        msg = self.msg
        message_parts = []

        # This is used to figure out when we are inside an AppleDouble container
        # AppleDouble containers consists of two parts: Mac-specific file data, and platform-independent data
        # We strip away Mac-specific stuff
        appledouble_parts = []

        ALTERNATIVE_MULTIPART = False

        for part in msg.walk():
            logger.debug('Message part: Main-Type: %s' % part.get_content_maintype())
            logger.debug('Message part: Content-Type: %s' % part.get_content_type())


            # Check whether we just finished processing an AppleDouble container
            if part not in appledouble_parts:
                appledouble_parts = []

            ## Check content type
            # Special handling for Mac-specific attachments.
            if part.get_content_type() == 'application/mac-binhex40':
                message_parts.append("'''A BinHex attachment named '%s' was ignored (use MIME encoding instead).'''" % part.get_filename())
                continue
            elif part.get_content_type() == 'application/applefile':
                if part in appledouble_parts:
                    message_parts.append("'''The resource fork of an attachment named '%s' was removed.'''" % part.get_filename())
                    continue
                else:
                    message_parts.append("'''An AppleSingle attachment named '%s' was ignored (use MIME encoding instead).'''" % part.get_filename())
                    continue
            elif part.get_content_type() == 'multipart/appledouble':
                # If we entering an AppleDouble container, set up appledouble_parts so that we know what to do with its subparts
                appledouble_parts = part.get_payload()
                continue
            elif part.get_content_type() == 'multipart/alternative':
                ALTERNATIVE_MULTIPART = True
                continue

            # Skip multipart containers
            if part.get_content_maintype() == 'multipart':
                logger.debug("Skipping multipart container")
                continue

            # Check if this is an inline part. It's inline if there is co Cont-Disp header, or if there is one and it says "inline"
            inline = self.inline_part(part)

            # Drop HTML message
            if ALTERNATIVE_MULTIPART:
                if part.get_content_type() == 'text/html':
                    logger.debug("Skipping alternative HTML message")
                    ALTERNATIVE_MULTIPART = False
                    continue

            # Inline text parts are where the body is
            if part.get_content_type() == 'text/plain' and inline:
                logger.debug('               Inline body part')

                # Try to decode, if fails then do not decode
                #
                body_text = part.get_payload(decode=1)
                if not body_text:
                    body_text = part.get_payload(decode=0)

                format = email.Utils.collapse_rfc2231_value(part.get_param('Format', 'fixed')).lower()
                delsp = email.Utils.collapse_rfc2231_value(part.get_param('DelSp', 'no')).lower()

                if self.parameters['strip_signature']:
                    body_text = self.strip_signature(body_text)

                # Get contents charset (iso-8859-15 if not defined in mail headers)
                #
                charset = part.get_content_charset()
                if not charset:
                    charset = 'iso-8859-15'

                try:
                    ubody_text = unicode(body_text, charset)

                except UnicodeError, detail:
                    ubody_text = unicode(body_text, 'iso-8859-15')

                except LookupError, detail:
                    ubody_text = 'ERROR: Could not find charset: %s, please install' %(charset)

                message_parts.append('%s' %ubody_text)
            else:
                # Not inline body, or a specially-handled attachment.
                logger.debug('               Filename: %s' % part.get_filename())

                message_parts.append((part.get_filename(), part))
        return message_parts

    def unique_attachment_names(self, message_parts):
        renamed_parts = []
        attachment_names = set()
        for part in message_parts:

            # If not an attachment, leave it alone
            if not isinstance(part, tuple):
                renamed_parts.append(part)
                continue

            (filename, part) = part
            # Decode the filename
            if filename:
                filename = self.email_to_unicode(filename)
            # If no name, use a default one
            else:
                filename = 'untitled-part'

                # Guess the extension from the content type, use non strict mode
                # some additional non-standard but commonly used MIME types
                # are also recognized
                #
                ext = mimetypes.guess_extension(part.get_content_type(), False)
                if not ext:
                    ext = '.bin'

                filename = '%s%s' % (filename, ext)

            # Discard relative paths in attachment names
            filename = filename.replace('\\', '/').replace(':', '/')
            filename = os.path.basename(filename)

            # We try to normalize the filename to utf-8 NFC if we can.
            # Files uploaded from OS X might be in NFD.
            # Check python version and then try it
            #
            if sys.version_info[0] > 2 or (sys.version_info[0] == 2 and sys.version_info[1] >= 3):
                try:
                    filename = unicodedata.normalize('NFC', unicode(filename, 'utf-8')).encode('utf-8')
                except TypeError:
                    pass

            # Make the filename unique for this rack
            num = 0
            unique_filename = filename
            filename, ext = os.path.splitext(filename)

            while unique_filename in attachment_names:
                num += 1
                unique_filename = "%s-%s%s" % (filename, num, ext)

            logger.debug(' Attachment with filename %s will be saved as %s' % (filename, unique_filename))
            attachment_names.add(unique_filename)

            renamed_parts.append((filename, unique_filename, part))

        return renamed_parts

    def inline_part(self, part):
        return part.get_param('inline', None, 'Content-Disposition') == '' or not part.has_key('Content-Disposition')


    def body_text(self, message_parts):
        body_text = []

        for part in message_parts:
            # Plain text part, append it
            if not isinstance(part, tuple):
                body_text.extend(part.strip().splitlines())
                body_text.append("")
                continue

        body_text = '\r\n'.join(body_text)
        self._body_text = body_text
        return body_text


    def get_photos(self, message_parts):
        """save an attachment as a single photo
        """
        # Get Maxium attachment size
        #
        max_size = self.parameters['max-attachment-size']
        status   = ''
        results = {}

        for part in message_parts:
            # Skip text body parts
            if not isinstance(part, tuple):
                continue

            (original, filename, part) = part
            # Skip html attachments and the like.
            if not part.get_content_type().startswith('image'):
                continue

            text = part.get_payload(decode=1)
            if not text:
                continue
            file_size = len(text)

            # Check if the attachment size is allowed
            #
            if (max_size != -1) and (file_size > max_size):
                status = '%s\nFile %s is larger than allowed attachment size (%d > %d)\n\n' \
                        %(status, original, file_size, max_size)
                continue

            # We use SimpleUploadedFile because it conveniently
            # supports the subset of file-like behavior needed by
            # poster.  Too bad, that's the last reason we really need
            # to import anything from django.
            results[u'photo'] = SimpleUploadedFile.from_dict(
                {'filename': filename, 'content': text,
                 'content-type': part.get_content_type()})
            # XXX what to do if there's more than one attachment?
            # we just ignore 'em.
            break
        return results


    def bounce(self, subject, body, notify_admin='', notify_admin_body=''):
        """Bounce a message to the sender, with additional subject
        and body for explanation.

        If the notify_admin string is non-empty, the site admin will
        be notified, with that string appended to the subject.
        If notify_admin_body is non-empty, it will be added to the body
        sent to the admin.
        """
        logger.debug("Bouncing message to %s" % self.email_addr)
        body += '\n\n------------ original message follows ---------\n\n'
        # TO DO: use attachments rather than inline.
        body += unicode(self.msg.as_string(), errors='ignore')
        if notify_admin:
            admin_subject = 'FixCity handle_mailin bounce! %s' % notify_admin
            admin_body = 'Bouncing to: %s\n' % self.msg['from']
            admin_body += 'Bounce subject: %r\n' % subject
            admin_body += 'Time: %s\n' % datetime.now().isoformat(' ')
            admin_body += 'Not attaching original body, check the log file.\n'
            if notify_admin_body:
                admin_body += 'Additional info:\n'
                admin_body += notify_admin_body
            self.notify_admin(admin_subject, admin_body)
        return self.reply(subject, body)

    def reply(self, subject, body):
        send_mail(subject, body, self.msg['to'], [self.msg['from']],
                  fail_silently=False)

    def notify_admin(self, subject, body):
        admin_email = settings.SERVICE_FAILURE_EMAIL
        if self.msg and self.msg.get('to'):
            from_addr = self.msg['to']
        else:
            # email might be so fubar that we can't even get addresses from it?
            from_addr = 'racks@fixcity.org'
        send_mail(subject, body, from_addr, [admin_email], fail_silently=False)


def adapt_errors(errors):
    """Convert the form field names in the errors dict into things
    that are meaningful via the email workflow, and adjust error
    messages appropriately too.
    """
    adapted = {}
    remove_me = object()
    key_mapping = {
        'title': 'subject',
        'address': remove_me,  # an error here will also show up in 'location'.
        'description': 'body',
        }

    val_mapping = {
        ('subject', 'This field is required.'): 
        ("Your subject line should follow this format:\n\n"
         "  Key Foods @224 McGuinness Blvd, Brooklyn NY\n\n"
         "First comes the name of the establishment"
         "(store, park, office etc.) you want a rack near.\n"
         "Then enter @ followed by the address.\n"
         ),

        ("location", "No geometry value provided."):
        ("The address didn't come through properly. Your subject line\n"
         "should follow this format:\n\n"
         "  Key Foods @224 McGuinness Blvd, Brooklyn NY\n\n"
         "Make sure you have the street, city, and state listed after\n"
         "the @ sign in this exact format.\n"),
        }

    for key, vals in errors.items():
        for val in vals:
            key = key_mapping.get(key, key)
            if key is remove_me:
                continue
            val = val_mapping.get((key, val), val)
            adapted[key] = adapted.get(key, ()) + (val,)
    return adapted


class Command(BaseCommand):
    option_list = BaseCommand.option_list + (
        make_option('--dry-run', action="store_true",
                    help="Don't save any data.", dest="dry_run"),
        make_option('--debug', type="int", default=0,
                    help="Add some verbosity and save any problematic data."),
        make_option('--debug-dir', type="str", default=0, action='store',
                    help="Where to dump mail messages for debugging."),
        make_option('--strip-signature', action="store_true", default=True,
                    help="Remove signatures from incoming mail"),
        make_option('--max-attachment-size', type="int",
                    help="Max size of uploaded files."),
    )

    def handle(self, *args, **options):
        logger.debug('starting handle')
        parser = EmailParser(options)
        did_stdin = False
        for filename in args:
            now = datetime.now().isoformat(' ')
            logger.info("------------- %s ------------" % now)
            if filename == '-':
                if did_stdin:
                    continue
                thisfile = sys.stdin
                did_stdin = True
            else:
                thisfile = open(filename)
            try:
                raw_msg = thisfile.read()
                parser.parse(raw_msg)
            except:
                tb_msg = "Exception at %s follows:\n------------\n" % now
                tb_msg += traceback.format_exc()
                tb_msg += "\n -----Original message follows ----------\n\n"
                tb_msg += raw_msg
                if parser.msg:
                    parser.save_email_for_debug(parser.msg)
                parser.notify_admin('Unexpected traceback in handle_mailin',
                                    tb_msg)
                raise
