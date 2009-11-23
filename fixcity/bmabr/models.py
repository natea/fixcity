from django.contrib.gis.db import models
from django.forms import ModelForm, ValidationError
from sorl.thumbnail.fields import ImageWithThumbnailsField 

RACK_IMAGE_LOCATION = 'images/racks/'

class CommunityBoard(models.Model):
    gid = models.IntegerField(primary_key=True)
    borocd = models.IntegerField()
    name = models.IntegerField()
    boro = models.CharField(max_length=50)
    the_geom = models.MultiPolygonField()
    objects = models.GeoManager()

    class Meta:
        db_table = u'gis_community_board'
        ordering = ['name']

    def __unicode__(self):
        return "Brooklyn Community Board %s " % self.name




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



class Comment(models.Model):
    text = models.CharField(max_length=300)
    email = models.EmailField()
    rack = models.ForeignKey(Rack)
    
    class Meta: 
        ordering = ['rack']

    def __unicode__(self):
        return self.email



class Neighborhoods(models.Model):
    gid = models.IntegerField(primary_key=True)
    state = models.CharField(max_length=2)
    county = models.CharField(max_length=43)
    city = models.CharField(max_length=64)
    name = models.CharField(max_length=64)
    regionid = models.IntegerField()
    the_geom = models.MultiPolygonField() 
    objects = models.GeoManager()

    class Meta:
        db_table = u'gis_neighborhoods'
        
    def __unicode__(self):
        return self.name


class SubwayStations(models.Model):
    gid = models.IntegerField(primary_key=True)
    objectid = models.TextField() # This field type is a guess.
    id = models.IntegerField()
    name = models.CharField(max_length=31)
    alt_name = models.CharField(max_length=38)
    cross_st = models.CharField(max_length=27)
    long_name = models.CharField(max_length=60)
    label = models.CharField(max_length=50)
    borough = models.CharField(max_length=15)
    nghbhd = models.CharField(max_length=30)
    routes = models.CharField(max_length=20)
    transfers = models.CharField(max_length=25)
    color = models.CharField(max_length=30)
    express = models.CharField(max_length=10)
    closed = models.CharField(max_length=10)
    the_geom = models.PointField()
    objects = models.GeoManager()
    class Meta:
        db_table = u'gis_subway_stations'



NEED_SOURCE_OR_EMAIL = "If email address is not provided, another source must be specified"

NEED_PHOTO_TO_VERIFY = "You can't mark a rack as verified unless it has a photo"


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

    def clean(self):
        cleaned_data = self.cleaned_data
        if self.is_bound and self.instance.source:
            return cleaned_data
        if cleaned_data.get('email') or cleaned_data.get('source'):
            return cleaned_data
        raise ValidationError(NEED_SOURCE_OR_EMAIL)


class CommentForm(ModelForm): 
    class Meta: 
        model = Comment
        

class SupportForm(ModelForm): 
    class Meta: 
        model = StatementOfSupport
