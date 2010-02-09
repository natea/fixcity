from django.contrib.gis.db import models
from django.contrib.auth.models import User
from django.forms import ModelForm, ValidationError
from sorl.thumbnail.fields import ImageWithThumbnailsField

RACK_IMAGE_LOCATION = 'images/racks/'


class CommunityBoard(models.Model):
    gid = models.IntegerField(primary_key=True)
    borocd = models.IntegerField()
    board = models.IntegerField()
    borough = models.ForeignKey('Borough')
    the_geom = models.MultiPolygonField()
    objects = models.GeoManager()

    class Meta:
        db_table = u'gis_community_board'
        ordering = ['board']

    def __unicode__(self):
        return "%s Community Board %s" % (self.borough.boroname, self.board)

    @property
    def racks(self):
        return Rack.objects.filter(location__intersects=self.the_geom)



class Rack(models.Model):
    address = models.CharField(max_length=200)
    title = models.CharField(max_length=140)
    date = models.DateTimeField()
    description = models.CharField(max_length=300, blank=True)
    email = models.EmailField(blank=True)
    photo = ImageWithThumbnailsField(
        upload_to=RACK_IMAGE_LOCATION,
        thumbnail={'size': (100, 100)},
        extra_thumbnails={'large': {'size': (400,400)},},
        blank=True, null=True)
    # We might make this a foreign key to a User eventually, but for now
    # it's optional.
    user = models.CharField(max_length=20, blank=True)
    location = models.PointField(srid=4326)

    verified = models.BooleanField(default=False, blank=True)
    # these represent the parts of a rack that need to be marked for a rack to
    # be marked as verified/complete
    verify_surface = models.BooleanField(default=False, blank=True)
    verify_objects = models.BooleanField(default=False, blank=True)
    verify_access = models.BooleanField(default=False, blank=True)

    # keep track of where the rack was submitted from
    # if not set, that means it was submitted from the web
    source = models.ForeignKey('Source', null=True, blank=True)

    bulk_orders = models.ManyToManyField('NYCDOTBulkOrder', null=True, blank=True)


    objects = models.GeoManager()

    def __unicode__(self):
        return self.address

    def get_absolute_url(self):
        return '/racks/%s/' % self.id

    def get_thumbnail_url(self):
        if self.photo:
            return self.photo.thumbnail
        else:
            return '/site_media/img/default-rack.jpg'

    def get_source(self):
        """ how did this rack get submitted? """
        if self.source:
            return self.source.name
        else:
            return u'web'

    @property
    def locked(self):
        return bool(self.bulk_orders.count())


class Source(models.Model):
    """base class representing the source of where a rack was submitted from"""

    # this uses multi-table inheritance, see
    # http://docs.djangoproject.com/en/dev/topics/db/models/#multi-table-inheritance

    # string based name used to identify where a source came from,
    # eg. 'twitter', 'email', etc.
    name = models.CharField(max_length=20)

    def __unicode__(self):
        return self.name

    def get_child_source(self):
        """Try to get a more specific subclass instance."""
        if self.name:
            # If it's a twittersource, emailsource, etc., we'll look
            # that up via the child link that Django generates with
            # multi-table inheritance.
            try:
                return getattr(self, self.name + 'source')
            except AttributeError:
                pass

class EmailSource(Source):
    address = models.EmailField()

    def __unicode__(self):
        return self.address

class TwitterSource(Source):
    user = models.CharField(max_length=50)
    status_id = models.CharField(max_length=32)

    def get_absolute_url(self):
        user = self.user
        status_id = self.status_id
        return 'http://twitter.com/%(user)s/%(status_id)d' % locals()

    def __unicode__(self):
        return self.get_absolute_url().decode('utf-8')


class SeeClickFixSource(Source):
    issue_id = models.IntegerField()
    reporter = models.CharField(max_length=100)
    image_url = models.URLField()

    def get_absolute_url(self):
        return 'http://www.seeclickfix.com/issues/%d' % self.issue_id

    def __unicode__(self):
        return self.get_absolute_url().decode('utf-8')


class StatementOfSupport(models.Model):
    file = models.FileField(upload_to='documents/', blank=True, null=True)
    email = models.EmailField()
    s_rack = models.ForeignKey(Rack)

    class Meta:
        ordering = ['s_rack']

    def __unicode__(self):
        return self.email


class Neighborhood(models.Model):

    gid = models.IntegerField(primary_key=True)
    objectid = models.IntegerField()
    name = models.CharField(max_length=100, null=False)

    borough = models.CharField(max_length=50)
    city = models.CharField(max_length=50, default='New York City')
    state = models.CharField(max_length=2, null=True, default='NY')

    the_geom = models.PointField(srid=4326)

    objects = models.GeoManager()

    class Meta:
        db_table = u'gis_neighborhoods'
        
    def __unicode__(self):
        return self.name

class Borough(models.Model):
    gid = models.IntegerField(primary_key=True)
    borocode = models.SmallIntegerField()
    boroname = models.CharField(max_length=32)
    shape_leng = models.DecimalField(max_digits=1000, decimal_places=100)
    shape_area = models.DecimalField(max_digits=1000, decimal_places=100)
    the_geom = models.MultiPolygonField()
    objects = models.GeoManager()
    class Meta:
        db_table = u'gis_boroughs'

    def __unicode__(self):
        return self.boroname

    @classmethod
    def brooklyn(cls):
        """ convenience method to return the brooklyn borough """
        return cls.objects.get(gid=4)

NEED_SOURCE_OR_EMAIL = "If email address is not provided, another source must be specified"

NEED_PHOTO_TO_VERIFY = "You can't mark a rack as verified unless it has a photo"
NEED_LOGGEDIN_OR_EMAIL = "Email is required if you're not logged in."

class CityRack(models.Model):
    gid = models.IntegerField(primary_key=True)
    objectid = models.DecimalField(max_digits=1000, decimal_places=100)
    address = models.DecimalField(max_digits=1000, decimal_places=100)
    street_nam = models.CharField(max_length=31)
    zip_code_1 = models.CharField(max_length=12)
    from__cros = models.CharField(max_length=22)
    to__cross = models.CharField(max_length=22)
    boro_1 = models.CharField(max_length=8)
    neighborho = models.CharField(max_length=21)
    side_of_st = models.CharField(max_length=12)
    small = models.IntegerField()
    large = models.IntegerField()
    alt_addres = models.CharField(max_length=31)
    x = models.DecimalField(max_digits=1000, decimal_places=100)
    y = models.DecimalField(max_digits=1000, decimal_places=100)
    id = models.CharField(max_length=13)
    oppaddress = models.DecimalField(max_digits=1000, decimal_places=100)
    borocode = models.DecimalField(max_digits=1000, decimal_places=100)
    c_racksid = models.CharField(max_length=17)
    rackid = models.CharField(max_length=50)
    the_geom = models.PointField()
    objects = models.GeoManager()
    class Meta:
        db_table = u'gis_cityracks'


class NYCDOTBulkOrder(models.Model):
    """
    bulk orders for NYC bike racks
    """

    communityboard = models.ForeignKey(CommunityBoard)
    user = models.ForeignKey(User)
    date = models.DateTimeField(auto_now=True)
    organization = models.CharField(max_length=128, blank=False, null=True)
    rationale = models.TextField(blank=False, null=True)

    status_choices = (
        ('new', 'New'),
        ('approved', 'Approved for Submission'),
        ('pending', 'Pending Approval by DOT'),
        ('completed', 'Completed'),
        )

    status = models.TextField(null=False, blank=True, choices=status_choices,
                              default=status_choices[0][0])

    def __unicode__(self):
        return u'Bulk order for %s' % self.communityboard

    def submit(self):
        for rack in self.communityboard.racks:
            rack.bulk_orders.add(self)
            rack.save()
        self.status = 'pending'
        self.save()

    def approve(self):
        # xxx convenience, can go away
        self.status = 'approved'
        self.save()

    def delete(self, *args, **kw):
        self.rack_set.clear()
        super(NYCDOTBulkOrder, self).delete(*args, **kw)

    @property
    def racks(self):
        # WHen not submitted yet, we want all racks in the CB.  When
        # submitted, we want to freeze the racks from the CB at that
        # time.
        if self.status in ('new', 'approved'):
            return self.communityboard.racks
        return self.rack_set.all() #filter(bulk_orders.=self)

        

class NYCStreet(models.Model):

    # A small subset of the NYC streets database schema
    # ... maybe not even needed.
    # converted from http://www.nyc.gov/html/dcp/html/bytes/dwnlion.shtml

    gid = models.IntegerField(primary_key=True)
    street = models.CharField(max_length=35)
    nodeidfrom = models.CharField(max_length=7)
    nodeidto = models.CharField(max_length=7)
    zipleft = models.CharField(max_length=5)
    the_geom = models.MultiLineStringField()

    objects = models.GeoManager()

    class Meta:
        db_table = u'gis_nycstreets'


class BulkOrderForm(ModelForm):
    class Meta:
        model = NYCDOTBulkOrder

    def clean_status(self):
        status = self.cleaned_data.get('status')
        if not status:
            status = NYCDOTBulkOrder.status_choices[0][0]
        return status
        


class SupportForm(ModelForm):
    class Meta:
        model = StatementOfSupport


class RackForm(ModelForm):
    class Meta:
        model = Rack

    def clean_photo(self):
        photo = self.cleaned_data.get('photo')
        if not photo:
            return photo
        from fixcity.exif_utils import rotate_image_by_exif
        from PIL import Image
        img = Image.open(photo)
        rotated = rotate_image_by_exif(img)
        if not (rotated is img):
            photo.seek(0)
            rotated.save(photo)
        return photo

    def clean(self):
        from django.forms.util import ErrorList
        cleaned_data = self.cleaned_data

        # dynamically calculate the verified status from the requirements
        if self.is_bound:
            if (cleaned_data['verify_access'] and
                cleaned_data['verify_surface'] and
                cleaned_data['verify_objects']):
                cleaned_data['verified'] = True
            else:
                cleaned_data['verified'] = False

        if self.is_bound and self.instance.source:
            return cleaned_data
        if cleaned_data.get('email') or cleaned_data.get('source'):
            return cleaned_data
        email_errors = self._errors.get('email')
        if not email_errors and not cleaned_data.get('source'):
            # Assume this is submitted via the web and the user isn't logged in.
            # So, provide a helpful error message in the email field.
            #
            # This is the canonical way to associate an error msg with
            # a specific field when depending on other fields, as per
            # http://docs.djangoproject.com/en/dev/ref/forms/validation/#described-later
            self._errors['email'] = ErrorList([NEED_LOGGEDIN_OR_EMAIL])

        # This more general error is intended to be useful to script
        # authors integrating third-party rack sources, so they'll
        # know if they forgot the 'source' field.
        # It goes in errors.__all__ so it isn't shown on our web UI.
        raise ValidationError(NEED_SOURCE_OR_EMAIL)
