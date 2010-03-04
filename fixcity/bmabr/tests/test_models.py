from django.contrib.gis.geos.point import Point
from django.core.files.uploadedfile import TemporaryUploadedFile
from django.forms import ValidationError
from django.test import TestCase
from fixcity.bmabr.views import SRID
from fixcity.bmabr.models import RackForm
from fixcity.bmabr.models import Rack
from fixcity.bmabr.models import Source
import datetime

EPOCH = datetime.datetime.utcfromtimestamp(0)

class TestCommunityBoard(TestCase):

    def test_create_cb_and_borough(self):
        from fixcity.bmabr.models import CommunityBoard, Borough
        borough = Borough(borocode=1, boroname='Staten Island')
        cb = CommunityBoard(
            gid=1,
            borocd=99, board=123, borough=borough)
        self.assertEqual(unicode(cb), u'Staten Island Community Board 123')
                            
    def test_racks_within_boundaries(self):
        from fixcity.bmabr.models import CommunityBoard
        communityboard = CommunityBoard(the_geom='MULTIPOLYGON (((0.0 0.0, 10.0 0.0, 10.0 10.0, 0.0 10.0, 0.0 0.0)))')
        rack_inside = Rack(location='POINT (5.0 5.0)', date=EPOCH)
        rack_outside = Rack(location='POINT (20.0 20.0)', date=EPOCH)
        rack_edge = Rack(location='POINT (0.0 0.0)', date=EPOCH)
        rack_inside.save()
        rack_edge.save()
        rack_outside.save()

        self.assertEqual(set(communityboard.racks),
                         set([rack_inside, rack_edge]))


class TestRack(TestCase):

    def test_create_rack(self):
        from fixcity.bmabr.models import Rack
        point = Point(1.0, 2.0, SRID)
        rack = Rack(
            address='somewhere',
            date=EPOCH,
            location=point)
        self.assertEqual(rack.verified, False)

    def test_filter_by_verified(self):
        from fixcity.bmabr.models import Rack
        # If ALL 3 fields are true, we filter it as verified.
        rack = Rack(address='67 s 3rd st, brooklyn, ny 11211',
                    title='williamsburg somewhere',
                    date=EPOCH,
                    email='john@doe.net',
                    location=Point(-73.964858020364, 40.713349294636,
                                    srid=SRID),
                    verify_surface=True,
                    verify_objects=True,
                    verify_access=True)
        rack.save()
        self.assertEqual(1, Rack.objects.filter_by_verified('verified').count())
        self.assertEqual(0, Rack.objects.filter_by_verified('unverified').count())

        # If ANY of those fields are false, the rack is unverified.
        rack.verify_surface = False
        rack.save()
        self.assertEqual(0, Rack.objects.filter_by_verified('verified').count())
        self.assertEqual(1, Rack.objects.filter_by_verified('unverified').count())

        rack.verify_surface = True
        rack.verify_access = False
        rack.save()
        self.assertEqual(0, Rack.objects.filter_by_verified('verified').count())
        self.assertEqual(1, Rack.objects.filter_by_verified('unverified').count())

        rack.verify_access = True
        rack.verify_objects = False
        rack.save()
        self.assertEqual(0, Rack.objects.filter_by_verified('verified').count())
        self.assertEqual(1, Rack.objects.filter_by_verified('unverified').count())



class TestRackForm(TestCase):

    data = {'email': 'foo@bar.org',
            'title': 'A rack',
            'date': EPOCH,
            'location': Point(1.0, 2.0, SRID),
            'address': 'noplace in particular',
            }

    def test_rack_form_clean_photo(self):
        from fixcity.exif_utils import get_exif_info
        from PIL import Image
        import os.path

        data = self.data.copy()
        # Jump through a few hoops to simulate a real upload.
        HERE = os.path.abspath(os.path.dirname(__file__))
        path = os.path.join(HERE, 'files', 'test_exif.jpg')
        content = open(path).read()
        photofile = TemporaryUploadedFile('test_exif.jpg', 'image/jpeg',
                                          len(content), None)
        photofile.write(content)
        photofile.seek(0)
        # Okay, now we have something like a file upload.
        data['photo'] = photofile
        form = RackForm(data, {'photo': photofile})
        self.assert_(form.is_valid())
        # Make sure it doesn't have a bad rotation.        
        self.assertEqual({},
                         get_exif_info(Image.open(photofile.temporary_file_path())))
        
    
    def test_rack_form_clean__bound(self):
        data = self.data.copy()
        form = RackForm(data, {})
        form.is_bound = True
        form.instance.source = Source()
        form.is_valid()
        self.assertEqual(form.cleaned_data, form.clean())


    def test_rack_form_clean__unbound_with_email(self):
        data = self.data.copy()
        form = RackForm(data, {})
        form = RackForm(data, {})
        form.is_bound = False
        form.cleaned_data = data
        form._errors = {}

        self.assertEqual(form.cleaned_data, form.clean())


    def test_rack_form_clean__unbound_with_no_email_or_source(self):
        data = self.data.copy()
        del(data['email'])
        form = RackForm(data, {})
        form.is_bound = False
        form.cleaned_data = data
        form._errors = {}

        # Can't validate without an email or source
        self.assertRaises(ValidationError, form.clean)


    def test_rack_form_clean__unbound_with_source(self):
        data = self.data.copy()
        del(data['email'])
        form = RackForm(data, {})
        form.is_bound = False
        form.cleaned_data = data
        form._errors = {}
        self.assertRaises(ValidationError, form.clean)

        # A source is sufficient.
        form.cleaned_data['source'] = 'something'
        self.assertEqual(form.cleaned_data, form.clean())

    def test_rack_form_bound__verified(self):
        data = self.data.copy()
        data['verify_access'] = 'on'
        data['verify_objects'] = 'on'
        data['verify_surface'] = 'on'

        form = RackForm(data, {})
        form.is_bound = True
        self.assertEqual(form.is_valid(), True)
        self.assertEqual(form.cleaned_data['status'], 'verified')

    def test_rack_form_bound__unverified(self):
        data = self.data.copy()
        form = RackForm(data, {})
        form.is_bound = True
        self.assertEqual(form.is_valid(), True)
        self.assertEqual(form.cleaned_data['status'], 'new')

class TestSource(TestCase):

    def test_get_child_source(self):
        from fixcity.bmabr.models import TwitterSource
        ts = TwitterSource(name='twitter', user='joe', status_id='99')
        ts.save()
        from fixcity.bmabr.models import Source
        generic_source = Source.objects.filter(id=ts.id).all()[0]
        self.assertEqual(generic_source.twittersource, ts)
        self.assertEqual(generic_source.get_child_source(), ts)


class TestNYCDOTBulkOrder(TestCase):

    def _make_bo_and_rack(self):
        from fixcity.bmabr.models import NYCDOTBulkOrder, User, Rack, CommunityBoard
        user = User()
        user.save()
        cb = CommunityBoard(
            the_geom='MULTIPOLYGON (((0.0 0.0, 10.0 0.0, 10.0 10.0, 0.0 10.0, 0.0 0.0)))',
            gid=1, borocd=1, board=1, borough_id=1)
        cb.save()
        rack = Rack(location='POINT (5.0 5.0)', date=EPOCH)
        rack.save()

        bo = NYCDOTBulkOrder(user=user, communityboard=cb)
        return bo, rack

    def test_create_and_destroy(self):
        bo, rack = self._make_bo_and_rack()
        bo.save()
        bo.delete()
        rack.delete()

    def test_submission_adds_racks(self):
        bo, rack = self._make_bo_and_rack()
        bo.save()
        cb = bo.communityboard
        # Initially the bulk order has all racks from the cb.
        self.assertEqual(set(cb.racks), set([rack]))
        self.assertEqual(set(bo.racks), set([rack]))
        self.assertEqual(bo.status, 'new')
        # Approving has no effect...
        bo.approve()
        bo.save()
        self.assertEqual(set(bo.racks), set([rack]))
        self.assertEqual(set(bo.racks), set(cb.racks))
        self.assertEqual(bo.status, 'approved')
        # Gahhh. Django core devs think it's reasonable to chase
        # down all your references to a changed instance and reload
        # them by re-looking up the object by ID. Otherwise the state
        # in memory is out of date. (django ticket 901)
        rack = Rack.objects.get(id=rack.id)
        self.failIf(rack.locked)
        
        # Submission locks them...
        bo.submit()
        self.assertEqual(bo.status, 'pending')
        rack = Rack.objects.get(id=rack.id)
        self.assert_(rack.locked)
        self.assertEqual(set(bo.racks), set(cb.racks))

        # ... and even if you move a rack away from its cb,
        # it's still associated with this order.
        rack.location = 'POINT (100.0 100.0)'
        rack.save()
        rack = Rack.objects.get(id=rack.id)
        self.assertEqual(set(bo.racks), set([rack]))
        self.assertEqual(set(cb.racks), set())
        


    def test_racks_get_locked(self):
        bo, rack = self._make_bo_and_rack()
        bo.save()
        rack.bulk_orders.add(bo)
        rack.save()
        # reload to get new state.
        rack = Rack.objects.get(id=rack.id)
        self.assert_(rack.locked)

    def test_new_racks_not_added_to_pending_order(self):
        bo, rack = self._make_bo_and_rack()
        bo.save()
        bo.submit()
        self.assertEqual(bo.racks.count(), 1)
        self.assertEqual(bo.status, 'pending')
        rack2 = Rack(location='POINT (7.0 7.0)', date=EPOCH)
        rack2.save()
        self.failIf(rack2 in set(bo.racks))
        self.failIf(rack2.locked)
        self.assertEqual(bo.racks.count(), 1)

    def test_deletion_unlocks_racks(self):
        bo, rack = self._make_bo_and_rack()
        bo.save()
        bo.approve()
        bo.delete()
        # re-load the rack to get new state.
        rack = Rack.objects.get(id=rack.id)
        self.failIf(rack.locked)


class TestNeighborhood(TestCase):

    def test_create_and_destroy(self):
        from fixcity.bmabr.models import Neighborhood
        nb = Neighborhood(
            gid=1, objectid=1, state='NY', borough='Brooklyn',
            name='Williamsburg',
            the_geom='POINT (0.0 0.0)',
            )
        nb.save()
        self.assertEqual(unicode(nb), u'Williamsburg')
        nb.delete()
