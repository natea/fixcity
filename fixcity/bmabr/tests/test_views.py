# XXX I feel kinda icky importing settings during test

from django.conf import settings
from django.contrib.auth.models import User
from django.test import TestCase

from fixcity.bmabr.models import Rack
from fixcity.bmabr.views import SRID
from fixcity.bmabr.views import _preprocess_rack_form

import lxml.objectify

import mock
import unittest

from datetime import datetime

from django.contrib.gis.geos.point import Point

from django.core.cache import cache
from django.utils import simplejson as json



def clear_cache():
    for key in cache._expire_info.keys():
        cache.delete(key)

class UserTestCaseBase(TestCase):

    """Base class providing some conveniences
    for creating a user and logging in.
    """

    username = 'bernie'
    password = 'funkentelechy'
    email = 'bernieworrell@funk.org'

    def setUp(self):
        super(UserTestCaseBase, self).setUp()
        self._make_user()

    def tearDown(self):
        del(self.user)
        super(UserTestCaseBase, self).tearDown()
        
    def _make_user(self, is_superuser=False):
        user = getattr(self, 'user', None)
        if user is None:
            user = User.objects.create_user(self.username, self.email, self.password)
            user.save()
        if is_superuser != user.is_superuser:
            user.is_superuser = is_superuser
            user.save()
        self.user = user
        return user

    def _login(self, is_superuser=False):
        user = self._make_user(is_superuser)
        self.client.login(username=self.username, password=self.password)
        return user


class TestSourceFactory(unittest.TestCase):

    def test_existing_source(self):
        from fixcity.bmabr.models import Source, TwitterSource
        from fixcity.bmabr.views import source_factory
        existing = Source()
        existing.name = 'misc source'
        existing.save()
        dupe, is_new = source_factory({'source': existing.id})
        self.assertEqual(dupe, existing)
        self.failIf(is_new)

        # It should work also with subclasses of Source...
        twit = TwitterSource(status_id=12345, name='twitter')
        twit.save()
        self.assertEqual((twit, False), source_factory({'source': twit.id}))


    def test_twitter_source(self):
        from fixcity.bmabr.views import source_factory
        twit, is_new = source_factory({'source_type': 'twitter',
                                       'twitter_user': 'bob',
                                       'twitter_id': 123})
        self.assert_(is_new)
        self.assertEqual(twit.user, 'bob')
        self.assertEqual(twit.status_id, 123)
        self.assertEqual(twit.get_absolute_url(), 'http://twitter.com/bob/123')

    def test_unknown_source(self):
        from fixcity.bmabr.views import source_factory
        source, is_new = source_factory({'source_type': 'anything else'})
        self.assertEqual(source, None)
        self.failIf(is_new)


class TestUtilFunctions(unittest.TestCase):

    def setUp(self):
        clear_cache()
        super(TestUtilFunctions, self).setUp()
        
    def tearDown(self):
        clear_cache()
        super(TestUtilFunctions, self).tearDown()

    def test_api_factory(self):
        import tweepy
        from fixcity.bmabr.management.commands.tweeter import api_factory
        api = api_factory(settings)
        self.assert_(isinstance(api, tweepy.API))
                     
    def test_preprocess_rack_form__noop(self):
        orig_data = {'geocoded': '1'}
        data = orig_data.copy()
        _preprocess_rack_form(data)
        self.assertEqual(data, orig_data)

    @mock.patch('geopy.geocoders.Google.geocode')
    def test_preprocess_rack_form__address_but_no_matching_user(self,
                                                                mock_geocode):
        address = '148 Lafayette St, New York, NY'
        mock_geocode.return_value = [(address, (20, 40))]
        data = {'geocoded': '0', 'email': 'foo@bar.com', 'address': address}
        _preprocess_rack_form(data)
        self.failIf(data.has_key('user'))
        self.assertEqual(data['location'],
                         'POINT (40.0000000000000000 20.0000000000000000)')

    @mock.patch('geopy.geocoders.Google.geocode')
    def test_preprocess_rack_form__no_location(self, mock_geocode):
        address = '148 Lafayette St, New York, NY'
        mock_geocode.return_value = []
        data = {'geocoded': '0', 'address': address}
        _preprocess_rack_form(data)
        self.assertEqual(data['location'], u'')

    def test_preprocess_rack_form__with_user(self):
        from fixcity.bmabr.views import _preprocess_rack_form
        data = {'geocoded': '1', 'email': 'foo@bar.com'}
        bob = User(username='bob', email='foo@bar.com')
        bob.save()
        _preprocess_rack_form(data)
        self.assertEqual(data['user'], 'bob')

        
    def test_newrack_no_data(self):
        from fixcity.bmabr.views import _newrack
        from fixcity.bmabr.models import NEED_SOURCE_OR_EMAIL
        result = _newrack({}, {})
        self.failUnless(result.has_key('errors'))
        self.assertEqual(result['errors']['title'],
                         [u'This field is required.'])
        self.assertEqual(result['errors']['address'],
                         [u'This field is required.'])
        self.assertEqual(result['errors']['date'],
                         [u'This field is required.'])
        self.assertEqual(result['errors']['__all__'], [NEED_SOURCE_OR_EMAIL])
        self.assertEqual(result['rack'], None)

    def test_newrack_with_email_but_no_source(self):
        from fixcity.bmabr.views import _newrack
        result = _newrack({'email': 'joe@blow.com'}, {})
        self.assertEqual(result['errors'].get('email'), None)
        self.assertEqual(result['errors'].get('__all__'), None)
        self.assertEqual(result['errors'].get('source'), None)

    def test_newrack_with_bad_source_but_no_email(self):
        from fixcity.bmabr.views import _newrack
        from fixcity.bmabr.models import NEED_SOURCE_OR_EMAIL
        from fixcity.bmabr.models import NEED_LOGGEDIN_OR_EMAIL
        result = _newrack({'source': 999999999}, {})
        self.assertEqual(
            result['errors'].get('source'),
            [u'Select a valid choice. That choice is not one of the available choices.'])
        self.assertEqual(result['errors'].get('email'), [NEED_LOGGEDIN_OR_EMAIL])
        self.assertEqual(result['errors'].get('__all__'), [NEED_SOURCE_OR_EMAIL])

    def test_newrack_working(self):
        from fixcity.bmabr.views import _newrack
        from fixcity.bmabr.models import Source
        source = Source()
        source.name = 'unknown source type'
        source.save() # needed to get an ID
        result = _newrack({'title': 'footitle',
                           'address': '123 W 12th st, New York, NY',
                           'date': '2009-11-18 12:33',
                           'source': source.id,
                           'location': Point(20.0, 20.0, srid=SRID),
                           }, {})
        self.assertEqual(result['errors'], {})
        self.failUnless(result.get('message'))
        self.failUnless(result.get('rack'))


class TestCbsForBoro(TestCase):

    fixtures = ['communityboard_test_fixture.json']

    def test_cbs_for_boro__invalid(self):
        response = self.client.get('/cbs/not_an_int/')
        self.assertEqual(response.status_code, 404)

    def test_cbs_for_boro__no_such_borough(self):
        response = self.client.get('/cbs/123456789/')
        self.assertEqual(response.status_code, 404)

    def test_cbs_for_boro(self):
        response = self.client.get('/cbs/1/')  # 1 = Manhattan
        self.assertEqual(response['Content-Type'], 'application/json')
        parsed = json.loads(response.content)
        self.assertEqual(parsed,
                         [[1, 1], [2, 2], [64, 13]])
        
class TestStreetsFunctions(TestCase):

    # This is a tiny subset of brooklyn CB 1, enough for a couple tests.
    fixtures = ['gis_nycstreets_testfixture.json']

    def test_cross_streets(self):
        from fixcity.bmabr.views import cross_streets_for_rack
        rack = Rack(address='67 s 3rd st, brooklyn, ny 11211',
                    title='williamsburg somewhere',
                    date=datetime.utcfromtimestamp(0),
                    email='john@doe.net',
                    location=Point(-73.964858020364, 40.713349294636,
                                    srid=SRID),
                    )
        self.assertEqual(cross_streets_for_rack(rack),
                         (u"WYTHE AV", u"BERRY ST"))

    def test_cross_streets_outside_nyc(self):
        from fixcity.bmabr.views import cross_streets_for_rack
        rack = Rack(address='i have no idea where this is',
                    title='far away',
                    date=datetime.utcfromtimestamp(0),
                    email='john@doe.net', location=Point(20.0, 20.0, srid=SRID),
                    )
        self.assertEqual(cross_streets_for_rack(rack),
                         (None, None))



class TestNeighborhoodForRack(TestCase):

    # Just williamsburg for testing.
    fixtures = ['gis_neighborhoods_testfixture.json']

    def test_neighborhood_outside_nyc(self):
        from fixcity.bmabr.views import neighborhood_for_rack
        rack = Rack(address='i have no idea where this is',
                    title='far away',
                    date=datetime.utcfromtimestamp(0),
                    email='john@doe.net', location=Point(20.0, 20.0, srid=SRID),
                    )
        self.assertEqual(neighborhood_for_rack(rack),
                         "<unknown>")

    def test_cross_streets(self):
        from fixcity.bmabr.views import neighborhood_for_rack
        rack = Rack(address='67 s 3rd st, brooklyn, ny 11211',
                    title='williamsburg somewhere',
                    date=datetime.utcfromtimestamp(0),
                    email='john@doe.net',
                    location=Point(-73.964858020364, 40.713349294636,
                                    srid=SRID),
                    )
        self.assertEqual(neighborhood_for_rack(rack),
                         "Williamsburg")


class TestIndex(TestCase):

    def test_index(self):
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)


class TestProfile(UserTestCaseBase):

    def test_profile(self):
        response = self.client.get('/profile/')
        self.assertEqual(response.status_code, 302)
        self._login()
        response = self.client.get('/profile/')
        self.assertEqual(response.status_code, 200)
        

class TestActivation(TestCase):

    def test_activate__malformed_key(self):
        response = self.client.get('/accounts/activate/XYZPDQ/')
        self.assertEqual(response.status_code, 200)
        self.failUnless(response.context['key_status'].count('Malformed'))

    # lots more to test in this view!



class TestKMLViews(TestCase):

        
    def tearDown(self):
        super(TestKMLViews, self).tearDown()
        clear_cache()
                
    def test_rack_requested_kml__empty(self):
        kml = self.client.get('/racks/requested.kml').content
        # This is maybe a bit goofy; we parse the output to test it
        tree = lxml.objectify.fromstring(kml)
        placemarks = tree.Document.getchildren()
        self.assertEqual(len(placemarks), 0)

        
    def test_rack_requested_kml__one(self):
        rack = Rack(address='148 Lafayette St, New York NY',
                    title='TOPP', date=datetime.utcfromtimestamp(0),
                    email='john@doe.net', location=Point(20.0, 20.0, srid=SRID),
                    )
        rack.save()
        kml = self.client.get('/racks/requested.kml').content
        tree = lxml.objectify.fromstring(kml)
        placemarks = tree.Document.getchildren()
        self.assertEqual(len(placemarks), 1)
        placemark = tree.Document.Placemark
        self.assertEqual(placemark.name, rack.title)
        self.assertEqual(placemark.address, rack.address)
        self.assertEqual(placemark.description, '')
        
        self.assertEqual(placemark.Point.coordinates, '20.0,20.0,0')

        # Argh. Searching child elements for specific attribute values
        # is making my head hurt. xpath should help, but I couldn't
        # find the right expression. Easier to extract them into a
        # dict.
        data = {}
        for d in placemark.ExtendedData.Data:
            data[d.attrib['name']] = d.value

        self.assertEqual(data['page_number'], 1)
        self.assertEqual(data['num_pages'], 1)
        self.assertEqual(data['source'], 'web')
        self.assertEqual(data['date'], 'Jan. 1, 1970')
        self.assertEqual(data['votes'], 0)


class TestRackView(UserTestCaseBase):

    def test_rack_view_anonymous(self):
        rack = Rack(address='148 Lafayette St, New York NY',
                    title='TOPP', date=datetime.utcfromtimestamp(0),
                    email='john@doe.net', location=Point(20.0, 20.0, srid=SRID),
                    user='somebody',
                    )
        rack.save()
        response = self.client.get('/racks/%d/' % rack.id)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['user_likes_this_rack'], False)
        self.assertEqual(response.context['user_suggested_this_rack'], False)

    def test_rack_view_logged_in(self):
        user = self._login()
        rack = Rack(address='148 Lafayette St, New York NY',
                    title='TOPP', date=datetime.utcfromtimestamp(0),
                    email='john@doe.net', location=Point(20.0, 20.0, srid=SRID),
                    user=user.username,
                    )
        rack.save()
        response = self.client.get('/racks/%d/' % rack.id)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['user_likes_this_rack'], False)
        self.assertEqual(response.context['user_suggested_this_rack'], True)

class TestVotes(UserTestCaseBase):

    def test_get(self):
        rack = Rack(address='148 Lafayette St, New York NY',
                    title='TOPP', date=datetime.utcfromtimestamp(0),
                    email='john@doe.net', location=Point(20.0, 20.0, srid=SRID),
                    )
        rack.save()
        self._login()
        response = self.client.get('/racks/%d/votes/' % rack.id)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, '{"votes": 0}')


    def test_post(self):
        rack = Rack(address='148 Lafayette St, New York NY',
                    title='TOPP', date=datetime.utcfromtimestamp(0),
                    email='john@doe.net', location=Point(20.0, 20.0, srid=SRID),
                    )
        rack.save()
        response = self.client.post('/racks/%d/votes/' % rack.id)
        self.assertEqual(response.status_code, 302)
        self._login()
        response = self.client.post('/racks/%d/votes/' % rack.id)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, '{"votes": 1}')


class TestBulkOrders(UserTestCaseBase):

    def _make_bulk_order(self):
        # Ugh, there's a lot of inter-model dependencies to satisfy
        # before I can save a BulkOrder.  And I can't seem to mock
        # these.
        from fixcity.bmabr.models import NYCDOTBulkOrder, CommunityBoard, Borough
        user = self._make_user(is_superuser=True)
        from decimal import Decimal
        geom = 'MULTIPOLYGON (((0.0 0.0, 1.0 0.0, 1.0 1.0, 0.0 0.0)))'
        borough = Borough(boroname='Brooklyn', gid=1, borocode=1,
                          the_geom=geom, 
                          shape_leng=Decimal("339789.04731400002"),
                          shape_area=Decimal("635167251.876999974"),
                          )
        borough.save()
        cb = CommunityBoard(gid=1, borocd=1, board=1,
                            the_geom=geom,
                            borough=borough)
        cb.save()

        from fixcity.bmabr.models import Rack
        from fixcity.bmabr.models import TwitterSource
        ts = TwitterSource(name='twitter', user='joe', status_id='99')

        rack = Rack(location='POINT (0.5 0.5)', email=user.email,
                    user=user.username,
                    title='A popular bar',
                    address='123 Something St, Brooklyn NY',
                    date=datetime.utcfromtimestamp(0),
                    source=ts,
                    )
        rack.save()

        bo = NYCDOTBulkOrder(user=user, communityboard=cb)
        bo.save()
        return bo

    def test_bulk_order_edit_form__unprivileged(self):
        response = self.client.get('/bulk_order/999/edit/')
        self.assertEqual(response.status_code, 302)
        self.failUnless(response.has_header('location'))
        self.assertEqual(response['location'],
                         'http://testserver/accounts/login/?next=/bulk_order/999/edit/')
        
    def test_bulk_order_edit_form__missing(self):
        user = self._login(is_superuser=True)
        response = self.client.get('/bulk_order/123456789/edit/')
        self.assertEqual(response.status_code, 404)

    def test_bulk_order_edit_form__get(self):
        bo = self._make_bulk_order()
        cb = bo.communityboard
        response = self.client.get('/bulk_order/%d/edit/' % bo.id)
        self.assertEqual(response.status_code, 302)
        self._login(is_superuser=True)
        response = self.client.get('/bulk_order/%d/edit/' % bo.id)
        self.assertEqual(response.status_code, 200)
        

    def test_bulk_order_edit_form__post(self):
        bo = self._make_bulk_order()
        # XXX do something


    def test_bulk_order_add_form__get(self):
        response = self.client.get('/bulk_order/')
        self.assertEqual(response.status_code, 302)
        self._login(is_superuser=True)
        response = self.client.get('/bulk_order/')
        self.assertEqual(response.status_code, 200)

    def test_bulk_order_add_form__post(self):
        from fixcity.bmabr.models import NYCDOTBulkOrder
        bo = self._make_bulk_order()
        cb = bo.communityboard
        bo.delete()
        # There's no BO for this community board now...
        self.assertEqual(len(NYCDOTBulkOrder.objects.filter(communityboard=cb)),
                         0)
        user = self._login(is_superuser=True)
        response = self.client.post('/bulk_order/', {'cb_gid': cb.pk,
                                                     'organization': 'TOPP',
                                                     'rationale': 'because i care'})
        if response.context is not None:
            self.assertEqual(response.context['form'].errors, [])
        self.assertEqual(response.status_code, 302)
        # There should be a BO now...
        self.assertEqual(len(NYCDOTBulkOrder.objects.filter(communityboard=cb)),
                         1)
        bo_id = NYCDOTBulkOrder.objects.get(communityboard=cb).id
        self.assertEqual(response['location'],
                         'http://testserver/bulk_order/%d/edit/' % bo_id)

    def test_bulk_order_pdf(self):
        bo = self._make_bulk_order()
        cb = bo.communityboard
        response = self.client.get('/communityboard/%d/bulk_order/order.pdf/' % cb.pk)
        self.assertEqual(response['Content-Type'], 'application/pdf')
        self.assertEqual(response.status_code, 200)

    def test_bulk_order_csv(self):
        bo = self._make_bulk_order()
        cb = bo.communityboard
        response = self.client.get('/communityboard/%d/bulk_order/order.csv/' % cb.pk)
        self.assertEqual(response['Content-Type'], 'text/csv')
        self.assertEqual(response.status_code, 200)

