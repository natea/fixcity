import unittest

class TestRecaptchaTags(unittest.TestCase):

    def test_recaptcha_html(self):
        from fixcity.bmabr.templatetags import recaptcha_tags
        from django.conf import settings  
        html = recaptcha_tags.recaptcha_html()
        self.failUnless(settings.RECAPTCHA_PUBLIC_KEY in html)
        self.failUnless(html.startswith('<script'))
        

class TestGoogleTags(unittest.TestCase):

    def test_google_analytics(self):
        from fixcity.bmabr.templatetags import google_analytics
        from django.conf import settings  
        html = google_analytics.google_analytics()
        self.failUnless(settings.GOOGLE_ANALYTICS_KEY in html)
        self.failUnless(html.startswith('<script'))
