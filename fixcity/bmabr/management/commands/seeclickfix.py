# Parses the json output feed from seeclickfix and creates racks from results
# Expected to be run from cron at regular intervals

from datetime import datetime
from django.conf import settings
from django.contrib.gis.geos.point import Point
from django.core.mail import send_mail
from django.core.management.base import BaseCommand
from django.utils import simplejson as json
from pickle import dump
from pickle import load
from fixcity.bmabr.models import RACK_IMAGE_LOCATION
from fixcity.bmabr.models import Rack
from fixcity.bmabr.models import SeeClickFixSource
from fixcity.bmabr.views import SRID
import httplib2
import os
import time
import traceback

SEECLICKFIX_DOMAIN = 'http://www.seeclickfix.com'

def create_rack(json_data):
    """create a bike rack given json_data as returned by seeclickfix"""
    title = json_data['summary']
    address = json_data['address']
    description = json_data['description']
    date = create_datetime_from_jsonstring(json_data['created_at'])
    lat = json_data['lat']
    lng = json_data['lng']
    location = str(Point(lng, lat, srid=SRID))

    # seeclickfix source information
    issue_id = int(json_data['issue_id'])
    image_link = json_data.get('public_filename')
    if image_link is not None:
        image_url = generate_image_url(image_link)
    else:
        image_url = ''
    reporter = json_data.get('reporter_display', '')
    source = SeeClickFixSource(name='seeclickfix',
                               issue_id=issue_id,
                               reporter=reporter,
                               image_url=image_url,
                               )

    rack = Rack(title=title,
                description=description,
                address=address,
                date=date,
                location=location,
                source=source,
                )
    return rack

def generate_image_url(image_link):
    """generate an absolute seeclickfix url from a relative image url"""
    return SEECLICKFIX_DOMAIN + image_link

def fetch_feed(feed_url):
    """fetch a json feed from seeclick fix and load into a python object"""

    http = httplib2.Http()
    response, content = http.request(feed_url)
    assert response.status == 200, "Did not receive 200 response from seeclickfix"
    return json.loads(content)

def get_latest_pickle_path():
    return settings.SEECLICKFIX_STATUS_PATH

def get_latest_date_seen():
    curpath = os.path.abspath(__file__)
    dirname = os.path.dirname(curpath)
    pickle_path = get_latest_pickle_path()
    try:
        f = open(pickle_path)
        latest_date = load(f)
        f.close()
    except IOError:
        # use a date for racks that we haven't seen yet
        latest_date = datetime(2009, 1, 1)
    return latest_date

def set_latest_date_seen(date):
    """keep track of the latest date to avoid making repetitions"""
    pickle_path = get_latest_pickle_path()
    f = open(pickle_path, 'w')
    dump(date, f)
    f.close()

def create_datetime_from_jsonstring(s):
    """return a datetime object given a string in a seeclickfix format"""
    # you can simply do this with python 2.6
    #return datetime.strptime(s, '%m/%d/%Y at %I:%M%p')
    timeobj = time.strptime(s, '%m/%d/%Y at %I:%M%p')
    return datetime(*(timeobj[:5]))


def fetch_issue(issue_id):
    """given an issue id, fetch the json data for it

    this has some additional information we're interested in, like who the rack
    was submitted by and if it contains an image"""

    url = '%s/issues/%d.json' % (SEECLICKFIX_DOMAIN, issue_id)
    return fetch_feed(url)[0]

def retrieve_image_for(rack):
    """download the source's image from seeclickfix, if any and attach to rack"""
    image_url = rack.source.image_url
    if not image_url:
        return
    # saving it all in memory is easier
    # the images aren't going to be too huge to fit
    http = httplib2.Http()
    response, content = http.request(image_url)
    assert response.status == 200, "Error downloading image url: %s" % image_url
    from django.core.files.base import ContentFile
    from django.core.files.storage import default_storage
    content_file = ContentFile(content)
    image_name = image_url.split('/')[-1]
    #XXX put storage location in one spot
    filename = default_storage.save(RACK_IMAGE_LOCATION + image_name, content_file)
    filehandle = default_storage.open(filename)
    filehandle.open()
    rack.photo = filehandle


class Command(BaseCommand):

    def handle(self, *args, **options):
        try:
            feed_url = settings.SEECLICKFIX_JSON_URL
            json_data_list = fetch_feed(feed_url)
            latest_date_seen = get_latest_date_seen()
            racks_saved = []
            for json_data in json_data_list:
                date = create_datetime_from_jsonstring(json_data['created_at'])
                if date <= latest_date_seen:
                    continue
                issue_id = json_data['issue_id']
                issue_data = fetch_issue(issue_id)
                rack = create_rack(issue_data)
                # the source needs to have an id when it's assigned to a rack
                # for the correct link to the rack to be established
                # XXX transactional?
                retrieve_image_for(rack)
                source = rack.source
                source.save()
                rack.source = source
                rack.save()
                racks_saved.append(rack)
            latest = reduce(max, [x.date for x in racks_saved], latest_date_seen)
            set_latest_date_seen(latest)
        except Exception, e:
            # mail any failures
            mail_to = [settings.SERVICE_FAILURE_EMAIL]
            msg = str(e) + '\n\n' + traceback.format_exc()
            send_mail(u'Seeclickfix service error', msg,
                      'seeclickfix@fixcity.com', mail_to, fail_silently=False)
            # person receiving cron messages will get stdout
            print msg
