
from south.db import db
from django.db import models
from fixcity.bmabr.models import *

class Migration:
    
    def forwards(self, orm):
        
        # Deleting model 'neighborhoods'
        db.delete_table(u'gis_neighborhoods')
        
        # Deleting model 'comment'
        db.delete_table('bmabr_comment')
        
        # Deleting model 'subwaystations'
        db.delete_table(u'gis_subway_stations')
        
    
    
    def backwards(self, orm):
        
        # Adding model 'neighborhoods'
        db.create_table(u'gis_neighborhoods', (
            ('city', orm['bmabr.subwaystations:city']),
            ('name', orm['bmabr.subwaystations:name']),
            ('regionid', orm['bmabr.subwaystations:regionid']),
            ('county', orm['bmabr.subwaystations:county']),
            ('state', orm['bmabr.subwaystations:state']),
            ('gid', orm['bmabr.subwaystations:gid']),
            ('the_geom', orm['bmabr.subwaystations:the_geom']),
        ))
        db.send_create_signal('bmabr', ['neighborhoods'])
        
        # Adding model 'comment'
        db.create_table('bmabr_comment', (
            ('text', orm['bmabr.subwaystations:text']),
            ('rack', orm['bmabr.subwaystations:rack']),
            ('email', orm['bmabr.subwaystations:email']),
            ('id', orm['bmabr.subwaystations:id']),
        ))
        db.send_create_signal('bmabr', ['comment'])
        
        # Adding model 'subwaystations'
        db.create_table(u'gis_subway_stations', (
            ('name', orm['bmabr.subwaystations:name']),
            ('objectid', orm['bmabr.subwaystations:objectid']),
            ('color', orm['bmabr.subwaystations:color']),
            ('express', orm['bmabr.subwaystations:express']),
            ('nghbhd', orm['bmabr.subwaystations:nghbhd']),
            ('cross_st', orm['bmabr.subwaystations:cross_st']),
            ('label', orm['bmabr.subwaystations:label']),
            ('long_name', orm['bmabr.subwaystations:long_name']),
            ('alt_name', orm['bmabr.subwaystations:alt_name']),
            ('closed', orm['bmabr.subwaystations:closed']),
            ('transfers', orm['bmabr.subwaystations:transfers']),
            ('routes', orm['bmabr.subwaystations:routes']),
            ('gid', orm['bmabr.subwaystations:gid']),
            ('borough', orm['bmabr.subwaystations:borough']),
            ('the_geom', orm['bmabr.subwaystations:the_geom']),
            ('id', orm['bmabr.subwaystations:id']),
        ))
        db.send_create_signal('bmabr', ['subwaystations'])
        
    
    
    models = {
        'bmabr.communityboard': {
            'Meta': {'db_table': "u'gis_community_board'"},
            'board': ('django.db.models.fields.IntegerField', [], {}),
            'boro': ('django.db.models.fields.CharField', [], {'max_length': '50'}),
            'borocd': ('django.db.models.fields.IntegerField', [], {}),
            'gid': ('django.db.models.fields.IntegerField', [], {'primary_key': 'True'}),
            'the_geom': ('django.contrib.gis.db.models.fields.MultiPolygonField', [], {})
        },
        'bmabr.emailsource': {
            'address': ('django.db.models.fields.EmailField', [], {'max_length': '75'}),
            'source_ptr': ('django.db.models.fields.related.OneToOneField', [], {'to': "orm['bmabr.Source']", 'unique': 'True', 'primary_key': 'True'})
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
        'bmabr.twittersource': {
            'source_ptr': ('django.db.models.fields.related.OneToOneField', [], {'to': "orm['bmabr.Source']", 'unique': 'True', 'primary_key': 'True'}),
            'status_id': ('django.db.models.fields.CharField', [], {'max_length': '32'}),
            'user': ('django.db.models.fields.CharField', [], {'max_length': '50'})
        }
    }
    
    complete_apps = ['bmabr']
