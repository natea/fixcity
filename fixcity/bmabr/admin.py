from .models import CityRack
from .models import EmailSource
from .models import NYCDOTBulkOrder
from .models import Rack, Neighborhood, CommunityBoard, Borough
from .models import SeeClickFixSource
from .models import Source
from .models import StatementOfSupport
from .models import TwitterSource
from attachments.admin import AttachmentInlines
from django.contrib import admin as oldAdmin
from django.contrib.gis import admin

class StatementOfSupportAdmin(admin.GeoModelAdmin):
    list_display = ('s_rack','email')

class StatementInline(oldAdmin.StackedInline):
    model = StatementOfSupport

# Use nice boolean graphics for these properties.
def _locked(rack):
    return rack.locked
_locked.boolean = True
_locked.short_description = 'Locked'

def _verified(rack):
    return rack.verified
_verified.boolean = True
_verified.short_description = 'Verified'


class RackAdmin(admin.GeoModelAdmin):

    list_display = ('id', 'address', 'location', 'date', 'user', 'email',
                    _verified, _locked, 'source')

class NeighborhoodAdmin(admin.GeoModelAdmin):
    list_display = ('name','borough')


class CommunityBoardAdmin(admin.GeoModelAdmin):
    list_display = ('borough','board','gid')
    ordering = ('borough','board')

class BoroughAdmin(admin.GeoModelAdmin):
    list_display = ('boroname',)


class NYCDOTBulkOrderAdmin(admin.ModelAdmin):
    inlines = [AttachmentInlines]
    list_display = ('communityboard', 'user', 'date', 'organization', 'status')


admin.site.register(StatementOfSupport, StatementOfSupportAdmin)
admin.site.register(Neighborhood, NeighborhoodAdmin)
admin.site.register(Rack, RackAdmin)
admin.site.register(CommunityBoard, CommunityBoardAdmin)
admin.site.register(Borough, BoroughAdmin)
admin.site.register(Source)
admin.site.register(SeeClickFixSource)
admin.site.register(EmailSource)
admin.site.register(TwitterSource)
admin.site.register(CityRack)
admin.site.register(NYCDOTBulkOrder, NYCDOTBulkOrderAdmin)

