from django.contrib.gis import admin
from fixcity.bmabr.models import Rack, Comment, Neighborhoods, CommunityBoard, SubwayStations
from django.contrib import admin as oldAdmin
from fixcity.bmabr.models import SeeClickFixSource
from fixcity.bmabr.models import Source
from fixcity.bmabr.models import EmailSource
from fixcity.bmabr.models import TwitterSource
from fixcity.bmabr.models import  StatementOfSupport


class StatementOfSupportAdmin(admin.GeoModelAdmin):
    list_display = ('s_rack','email')

class StatementInline(oldAdmin.StackedInline):
    model = StatementOfSupport

class SubwayAdmin(admin.GeoModelAdmin):
    list_display = ('name','borough')
    search_fields = ('name','borough')

class CommentAdmin(admin.GeoModelAdmin):
    list_display = ('rack','email')

class RackAdmin(admin.GeoModelAdmin):
    list_display = ('address','location')

class NeighborhoodsAdmin(admin.GeoModelAdmin):
    list_display = ('name','county')

class CommunityBoardAdmin(admin.GeoModelAdmin):
    list_display = ('boro','board','gid')
    ordering = ('boro',)

admin.site.register(SubwayStations, SubwayAdmin)
admin.site.register(StatementOfSupport, StatementOfSupportAdmin)
admin.site.register(Neighborhoods, NeighborhoodsAdmin)
admin.site.register(Comment, CommentAdmin)
admin.site.register(Rack, RackAdmin)
admin.site.register(CommunityBoard, CommunityBoardAdmin)
admin.site.register(Source)
admin.site.register(SeeClickFixSource)
admin.site.register(EmailSource)
admin.site.register(TwitterSource)
