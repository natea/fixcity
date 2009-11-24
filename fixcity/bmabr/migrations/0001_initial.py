
from south.db import db
from django.db import models
from fixcity.bmabr.models import *

class Migration:
    
    def forwards(self, orm):
        
        # Adding model 'StatementOfSupport'
        db.create_table('bmabr_statementofsupport', (
            ('id', orm['bmabr.StatementOfSupport:id']),
            ('file', orm['bmabr.StatementOfSupport:file']),
            ('email', orm['bmabr.StatementOfSupport:email']),
            ('s_rack', orm['bmabr.StatementOfSupport:s_rack']),
        ))
        db.send_create_signal('bmabr', ['StatementOfSupport'])
        
        # Adding model 'EmailSource'
        db.create_table('bmabr_emailsource', (
            ('source_ptr', orm['bmabr.EmailSource:source_ptr']),
            ('address', orm['bmabr.EmailSource:address']),
        ))
        db.send_create_signal('bmabr', ['EmailSource'])
        
        # Adding model 'Source'
        db.create_table('bmabr_source', (
            ('id', orm['bmabr.Source:id']),
            ('name', orm['bmabr.Source:name']),
        ))
        db.send_create_signal('bmabr', ['Source'])
        
        # Adding model 'CommunityBoard'
        db.create_table(u'gis_community_board', (
            ('gid', orm['bmabr.CommunityBoard:gid']),
            ('borocd', orm['bmabr.CommunityBoard:borocd']),
            ('name', orm['bmabr.CommunityBoard:name']),
            ('the_geom', orm['bmabr.CommunityBoard:the_geom']),
        ))
        db.send_create_signal('bmabr', ['CommunityBoard'])
        
        # Adding model 'Rack'
        db.create_table('bmabr_rack', (
            ('id', orm['bmabr.Rack:id']),
            ('address', orm['bmabr.Rack:address']),
            ('title', orm['bmabr.Rack:title']),
            ('date', orm['bmabr.Rack:date']),
            ('description', orm['bmabr.Rack:description']),
            ('email', orm['bmabr.Rack:email']),
            ('photo', orm['bmabr.Rack:photo']),
            ('user', orm['bmabr.Rack:user']),
            ('location', orm['bmabr.Rack:location']),
            ('verified', orm['bmabr.Rack:verified']),
            ('source', orm['bmabr.Rack:source']),
        ))
        db.send_create_signal('bmabr', ['Rack'])
        
        # Adding model 'SeeClickFixSource'
        db.create_table('bmabr_seeclickfixsource', (
            ('source_ptr', orm['bmabr.SeeClickFixSource:source_ptr']),
            ('issue_id', orm['bmabr.SeeClickFixSource:issue_id']),
            ('reporter', orm['bmabr.SeeClickFixSource:reporter']),
            ('image_url', orm['bmabr.SeeClickFixSource:image_url']),
        ))
        db.send_create_signal('bmabr', ['SeeClickFixSource'])
        
        # Adding model 'Neighborhoods'
        db.create_table(u'gis_neighborhoods', (
            ('gid', orm['bmabr.Neighborhoods:gid']),
            ('state', orm['bmabr.Neighborhoods:state']),
            ('county', orm['bmabr.Neighborhoods:county']),
            ('city', orm['bmabr.Neighborhoods:city']),
            ('name', orm['bmabr.Neighborhoods:name']),
            ('regionid', orm['bmabr.Neighborhoods:regionid']),
            ('the_geom', orm['bmabr.Neighborhoods:the_geom']),
        ))
        db.send_create_signal('bmabr', ['Neighborhoods'])
        
        # Adding model 'Comment'
        db.create_table('bmabr_comment', (
            ('id', orm['bmabr.Comment:id']),
            ('text', orm['bmabr.Comment:text']),
            ('email', orm['bmabr.Comment:email']),
            ('rack', orm['bmabr.Comment:rack']),
        ))
        db.send_create_signal('bmabr', ['Comment'])
        
        # Adding model 'SubwayStations'
        db.create_table(u'gis_subway_stations', (
            ('gid', orm['bmabr.SubwayStations:gid']),
            ('objectid', orm['bmabr.SubwayStations:objectid']),
            ('id', orm['bmabr.SubwayStations:id']),
            ('name', orm['bmabr.SubwayStations:name']),
            ('alt_name', orm['bmabr.SubwayStations:alt_name']),
            ('cross_st', orm['bmabr.SubwayStations:cross_st']),
            ('long_name', orm['bmabr.SubwayStations:long_name']),
            ('label', orm['bmabr.SubwayStations:label']),
            ('borough', orm['bmabr.SubwayStations:borough']),
            ('nghbhd', orm['bmabr.SubwayStations:nghbhd']),
            ('routes', orm['bmabr.SubwayStations:routes']),
            ('transfers', orm['bmabr.SubwayStations:transfers']),
            ('color', orm['bmabr.SubwayStations:color']),
            ('express', orm['bmabr.SubwayStations:express']),
            ('closed', orm['bmabr.SubwayStations:closed']),
            ('the_geom', orm['bmabr.SubwayStations:the_geom']),
        ))
        db.send_create_signal('bmabr', ['SubwayStations'])
        
        # Adding model 'TwitterSource'
        db.create_table('bmabr_twittersource', (
            ('source_ptr', orm['bmabr.TwitterSource:source_ptr']),
            ('user', orm['bmabr.TwitterSource:user']),
            ('status_id', orm['bmabr.TwitterSource:status_id']),
        ))
        db.send_create_signal('bmabr', ['TwitterSource'])
        
    
    
    def backwards(self, orm):
        
        # Deleting model 'StatementOfSupport'
        db.delete_table('bmabr_statementofsupport')
        
        # Deleting model 'EmailSource'
        db.delete_table('bmabr_emailsource')
        
        # Deleting model 'Source'
        db.delete_table('bmabr_source')
        
        # Deleting model 'CommunityBoard'
        db.delete_table(u'gis_community_board')
        
        # Deleting model 'Rack'
        db.delete_table('bmabr_rack')
        
        # Deleting model 'SeeClickFixSource'
        db.delete_table('bmabr_seeclickfixsource')
        
        # Deleting model 'Neighborhoods'
        db.delete_table(u'gis_neighborhoods')
        
        # Deleting model 'Comment'
        db.delete_table('bmabr_comment')
        
        # Deleting model 'SubwayStations'
        db.delete_table(u'gis_subway_stations')
        
        # Deleting model 'TwitterSource'
        db.delete_table('bmabr_twittersource')
        
    
    
    models = {
        'bmabr.comment': {
            'email': ('django.db.models.fields.EmailField', [], {'max_length': '75'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'rack': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['bmabr.Rack']"}),
            'text': ('django.db.models.fields.CharField', [], {'max_length': '300'})
        },
        'bmabr.communityboard': {
            'Meta': {'db_table': "u'gis_community_board'"},
            'borocd': ('django.db.models.fields.IntegerField', [], {}),
            'gid': ('django.db.models.fields.IntegerField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '10'}),
            'the_geom': ('django.contrib.gis.db.models.fields.MultiPolygonField', [], {})
        },
        'bmabr.emailsource': {
            'address': ('django.db.models.fields.EmailField', [], {'max_length': '75'}),
            'source_ptr': ('django.db.models.fields.related.OneToOneField', [], {'to': "orm['bmabr.Source']", 'unique': 'True', 'primary_key': 'True'})
        },
        'bmabr.neighborhoods': {
            'Meta': {'db_table': "u'gis_neighborhoods'"},
            'city': ('django.db.models.fields.CharField', [], {'max_length': '64'}),
            'county': ('django.db.models.fields.CharField', [], {'max_length': '43'}),
            'gid': ('django.db.models.fields.IntegerField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '64'}),
            'regionid': ('django.db.models.fields.IntegerField', [], {}),
            'state': ('django.db.models.fields.CharField', [], {'max_length': '2'}),
            'the_geom': ('django.contrib.gis.db.models.fields.MultiPolygonField', [], {})
        },
        'bmabr.rack': {
            'address': ('django.db.models.fields.CharField', [], {'max_length': '200'}),
            'date': ('django.db.models.fields.DateTimeField', [], {}),
            'description': ('django.db.models.fields.CharField', [], {'max_length': '300', 'blank': 'True'}),
            'email': ('django.db.models.fields.EmailField', [], {'max_length': '75', 'blank': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'location': ('django.contrib.gis.db.models.fields.PointField', [], {}),
            'photo': ('django.db.models.fields.files.ImageField', [], {'max_length': '100', 'null': 'True', 'blank': 'True'}),
            'source': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['bmabr.Source']", 'null': 'True', 'blank': 'True'}),
            'title': ('django.db.models.fields.CharField', [], {'max_length': '140'}),
            'user': ('django.db.models.fields.CharField', [], {'max_length': '20', 'blank': 'True'}),
            'verified': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'blank': 'True'})
        },
        'bmabr.seeclickfixsource': {
            'image_url': ('django.db.models.fields.URLField', [], {'max_length': '200'}),
            'issue_id': ('django.db.models.fields.IntegerField', [], {}),
            'reporter': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'source_ptr': ('django.db.models.fields.related.OneToOneField', [], {'to': "orm['bmabr.Source']", 'unique': 'True', 'primary_key': 'True'})
        },
        'bmabr.source': {
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '20'})
        },
        'bmabr.statementofsupport': {
            'email': ('django.db.models.fields.EmailField', [], {'max_length': '75'}),
            'file': ('django.db.models.fields.files.FileField', [], {'max_length': '100', 'null': 'True', 'blank': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            's_rack': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['bmabr.Rack']"})
        },
        'bmabr.subwaystations': {
            'Meta': {'db_table': "u'gis_subway_stations'"},
            'alt_name': ('django.db.models.fields.CharField', [], {'max_length': '38'}),
            'borough': ('django.db.models.fields.CharField', [], {'max_length': '15'}),
            'closed': ('django.db.models.fields.CharField', [], {'max_length': '10'}),
            'color': ('django.db.models.fields.CharField', [], {'max_length': '30'}),
            'cross_st': ('django.db.models.fields.CharField', [], {'max_length': '27'}),
            'express': ('django.db.models.fields.CharField', [], {'max_length': '10'}),
            'gid': ('django.db.models.fields.IntegerField', [], {'primary_key': 'True'}),
            'id': ('django.db.models.fields.IntegerField', [], {}),
            'label': ('django.db.models.fields.CharField', [], {'max_length': '50'}),
            'long_name': ('django.db.models.fields.CharField', [], {'max_length': '60'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '31'}),
            'nghbhd': ('django.db.models.fields.CharField', [], {'max_length': '30'}),
            'objectid': ('django.db.models.fields.TextField', [], {}),
            'routes': ('django.db.models.fields.CharField', [], {'max_length': '20'}),
            'the_geom': ('django.contrib.gis.db.models.fields.PointField', [], {}),
            'transfers': ('django.db.models.fields.CharField', [], {'max_length': '25'})
        },
        'bmabr.twittersource': {
            'source_ptr': ('django.db.models.fields.related.OneToOneField', [], {'to': "orm['bmabr.Source']", 'unique': 'True', 'primary_key': 'True'}),
            'status_id': ('django.db.models.fields.CharField', [], {'max_length': '32'}),
            'user': ('django.db.models.fields.CharField', [], {'max_length': '50'})
        }
    }
    
    complete_apps = ['bmabr']
