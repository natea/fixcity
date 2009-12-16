# Create your views here.
from django.http import HttpResponse, HttpResponseRedirect
from django.http import HttpResponseNotAllowed
from django.http import HttpResponseServerError
from django.shortcuts import render_to_response
from django.template import RequestContext
from django.template.loader import render_to_string
from django.core.cache import cache
from django.core.files.uploadhandler import FileUploadHandler
from django.core.paginator import EmptyPage
from django.core.paginator import InvalidPage
from django.core.paginator import Paginator

from django.contrib.auth.forms import SetPasswordForm
from django.contrib.auth.models import User
from django.contrib.auth.tokens import default_token_generator as token_generator
from django.http import Http404
from django.shortcuts import get_object_or_404
from django.utils.http import base36_to_int

from django.contrib.auth.decorators import login_required
from django.contrib.gis.geos.point import Point
from django.contrib.gis.geos.polygon import Polygon
from django.contrib.gis.shortcuts import render_to_kml

from django.template import Context, loader

from django.views.decorators.cache import cache_page

from fixcity.bmabr.models import Borough
from fixcity.bmabr.models import Rack, Comment
from fixcity.bmabr.models import Neighborhoods
from fixcity.bmabr.models import CommunityBoard
from fixcity.bmabr.models import RackForm, CommentForm, SupportForm
from fixcity.bmabr.models import StatementOfSupport
from fixcity.bmabr.models import Source, TwitterSource, SeeClickFixSource, EmailSource
from fixcity.bmabr.serializers import serialize_racks
from fixcity.flash_messages import flash
from fixcity.flash_messages import flash_error

from geopy import geocoders

from django.utils import simplejson as json
from django.conf import settings

import logging
import sys
import traceback

cb_metric = 50.00 
GKEY="ABQIAAAApLR-B_RMiEN2UBRoEWYPlhTmTlZhMVUZVOGFgSe6Omf4DswcaBSLmUPer5a9LF8EEWHK6IrMgA62bg"
g = geocoders.Google(GKEY)
SRID=4326

# XXX Need to figure out what order we really want these in.
DEFAULT_RACK_ORDER = ('-date', '-id')

def user_context(request):
    # Complicated a bit because AnonymousUser doesn't have some attributes.
    user = request.user
    first = getattr(user, 'first_name', '')
    last = getattr(user, 'last_name', '')
    email = getattr(user, 'email', '')
    if first and last:
        displayname = u'%s %s' % (first, last)
    else:
        displayname = first or last or user.username
    return {
        'request': request, 
        'user': request.user,
        'user_displayname': displayname,
        'user_email': email,
    }

def index(request):
    racks_query = Rack.objects.order_by(*DEFAULT_RACK_ORDER)[:7]
    return render_to_response('index.html',
       {'request':request,
        'recent_racks': racks_query,
        },
       context_instance=RequestContext(request)
                              ) 

@login_required
def profile(request): 
    user = request.user
    racks = Rack.objects.filter(user=user.username)
    return render_to_response('profile.html',
       {'user': user,
       'racks': racks
        },
       context_instance=RequestContext(request)
                              ) 

def built(request): 
    rack = Rack.objects.all()
    rack_extent = rack.extent()
    return render_to_response('built.html',{ 
            'rack_extent': rack_extent},
            context_instance=RequestContext(request)
            )


def _geocode(text):
    # Cache a bit, since that's easier than ensuring that our AJAX
    # code doesn't call it with the same params a bunch of times.
    text = text.strip()
    key = ('_geocode', text)
    result = cache.get(key)
    if result is None:
        result = list(g.geocode(text, exactly_one=False))
        cache.set(key, result, 60 * 10)
    return result

def geocode(request):
    location = request.REQUEST['geocode_text']
    results = _geocode(location)
    response = HttpResponse(content_type='application/json')
    response.write(json.dumps(results))
    return response

def reverse_geocode(request): 
    lat = request.REQUEST['lat'] 
    lon = request.REQUEST['lon']
    point = (lat, lon)
    key = ('reverse_geocode', point)
    result = cache.get(key)
    if result is None:
        (new_place,new_point) = g.reverse(point)
        result = new_place
        cache.set(key, result, 60 * 10)
    return HttpResponse(result)

def submit_all(request): 
    ''' 
    needs major re-working
    ''' 
    community_board_query = CommunityBoard.objects.filter() 
    return render_to_response('submit.html', {
            'community_board_query': community_board_query,
            })


def submit(request): 
    brooklyn = Borough.brooklyn()
    community_board_query = CommunityBoard.objects.filter(board=1, borough=brooklyn)
    for communityboard in community_board_query:
        racks_query = Rack.objects.filter(location__within=communityboard.the_geom)
        racks_count = Rack.objects.filter(location__within=communityboard.the_geom).count()
        cb_metric_percent = racks_count/cb_metric 
        cb_metric_percent = cb_metric_percent * 100 
        community_board_query_extent = community_board_query.extent()
    return render_to_response('submit.html', {
            'community_board_query': community_board_query,
            'cb_metric_percent':cb_metric_percent,
            'racks_query': racks_query,
            'racks_count': racks_count,
            'community_board_query_extent': community_board_query_extent,
            },
             context_instance=RequestContext(request)
             )

def make_paginator(objs, start_page, per_page):
    """create a paginator and page object from a list"""
    paginator = Paginator(objs, per_page)
    try:
        page = paginator.page(start_page)
    except (EmptyPage, InvalidPage):
        page = paginator.page(paginator.num_pages)
    return (page, paginator)

def verify(request):
    # determine the appropriate racks query
    racks = Rack.objects.all()
    try:
        board_gid = int(request.GET.get('cb', '0'))
    except ValueError:
        board_gid = 0
    if board_gid != 0:
        # racks for a particular community board
        cb = get_object_or_404(CommunityBoard, gid=board_gid)
        racks = racks.filter(location__within=cb.the_geom)
    else:
        try:
            boro_gid = int(request.GET.get('boro', '0'))
            if boro_gid != 0:
                boro = get_object_or_404(Borough, gid=boro_gid)
            else:
                boro = Borough.brooklyn()
        except ValueError:
            boro = Borough.brooklyn()
        racks = racks.filter(location__within=boro.the_geom)
    vrfy = request.GET.get('verified')
    if vrfy is not None:
        if vrfy == 'verified':
            racks = racks.filter(verified=True)
        elif vrfy == 'unverified':
            racks = racks.filter(verified=False)
    racks = racks.order_by(*DEFAULT_RACK_ORDER)
    # set up pagination information
    try:
        cur_page_num = int(request.GET.get('page', '1'))
    except ValueError:
        cur_page_num = 1
    per_page = 7
    page, paginator = make_paginator(racks, cur_page_num, per_page)
    template_params = {'paginator': paginator,
                       'page': page,
                       'cur_page_num': cur_page_num,
                       }
    # and return the appropriate template based on on request type
    if request.is_ajax():
        racks_html = render_to_string('racklist.html', template_params)
        return HttpResponse(racks_html)
    else:
        boards = CommunityBoard.objects.filter(borough=Borough.brooklyn())
        template_params['boards'] = boards
        return render_to_response('verify.html',
                                  template_params,
                                  context_instance=RequestContext(request))

def verify_by_communityboard(request,cb_id): 
    rack_query = Rack.objects.filter(communityboard=cb_id)    
    return render_to_response('verify_communityboard.html', { 
            'rack_query':rack_query
            },
            context_instance=RequestContext(request))

def _preprocess_rack_form(postdata):
    """Handle an edge case where the form is submitted before the
    client-side ajax code finishes setting the location.
    This can easily happen eg. if the user types an
    address and immediately hits return or clicks submit.

    Also do any other preprocessing needed.
    """

    if int(postdata[u'geocoded']) != 1:
        if postdata['address'].strip():
            results = _geocode(postdata['address'])
            # XXX handle multiple (or zero) results.
            try:
                lat, lon = results[0][1]
            except IndexError:
                # no results. XXX what to do here?
                postdata[u'location'] = u''
            else:
                postdata[u'location'] = str(Point(lon, lat, srid=SRID))
            
    # Handle a registered user submitting without logging in...
    # eg. via email.
    user = postdata.get('user', '').strip()
    email = postdata.get('email', '').strip()
    if email and not user:
        users = User.objects.filter(email=email).all()
        if len(users) == 1:
            postdata['user'] = users[0].username
        

def _newrack(data, files):
    """Thin wrapper around RackForm, returning a dict with some
    info useful for UIs."""
    form = RackForm(data, files)
    new_rack = None
    message = ''
    if form.is_valid():
        new_rack = form.save()
        message = '''
        Thank you for your suggestion! Racks can take six months
        or more for the DOT to install, but we\'ll be in touch
        about its progress.
        '''
    return {'rack': new_rack, 'message': message, 'form': form,
            'errors': form.errors}

def source_factory(data):
    """Given something like a request.POST, decide which kind of Source
    to create, if any."""
    if data.get('source'):
        source = Source.objects.filter(id=data['source']).all()
        assert len(source) == 1, \
               "Unexpectedly got %d sources with id %s" % (len(source), data['source'])
        source = source[0]
        # Try to get a more specific subclass instance.
        source = source.get_child_source() or source
        return source

    source = None
    source_type = data.get('source_type')
    if source_type == 'twitter':
        source = TwitterSource(name='twitter', user=data['twitter_user'],
                               status_id=data['twitter_id'])
    elif data.has_key('email'):
        # XXX actually we don't know if this came via web or email. hmm.
        pass
    # XXX handle SeeClickFixSource here
    if source:
        # We need to save it to get the ID.
        # As long as we have transactions enabled, this will roll back
        # if the rack fails to validate. XXX TEST THAT
        source.save()
    return source


def newrack_form(request):
    if request.method == 'POST':
        _preprocess_rack_form(request.POST)
        result = _newrack(request.POST, request.FILES)
        form = result['form']
        if not result['errors']:
            message = '''<h2>Thank you for your suggestion!</h2><p>Racks can take six months or more for the DOT to install, but we\'ll be in touch about its progress.</p><a href="/rack/new/">Add another rack</a> or continue to see other suggestions.'''
            flash(message, request)
            return HttpResponseRedirect('/verify/')
        else:
            flash_error('Please correct the following errors.', request)
    else:
        form = RackForm()
    return render_to_response('newrack.html', { 
            'form': form,
           },
           context_instance=RequestContext(request))


def rack_index(request):
    if request.method == 'POST':
        return newrack_json(request)
    else:
        # The /verify/ page serves as our main list of racks currently.
        return HttpResponseRedirect('/verify/')


def newrack_json(request):
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])
    # I would think there'd be a more useful way to get Django to
    # treat an entire POST body as JSON, but I haven't found it.
    args = json.loads(request.raw_post_data)
    post = request.POST.copy()
    post.clear()  # it doesn't have anything in useful form..
    post.update(args)
    _preprocess_rack_form(post)
    source = source_factory(post)
    if source:
        post['source'] = source.id
    rackresult = _newrack(post, files={})
    if rackresult['errors']:
        status = 400
        # Annoyingly, the errors thingy is made of weird dict & list
        # subclasses that I can't simply serialize.
        errors = {}
        for key, val in rackresult['errors'].items():
            # it's a list subclass containing string subclasses.
            errors[key] = [s[:] for s in val]
        output = {'errors': errors}
        # Bit of logging temporarily since we have no other way to
        # debug these on the live site...
        logger = logging.getLogger('')
        logger.error("Errors in newrack_json: %s.\nInput data was: %s" %
                     (str(errors), request.raw_post_data))
    else:
        status = 200
        rack = rackresult['rack']
        output = {'rack': rack.id,
                  'message': rackresult['message'],
                  'photo_post_url': '/rack/%d/photos/' % rack.id,
                  'rack_url': '/rack/%d/' % rack.id,
                  'user': rack.user,
                  'email': rack.email,
                  # XXX what about other Sources?
                  }
    return HttpResponse(json.dumps(output), mimetype='application/json',
                        status=status)



def support(request, rack_id): 
    """Add a statement of support."""
    if request.method == "POST":
        form_support = SupportForm(request.POST,request.FILES)
        if form_support.is_valid(): 
            new_support = form_support.save()
            return HttpResponseRedirect('/rack/%s/' % rack_id)              
        else: 
            return HttpResponse('something went wrong')              
    else:         
        return HttpResponse('not allowed')  

@login_required
def rack_edit(request,rack_id):
    rack = get_object_or_404(Rack, id=rack_id)
    if request.method == 'POST':
        # For now, preserve the original creator.
        request.POST[u'email'] = rack.email
        request.POST[u'user'] = rack.user
        _preprocess_rack_form(request.POST)
        form = RackForm(request.POST, request.FILES, instance=rack)
        if form.is_valid():
            x = form.save()
            flash('Your changes have been saved.', request)
            return HttpResponseRedirect('/rack/%s/edit/' % rack.id)
        else:
            flash_error('Please correct the following errors.', request)
    else: 
        form = RackForm()

    # Who created this rack?
    if rack.user == request.user.username or rack.email == request.user.email:
        creator = rack.user
    else:
        # Don't reveal email address to other users.
        # Instead show a username, or a truncated address if submitted
        # anonymously.
        creator = rack.user or "anonymous" # (%s@...)" % (rack.email.split('@', 1)[0]))
    return render_to_response('update_rack.html', 
          {"rack": rack,
           "form": form ,
           "creator": creator,
           },
          context_instance=RequestContext(request))

def rack(request,rack_id): 
    rack = get_object_or_404(Rack, id=rack_id)
    comment_query = Comment.objects.filter(rack=rack_id)
    statement_query = StatementOfSupport.objects.filter(s_rack=rack_id)
    return render_to_response('rack.html', { 
            'rack': rack,            
            'comment_query': comment_query,
            'statement_query': statement_query,
            },
            context_instance=RequestContext(request))
           
    

def add_comment(request): 
    form = CommentForm(request.POST)
    rack_id = request.POST['rack']
    if form.is_valid(): 
        new_comment = form.save()
        return HttpResponseRedirect('/rack/%s/#comments'% rack_id )   
    else: 
        return HttpResponseRedirect('/error/comment/') 


def updatephoto(request,rack_id):
    rack = Rack.objects.get(id=rack_id) 
    rack.photo = request.FILES['photo']
    rack.save()
    return HttpResponse('ok')

    
def rack_all_kml(request): 
    racks = Rack.objects.all()
    return render_to_kml("placemarkers.kml", {'racks' : racks}) 

# Cache hits are likely in a few cases: initial load of page;
# or clicking pagination links; or zooming in/out.
@cache_page(60 * 10)
def rack_requested_kml(request):
    try:
        page_number = int(request.REQUEST.get('page_number', '1'))
    except ValueError:
        page_number = 1
    try:
        page_size = int(request.REQUEST.get('page_size', sys.maxint))
    except ValueError:
        page_size = sys.maxint
    # Get bounds from request.
    bbox = request.REQUEST.get('bbox')
    if bbox:
        bbox = [float(n) for n in bbox.split(',')]
        assert len(bbox) == 4
        geom = Polygon.from_bbox(bbox)
        racks = Rack.objects.filter(location__within=geom)
    else:
        racks = Rack.objects.all()
    cb = request.GET.get('cb')
    boro = request.GET.get('boro')
    verified = request.GET.get('verified')
    board = None
    borough = None
    if cb is not None:
        try:
            board = CommunityBoard.objects.get(gid=int(cb))
            racks = racks.filter(location__within=board.the_geom)
        except (CommunityBoard.DoesNotExist, ValueError):
            board = None
    if board is None and boro is not None:
        try:
            borough = Borough.objects.get(gid=int(boro))
            racks = racks.filter(location__within=borough.the_geom)
        except (CommunityBoard.DoesNotExist, ValueError):
            pass
    if verified is not None:
        if verified == 'verified':
            racks = racks.filter(verified=True)
        elif verified == 'unverified':
            racks = racks.filter(verified=False)
    racks = racks.order_by(*DEFAULT_RACK_ORDER)
    paginator = Paginator(racks, page_size)
    page_number = min(page_number, paginator.num_pages)
    page = paginator.page(page_number)
    return render_to_kml("placemarkers.kml", {'racks' : racks,
                                              'page': page,
                                              'page_size': page_size,
                                              })


def community_board_kml(request): 
    community_boards = CommunityBoard.objects.all()
    return render_to_kml("community_board.kml",{'community_boards': community_boards})
 

def community_board_kml_by_id(request,cb_id): 
    community_boards = CommunityBoard.objects.filter(gid=cb_id)
    return render_to_kml("community_board.kml",{'community_boards': community_boards})

def rack_pendding_kml(request): 
    racks = Rack.objects.filter(status='a')
    return render_to_kml("placemarkers.kml", {'racks' : racks}) 


def rack_built_kml(request): 
    racks = Rack.objects.filter(status='a')
    return render_to_kml("placemarkers.kml", {'racks' : racks}) 


def rack_by_id_kml(request, rack_id): 
    racks = Rack.objects.filter(id=rack_id)
    return render_to_kml("placemarkers.kml",{'racks':racks})


def neighborhoods(request): 
    neighborhood_list = Neighborhoods.objects.all()
    return render_to_response('neighborhoods.html', {'neighborhood_list': neighborhood_list})


def communityboard(request): 
    communityboard_list = CommunityBoard.objects.all()      
    return render_to_response('communityboard.html', { 
            "communityboard_list": communityboard_list  
            }
           )


def activate(request, activation_key,
             template_name='registration/activate.html',
             extra_context=None):
    # Activate, then add this account to any Racks that were created
    # anonymously with this user's email address.  I would prefer to
    # simply wrap the registration.views.activate function from
    # django-registration, but I can't really do that because I can't
    # get at the activated user - it just returns rendered HTML. So,
    # I'm copy-pasting its code.

    context_instance = RequestContext(request)

    from registration.models import RegistrationProfile
    # -- Begin copy-pasted code from django-registration.
    activation_key = activation_key.lower() # Normalize before trying anything with it.
    
    account = RegistrationProfile.objects.activate_user(activation_key)
    if extra_context is None:
        extra_context = {}
    for key, value in extra_context.items():
        context_instance[key] = callable(value) and value() or value
    # -- End copy-pasted code from django-registration.

    # Let the user know if activation failed, and why.
    context_instance['key_status'] = 'Activation failed. Double-check your URL'
    if account:
        context_instance['key_status'] = 'Activated'
    else:
        from registration.models import SHA1_RE
        if not SHA1_RE.search(activation_key):
            context_instance['key_status'] = ('Malformed activation key. '
                                              'Make sure you got the URL right!')
        else:
            reg_profile = RegistrationProfile.objects.filter(
                activation_key=activation_key)
            if reg_profile: 
                reg_profile = reg_profile[0]
                if reg_profile.activation_key_expired():
                    context_instance['key_status'] = 'Activation key expired'
            else:
                # Unfortunately it's impossible to be sure if the user already
                # activated, because activation causes the key to be reset.
                # We could do it if we knew who the user was at this point,
                # but we don't.
                context_instance['key_status'] = ('No such activation key.'
                                                  ' Maybe you already activated?')

    # Now see if we need to reset the password.
    token = request.REQUEST.get('token')
    context_instance['valid_reset_token'] = False
    if token:
        uidb36 = request.REQUEST['uidb36']
        # Copy-paste-and-hack code from django.contrib.auth.views, yay.
        try:
            uid_int = base36_to_int(uidb36)
        except ValueError:
            raise Http404
        user = get_object_or_404(User, id=uid_int)
        context_instance['token'] = token
        context_instance['uidb36'] = uidb36
        context_instance['username'] = user.username
        if token_generator.check_token(user, token):
            context_instance['valid_reset_token'] = True
            if request.method == 'POST':
                form = SetPasswordForm(user, request.POST)
                if form.is_valid():
                    form.save()
                    flash('Password changed.', request)
                    from django.contrib.auth import login, authenticate
                    user = authenticate(username=user.username,
                                        password=request.POST['new_password1'])
                    if user:
                        login(request, user)
                        return HttpResponseRedirect('/')

    # Post-activation: Modify anonymous racks.
    context_instance['activation_key'] = activation_key
    if account:
        for rack in Rack.objects.filter(email=account.email, user=u''):
            rack.user = account.username
            rack.save()

    return render_to_response(template_name,
                              { 'account': account,
                                'expiration_days': settings.ACCOUNT_ACTIVATION_DAYS },
                              context_instance=context_instance)


class QuotaExceededError(Exception):
    pass

class QuotaUploadHandler(FileUploadHandler):
    """
    This upload handler terminates the connection if a file larger than
    the specified quota is uploaded.
    """

    QUOTA_MB = 5  # Should be a setting in settings.py?
    QUOTA =  QUOTA_MB * 1024 * 1024

    def __init__(self, request=None):
        super(QuotaUploadHandler, self).__init__(request)
        self.total_upload = 0
    
    def receive_data_chunk(self, raw_data, start):
        self.total_upload += len(raw_data)
        if self.total_upload >= self.QUOTA:
            raise QuotaExceededError('Maximum upload size is %.2f MB'
                                     % self.QUOTA_MB)
        # Delegate to the next handler.
        return raw_data
            
    def file_complete(self, file_size):
        return None

def server_error(request, template_name='500.html'):
    """
    500 error handler.
    This ONLY gets used if settings.DEBUG==False.

    Templates: `500.html`
    Context: None
    """
    info = sys.exc_info()
    exc_type = info[1].__class__.__name__
    exc_value = str(info[1])
    logger = logging.getLogger('')
    logger.error('at %r:' % request.build_absolute_uri())
    # This is fairly ugly in the apache error log, as each line gets
    # its own log entry, but hey it's way better than nothing.
    logger.error(traceback.format_exc())
    template = loader.get_template(template_name)
    context = Context({'exc_type': exc_type, 'exc_value': exc_value})
    return HttpResponseServerError(template.render(context),
                                   mimetype="application/xhtml+xml")

def cb1racks(request):
    brooklyn = Borough.brooklyn()
    cb1 = CommunityBoard.objects.get(board=1, borough=brooklyn)
    racks = Rack.objects.filter(location__within=cb1.the_geom)
    racks = racks.order_by('verified')
    nracks = len(racks)
    nverified = len([r for r in racks if r.verified])
    nunverified = nracks - nverified
    return render_to_response('cb1racks.html', {'racks': racks,
                                                'nracks': nracks,
                                                'nverified': nverified,
                                                'nunverified': nunverified,
                                                },
                              context_instance=RequestContext(request))

def cbs_for_boro(request, boro):
    """return json results for ajax call to fetch boards for a cb"""
    try:
        boro = int(boro)
    except ValueError:
        raise Http404
    borough = get_object_or_404(Borough, gid=boro)
    boros = [b.board for b in CommunityBoard.objects.filter(borough=borough)]
    boros.sort()
    return HttpResponse(json.dumps(boros), mimetype='application/json')

def rack_borough_kml(request, borough_id):
    try:
        borough_id = int(borough_id)
    except ValueError:
        raise Http404
    boro = get_object_or_404(Borough, gid=borough_id)
    racks = Rack.objects.filter(location__within=boro.the_geom)
    return render_to_kml('placemarkers.kml', {'racks': racks})

def rack_board_kml(request, board_id):
    try:
        board_id = int(board_id)
    except ValueError:
        raise Http404
    board = get_object_or_404(CommunityBoard, gid=board_id)
    racks = Rack.objects.filter(location__within=board.the_geom)
    return render_to_kml('placemarkers.kml', {'racks': racks})
