from django.conf import settings
from django.utils import simplejson as json
from poster.encode import multipart_encode
import httplib2
import socket
import urlparse

logger = settings.LOGGER


class FixcityHttp(object):

    def __init__(self, notifier):
        self.notifier = notifier

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
        """Post a data structure (to be encoded as JSON) to the given URL.
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
        assert isinstance(response_body, basestring), "Got non-string body %r even though response code was 200." % response_body
        try:
            result = json.loads(response_body)
        except ValueError:
            error = "Got unparseable body. Response code %d. Body:\n%s" % (
                status, response_body)
            logger.error(error)
            self.notifier.on_server_error(error)
            return None
        if result.has_key('errors'):
            self.notifier.on_user_error(data, result['errors'])
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
            self.notifier.on_server_temp_failure()
            return None, None

        logger.debug("server %r responded with %s:\n%s" % (
            url, response.status, content))

        if response.status >= 500:
            self.notifier.on_server_error(content)

        return response.status, content
