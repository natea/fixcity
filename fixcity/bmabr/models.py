from django.contrib.gis.db import models
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
        return "%s Community Board %s " % (self.borough.boroname, self.board)


class Rack(models.Model):
    address = models.CharField(max_length=200)
    title = models.CharField(max_length=140)
    date = models.DateTimeField()
    description = models.CharField(max_length=300, blank=True)
    email = models.EmailField(blank=True)
    photo = ImageWithThumbnailsField(
                              upload_to=RACK_IMAGE_LOCATION,
                              thumbnail={'size': (100, 100)},
                              extra_thumbnails = {
                                   'large': {'size': (400,400)},
                                },
                              blank=True, null=True)
    # We might make this a foreign key to a User eventually, but for now
    # it's optional.
    user = models.CharField(max_length=20, blank=True)
    location = models.PointField(srid=4326)

    verified = models.BooleanField(default=False, blank=True)

    # keep track of where the rack was submitted from
    # if not set, that means it was submitted from the web
    source = models.ForeignKey('Source', null=True, blank=True)

    objects = models.GeoManager()

    def __unicode__(self):
        return self.address

    def get_absolute_url(self):
        return '/rack/%s' % self.id

    def get_thumbnail_url(self):
        if self.photo:
            return self.photo.thumbnail
        else:
            return '/site_media/img/default-rack.jpg'

    def get_source(self):
        if self.source:
            return self.source.name
        else:
            return u'web'

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


class Borough(models.Model):
    gid = models.IntegerField(primary_key=True)
    borocode = models.SmallIntegerField()
    boroname = models.CharField(max_length=32)
    shape_leng = models.DecimalField(max_digits=65535, decimal_places=65535)
    shape_area = models.DecimalField(max_digits=65535, decimal_places=65535)
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

class RackForm(ModelForm):
    class Meta:
        model = Rack

    def clean_verified(self):
        verified = self.cleaned_data.get('verified')
        errors = []
        if verified:
            if not (self.cleaned_data.get('photo') or (
                self.is_bound and bool(self.instance.photo))):
                raise ValidationError(NEED_PHOTO_TO_VERIFY)
        return verified

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


class SupportForm(ModelForm):
    class Meta:
        model = StatementOfSupport
