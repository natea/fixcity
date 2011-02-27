"""
Civic API bikerack sync
"""

from couchdb import Server
from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import simplejson as json
from fixcity.bmabr.models import Rack
import logging

logger = logging.getLogger('civicapisync')

def _rack_to_geojson(rack):
    # a new rack
    doc = {
        'type': 'Feature',
        'geometry': json.loads(rack.location.geojson),
        'properties': {
            # XXX ...
        }
    }
    return doc


def do_push():
    # very crappy first pass at sync with Civic API
    
    # Note this will cease to update items that 
    # no longer exist on the remote end and it 
    # will always defer to the remote end if there
    # is a change there.
    # this does not send any extended metadata, just 
    # the geometry.
    

    server = Server(settings.CIVIC_API_SERVER)
    db = server[settings.CIVIC_API_DATABASE]

    batch_size = 100

    def _update(rs):
        """
        helper to update a batch of racks that have already been 
        pushed civic api at some point in the past.  
        rs - dict mapping civic_api_id -> bmabr.models.Rack
        """
        updates = []
        # pull current state from civic api
        cur_docs = db.view('_all_docs', keys=rs.keys(), include_docs=True)
        for row in cur_docs:
            doc = row.get('doc')
            if doc is None: 
                logger.warning("Rack %s no longer exists on remote end." % row.id)
                continue
            rack = rs.get(doc['_id'])
            
            # conflict, defer to civic api
            # and update our database
            if rack.civic_api_rev != doc['_rev']: 
                # pull metadata, currently geom only
                rack.location = json.dumps(doc['geometry'])
                rack.civic_api_rev = doc['_rev']
                rack.save()
                logger.info("Took update of %s from Civic API" % rack.civic_api_id)
            else: 
                # push our metadata
                # XXX check other fields for change, this 
                # is also possibly unstable.
                new_geom = json.loads(rack.location.geojson)
                if new_geom != doc['geometry']: 
                    doc['geometry'] = new_geom 
                    updates.append(doc)
        if len(updates): 
            for success, cid, rev_or_exc in db.update(updates):
                if success == False:
                    logger.error("Failed to update rack %s" % cid)
                else: 
                    rack = rs[cid]
                    rack.civic_api_rev = rev_or_exc
                    rack.save()
                    logger.info("Pushed update of %s to Civic API" % rack.civic_api_id)
    # pull in current state of CivicAPI racks
    # that we manage and update them in batches
    #
    # XXX just select the racks that have a non-null 
    # civic_api_id
    pracks = {}
    for rack in Rack.objects.exclude(civic_api_id__exact='').all():
        if rack.civic_api_id:
            pracks[rack.civic_api_id] = rack
        if len(pracks) >= batch_size:
            _update(pracks)
            pracks = {}
    if len(pracks):
        _update(pracks)

    def _create(docs, rs):
        """
        helper to create a batch of racks
        docs - list of couchdb docs
        rs - list of bmabr.models.Rack corresponding to docs
        """
        for i, (success, cid, rev_or_exc) in enumerate(db.update(docs)):
            if success == False: 
                logger.error("Failed to push rack to Civic API: %s" % rev_or_exc)
            else: 
                rs[i].civic_api_id = cid
                rs[i].civic_api_rev = rev_or_exc
                rs[i].save()
                logger.info("Pushed new rack %s to Civic API" % cid)

    # create new racks in batches
    creates = []
    racks = []    
    for rack in Rack.objects.filter(civic_api_id__exact=''):
        creates.append(_rack_to_geojson(rack))
        racks.append(rack)
        if len(creates) >= batch_size:
            _create(creates, racks)
            creates = []
            racks = []
    if len(creates):
        _create(creates, racks)

class Command(BaseCommand):

    def handle(self, *args, **options):
        do_push()
