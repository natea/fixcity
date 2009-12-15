from django.contrib.gis import admin
from django.contrib import admin as oldAdmin 
from fixcity.bmabr.models import Rack, CommunityBoard
from fixcity.bmabr.models import SeeClickFixSource
from fixcity.bmabr.models import Source
from fixcity.bmabr.models import EmailSource
from fixcity.bmabr.models import TwitterSource
from fixcity.bmabr.models import  StatementOfSupport


class StatementOfSupportAdmin(admin.GeoModelAdmin): 
    list_display = ('s_rack','email') 
admin.site.register(StatementOfSupport,StatementOfSupportAdmin)


class StatementInline(oldAdmin.StackedInline): 
    model = StatementOfSupport

class RackAdmin(admin.GeoModelAdmin): 
    list_display = ('address','location')
admin.site.register(Rack, RackAdmin)


class CommunityBoardAdmin(admin.GeoModelAdmin): 
    list_display = ('boro','board','gid')
    ordering = ('boro',)
admin.site.register(CommunityBoard,CommunityBoardAdmin)

admin.site.register(Source)
admin.site.register(SeeClickFixSource)
admin.site.register(EmailSource)
admin.site.register(TwitterSource)
