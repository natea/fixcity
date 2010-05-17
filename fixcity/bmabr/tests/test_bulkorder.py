from datetime import datetime
from django.contrib.auth.models import User
from django.test import TestCase
import mock
import os
from fixcity.bmabr import bulkorder

class UserTestCaseBase(TestCase):

    """Base class providing some conveniences
    for creating a user and logging in.
    """

    username = 'bernie'
    password = 'funkentelechy'
    email = 'bernieworrell@funk.org'

    def _make_user(self, is_superuser=False):
        try:
            user = User.objects.get(username=self.username)
        except User.DoesNotExist:
            user = User.objects.create_user(self.username, self.email, self.password)
            user.save()
        if is_superuser != user.is_superuser:
            user.is_superuser = is_superuser
            user.save()
        return user

    def _login(self, is_superuser=False):
        user = self._make_user(is_superuser)
        self.client.login(username=self.username, password=self.password)
        return user


class TestBulkOrderFunctions(UserTestCaseBase):

    geom = 'MULTIPOLYGON (((0.0 0.0, 1.0 0.0, 1.0 1.0, 0.0 1.0, 0.0 0.0)))'

    def _make_cb(self):
        from fixcity.bmabr.models import CommunityBoard, Borough
        from decimal import Decimal
        borough = Borough(boroname='Brooklyn', gid=1, borocode=1,
                          the_geom=self.geom,
                          shape_leng=Decimal("339789.04731400002"),
                          shape_area=Decimal("635167251.876999974"),
                          )
        borough.save()
        cb = CommunityBoard(gid=1, borocd=1, board=1,
                            the_geom=self.geom,
                            borough=borough)
        cb.save()
        return cb

    def _make_rack(self):
        from fixcity.bmabr.models import Rack
        from fixcity.bmabr.models import TwitterSource
        user = self._make_user()
        ts = TwitterSource(name='twitter', user='joe', status_id='99')
        rack = Rack(location='POINT (0.5 0.5)', email=user.email,
                    user=user.username,
                    title='A popular bar',
                    address='123 Something St, Brooklyn NY',
                    date=datetime.utcfromtimestamp(0),
                    source=ts,
                    )
        rack.save()
        return rack

    def _make_bulk_order(self):
        # Ugh, there's a lot of inter-model dependencies to satisfy
        # before I can save a BulkOrder.  And I can't seem to mock
        # these.
        user = self._make_user()
        cb = self._make_cb()
        rack = self._make_rack()
        from fixcity.bmabr.models import NYCDOTBulkOrder
        bo = NYCDOTBulkOrder(user=user, communityboard=cb)
        bo.save()
        return bo

    @mock.patch('fixcity.bmabr.bulkorder.get_map')
    def test_make_rack_page(self, mock_get_map):
        HERE = os.path.abspath(os.path.dirname(__file__))
        img_path = os.path.join(HERE, 'files', 'test_exif.jpg')
        mock_get_map.return_value = img_path
        rack = self._make_rack()
        flowables = bulkorder.make_rack_page(rack)
        self.assert_(isinstance(flowables, list))
        self.assertEqual(mock_get_map.call_count, 1)


    @mock.patch('fixcity.bmabr.bulkorder.get_map')
    def test_make_pdf__google_down(self, mock_get_map):
        mock_get_map.side_effect = RuntimeError('Whoopsie')
        bo = self._make_bulk_order()
        bo.approve()
        from cStringIO import StringIO
        outfile = StringIO()
        self.assertRaises(RuntimeError, bulkorder.make_pdf, bo, outfile)
        # We retried our mocked map-getter 3 times, and it raised the exception
        # each time, as if the service on the other end was dead...
        self.assertEqual(mock_get_map.call_count, 3)

