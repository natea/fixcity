from django.conf.urls.defaults import *

from django.conf import settings

# Uncomment the next two lines to enable the admin:
from django.contrib import admin
admin.autodiscover()

urlpatterns = patterns(
    '',
    (r'^$', 'fixcity.bmabr.views.index'),

    (r'^blank/$', 'fixcity.bmabr.views.blank_page'),

    # Account URL overrides.
    # Note these go first because django just iterates over these
    # patterns and uses the FIRST match.
    # XXX I think the auth application provides some generic passwd reset views
    # we could use? see http://www.stonemind.net/blog/2007/04/13/django-registration-for-newbies/
    (r'^accounts/activate/(?P<activation_key>\w+)/$', 'fixcity.bmabr.views.activate'),
    # Accounts URLs - anything for django-registration that we didn't override.
    (r'^accounts/', include('registration.urls')),

    (r'^profile/$', 'fixcity.bmabr.views.profile'),

    (r'^geocode/$', 'fixcity.bmabr.views.geocode'),
    (r'^reverse/$', 'fixcity.bmabr.views.reverse_geocode'),
    (r'^cbs/(?P<boro>\w+)/$', 'fixcity.bmabr.views.cbs_for_boro'),

    url(r'racks/$','fixcity.bmabr.views.racks_index', name='listracks'),

    (r'racks/communityboard/(?P<cb_id>\d+)/$', 'fixcity.bmabr.views.racks_by_communityboard'),


    (r'^racks/(?P<rack_id>\d+)/$', 'fixcity.bmabr.views.rack_view'),
    url(r'^racks/(?P<rack_id>\d+)/edit/$', 'fixcity.bmabr.views.rack_edit', name='editrack'),
    (r'^racks/(?P<rack_id>\d+)/support/$', 'fixcity.bmabr.views.support'),
    (r'^racks/(?P<rack_id>\d+)/votes/$', 'fixcity.bmabr.views.votes'),

     # KML URLs

    (r'racks/all.kml$', 'fixcity.bmabr.views.rack_all_kml'),
    (r'racks/requested.kml$', 'fixcity.bmabr.views.rack_requested_kml'),

    # Bulk order URLs
    (r'^bulk_order/(?P<bo_id>\d+)/order.csv/$', 'fixcity.bmabr.views.bulk_order_csv'),
    (r'^bulk_order/(?P<bo_id>\d+)/order.pdf/$', 'fixcity.bmabr.views.bulk_order_pdf'),
    (r'^bulk_order/(?P<bo_id>\d+)/order.zip/$', 'fixcity.bmabr.views.bulk_order_zip'),
    (r'^bulk_order/$', 'fixcity.bmabr.views.bulk_order_add_form'),
    (r'^bulk_order/(?P<bo_id>\d+)/approve/$', 'fixcity.bmabr.views.bulk_order_approval_form'),
    (r'^bulk_order/(?P<bo_id>\d+)/edit/$', 'fixcity.bmabr.views.bulk_order_edit_form'),

    (r'communityboard/(?P<cb_id>\d+).kml','fixcity.bmabr.views.community_board_kml'),
    (r'borough/(?P<boro_id>\d+).kml', 'fixcity.bmabr.views.borough_kml'),
    (r'^cityracks.kml$', 'fixcity.bmabr.views.cityracks_kml'),

    # different views for adding infomation, rack, comments, photos.

    url(r'^racks/new/$', 'fixcity.bmabr.views.newrack_form', name='newrack'),
    (r'^racks/(?P<rack_id>\d+)/photos/$', 'fixcity.bmabr.views.updatephoto'),

    # redirect old /rack/ urls
    (r'^rack/', 'fixcity.bmabr.views.redirect_rack_urls'),

    # Static media for dev work.  For deployment, these should be served
    # by a front-end server eg. apache!
    # see http://docs.djangoproject.com/en/dev/howto/static-files/
    (r'^site_media/(?P<path>.*)$', 'django.views.static.serve',
      {'document_root': settings.STATIC_DOC_ROOT, 'show_indexes': True}),
    (r'^uploads/(?P<path>.*)$', 'django.views.static.serve',
      {'document_root': settings.MEDIA_ROOT, 'show_indexes': True}),

    # Uncomment the admin/doc line below and add 'django.contrib.admindocs' 
    # to INSTALLED_APPS to enable admin documentation:
    # (r'^admin/doc/', include('django.contrib.admindocs.urls')),
    (r'^admin/(.*)', admin.site.root),

    (r'^blog/', include('basic.blog.urls')),

    (r'^comments/', include('django.contrib.comments.urls')),

    (r'^attachments/', include('attachments.urls')),

)

handler500 = 'fixcity.bmabr.views.server_error'
