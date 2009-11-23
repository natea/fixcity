from django.contrib.gis import admin
from django.contrib import admin as oldAdmin 
from fixcity.bmabr.models import Rack, Comment, Neighborhoods, CommunityBoard, SubwayStations
from fixcity.bmabr.models import SeeClickFixSource
from fixcity.bmabr.models import Source
from fixcity.bmabr.models import EmailSource
from fixcity.bmabr.models import TwitterSource
from fixcity.bmabr.models import  StatementOfSupport


#class PhotoAdmin(admin.GeoModelAdmin): 
#    list_display  = ('rack','email') 
#admin.site.register(Photo,PhotoAdmin)


class StatementOfSupportAdmin(admin.GeoModelAdmin): 
    list_display = ('s_rack','email') 
admin.site.register(StatementOfSupport,StatementOfSupportAdmin)


class StatementInline(oldAdmin.StackedInline): 
    model = StatementOfSupport

class SubwayAdmin(admin.GeoModelAdmin): 
    list_display = ('name','borough')
    search_fields = ('name','borough')
admin.site.register(SubwayStations,SubwayAdmin)

class CommentAdmin(admin.GeoModelAdmin): 
    list_display = ('rack','email')
admin.site.register(Comment,CommentAdmin)

class RackAdmin(admin.GeoModelAdmin): 
    list_display = ('address','location')
admin.site.register(Rack, RackAdmin)


class NeighborhoodsAdmin(admin.GeoModelAdmin): 
    list_display = ('name','county')
admin.site.register(Neighborhoods,NeighborhoodsAdmin)


class CommunityBoardAdmin(admin.GeoModelAdmin): 
    list_display = ('boro','name','gid')
    ordering = ('boro',)
admin.site.register(CommunityBoard,CommunityBoardAdmin)

admin.site.register(Source)
admin.site.register(SeeClickFixSource)
admin.site.register(EmailSource)
admin.site.register(TwitterSource)
