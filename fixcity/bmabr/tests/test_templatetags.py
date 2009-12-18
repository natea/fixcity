import unittest
import mock


class TestRecaptchaTags(unittest.TestCase):

    def test_recaptcha_html(self):
        from fixcity.bmabr.templatetags import recaptcha_tags
        from django.conf import settings  
        html = recaptcha_tags.recaptcha_html()
        self.failUnless(settings.RECAPTCHA_PUBLIC_KEY in html)
        self.failUnless(html.startswith('<script'))
        

class TestGoogleTags(unittest.TestCase):

    @mock.patch('django.conf.settings')
    def test_google_analytics(self, mock_settings):
        from fixcity.bmabr.templatetags import google_analytics
        mock_settings.GOOGLE_ANALYTICS_KEY = 'xyzpdq'
        html = google_analytics.google_analytics()
        self.failUnless('xyzpdq' in html)
        self.failUnless(html.startswith('<script'))

        # For some reason this doesn't work if I put it in a separate
        # test case... the google_analytics() function keeps a
        # reference to the OLD mock_settings instance with the
        # 'xyzpdq' value!
        mock_settings.GOOGLE_ANALYTICS_KEY = ''
        html = google_analytics.google_analytics()
        self.assertEqual(html, '')
