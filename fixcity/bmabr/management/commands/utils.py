from django.conf import settings
from django.utils import simplejson as json
from poster.encode import multipart_encode
import httplib2
import socket
import urlparse

logger = settings.LOGGER

class _False(object):
    def __len__(self):
        return 0

SERVER_TEMP_FAILURE = _False()

SERVER_ERROR = _False()


class FixcityHttp(object):

    def __init__(self, notifier, error_adapter):
        self.notifier = notifier
        self.error_adapter = error_adapter

    def submit(self, data):
        photos = data.pop('photos', {})
        url = settings.RACK_POSTING_URL
        result = self.do_post_json(url, data)
        if not result:
            # XXX return what?
            return

        if result.has_key('errors'):
            return result

        # Lots of rack-specific stuff below
        parsed_url = urlparse.urlparse(url)
        base_url = parsed_url[0] + '://' + parsed_url[1]
        photo_url = base_url + result['photo_post_url']
        rack_url = base_url + result['rack_url']
        rack_user = result.get('user')

        if photos.has_key('photo'):
            datagen, headers = multipart_encode({'photo': photos['photo']})
            # httplib2 doesn't like poster's integer headers.
            headers['Content-Length'] = str(headers['Content-Length'])
            body = ''.join([s for s in datagen])
            status, result = self.do_post(photo_url, body, headers=headers)
            logger.debug("result from photo upload:")
            logger.debug("%s, %s" % (status, result))

        self.notifier.on_submit_success(locals())

    def do_post_json(self, url, data, headers={}):
        """Post some data as json to the given URL.
        Expect the response to be JSON data, and return it decoded.
        If there are errors, return None.

        If the server detects validation errors, it should include an
        'errors' key in the response data.  The value for 'errors'
        should be a mapping of field name to a list of error strings
        for that field.  (Not coincidentally, django forms yield
        validation errors in that format.)
        """
        body = json.dumps(data)
        err_subject = "Unsuccessful Rack Request"
        headers.setdefault('Content-type', 'application/json')
        status, response_body = self.do_post(url, body, headers)
        if status != 200:
            # errors should've already been handled by do_post
            return None
        if isinstance(response_body, basestring):
            try:
                result = json.loads(response_body)
            except ValueError:
                logger.error("Got unparseable body. Response code %d. Body:\n%s"
                             % (status, response_body))
                self.notifier.bounce(err_subject,
                                     self.error_adapter.server_error_permanent)
                return None
            if result.has_key('errors'):
                err_msg = self.error_adapter.validation_errors(result['errors'])
                self.notifier.bounce(err_subject, err_msg)
        else:
            # XXX shouldn't get a non-string here, handle this error
            result = response_body
        return result


    def do_post(self, url, body, headers={}):
        """POST the body to the URL. Returns (status, response body)
        on success, or error placeholders on failure.
        """
        err_subject = "Unsuccessful Rack Request"
        http = httplib2.Http()
        try:
            response, content = http.request(url, 'POST',
                                             headers=headers,
                                             body=body)
        except (socket.error, AttributeError):
            # it's absurd that we have to catch AttributeError here,
            # but apparently that's what httplib2 0.5.0 raises because
            # the socket ends up being None. Lame!
            # Known issue: http://code.google.com/p/httplib2/issues/detail?id=62&can=1&q=AttributeError
            logger.debug('Server down? %r' % url)
            self.notifier.bounce(
                err_subject,
                self.error_adapter.server_error_retry,
                notify_admin='Server down??'
                )
            return None, None

        logger.debug("server %r responded with %s:\n%s" % (
            url, response.status, content))

        if response.status >= 500:
            err_msg = self.error_adapter.server_error_permanent
            self.notifier.bounce(
                err_subject, err_msg, notify_admin='500 Server error',
                notify_admin_body=content)

        return response.status, content

