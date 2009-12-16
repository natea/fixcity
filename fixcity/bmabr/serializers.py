# use a custom json serializer for racks

from django.utils import simplejson as json
from django.core.serializers.json import DjangoJSONEncoder

def serialize_racks(racks):
    rack_structs = []
    for rack in racks:
        if rack.source:
            source = rack.source.name
        else:
            source = u'web'
        if rack.photo:
            photo = rack.photo.thumbnail.absolute_url
        else:
            photo = '/site_media/img/default-rack.jpg'
        date = DjangoJSONEncoder().default(rack.date)
        rack_structs.append(dict(title=rack.title,
                                 address=rack.address,
                                 date=date,
                                 description=rack.description,
                                 email=rack.email,
                                 verified=rack.verified,
                                 thumbnail=photo,
                                 source=source,
                                 ))
    return json.dumps(rack_structs)
