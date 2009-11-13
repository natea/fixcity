# Parses the json output feed from seeclickfix and creates racks from results
# Expected to be run from cron at regular intervals

from datetime import datetime
from django.contrib.gis.geos.point import Point
from django.core.management.base import BaseCommand
from fixcity.bmabr.models import Rack
from fixcity.bmabr.views import SRID

def create_rack(json_data):
    """create a bike rack given json_data as returned by seeclickfix"""
    title = json_data['summary']
    address = json_data['address']
    description = json_data['description']
    date = create_datetime_from_jsonstring(json_data['created_at'])
    # skip photo for now
    lat = json_data['lat']
    lng = json_data['lng']
    location = str(Point(lng, lat, srid=SRID))
    # XXX how do we handle user?
    user = u'seeclickfix'
    rack = Rack(title=title,
                description=description,
                address=address,
                date=date,
                user=user,
                location=location,
                )
    return rack

def fetch_feed(feed_url):
    #XXX for now just stub it out for testing
    return [{"rating":1,"description":"I need a bike rack for my mobster fixie crew.","page":1,"lat":40.7172736790292,"object_id":"issue9738","address":"1315 Grand St, New York, NY 11211","lng":-73.9256286621094,"summary":"Junkyard bike rack","issue_id":9738,"id":"issue9738","created_at":"11/12/2009 at 05:45PM","updated_at_raw":"2009/11/12 17:45:36 -0500","status":"Open","updated_at":"11/12/2009 at 05:45PM"}]

def get_latest_date_seen():
    #XXX need to fill this in
    return datetime(2009, 1, 1)

def set_latest_date_seen(date):
    """keep track of the latest date to avoid making repetitions"""

def create_datetime_from_jsonstring(s):
    """return a datetime object given a string in a seeclickfix format"""
    return datetime.strptime(s, '%m/%d/%Y at %I:%M%p')


class Command(BaseCommand):

    def handle(self, *args, **options):
        #XXX fix feed_url
        feed_url = ''
        json_data_list = fetch_feed(feed_url)
        latest_date_seen = get_latest_date_seen()
        racks_saved = []
        for json_data in json_data_list:
            date = create_datetime_from_jsonstring(json_data['created_at'])
            if date < latest_date_seen:
                continue
            rack = create_rack(json_data)
            rack.save()
            racks_saved.append(rack)
        latest = reduce(max, [x.date for x in racks_saved], latest_date_seen)
        set_latest_date_seen(latest)
