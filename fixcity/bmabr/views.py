# Create your views here.
from django.http import HttpResponse, HttpResponseRedirect
from django.http import HttpResponseNotAllowed
from django.http import HttpResponseServerError
from django.http import HttpResponseBadRequest
from django.shortcuts import render_to_response
from django.template import RequestContext
from django.core.cache import cache
from django.core.files.uploadhandler import FileUploadHandler
from django.core.paginator import Paginator

from django.contrib.auth.forms import SetPasswordForm
from django.contrib.auth.models import User
from django.contrib.auth.tokens import default_token_generator as token_generator

from django.contrib.comments.forms import CommentForm

from django.http import Http404
from django.shortcuts import get_object_or_404
from django.utils.http import base36_to_int

from django.contrib.auth.decorators import login_required
from django.contrib.gis.geos.point import Point
from django.contrib.gis.geos.polygon import Polygon
from django.contrib.gis.shortcuts import render_to_kml

from django.template import Context, loader

from django.views.decorators.cache import cache_page

from fixcity.bmabr.models import Rack
from fixcity.bmabr.models import CommunityBoard
from fixcity.bmabr.models import RackForm, SupportForm
from fixcity.bmabr.models import StatementOfSupport
from fixcity.bmabr.models import Source, TwitterSource
from fixcity.flash_messages import flash
from fixcity.flash_messages import flash_error

from geopy import geocoders

from django.utils import simplejson as json
from django.conf import settings

from recaptcha.client import captcha

from voting.models import Vote

import logging
import sys
import traceback

cb_metric = 50.00 
GKEY="ABQIAAAApLR-B_RMiEN2UBRoEWYPlhTmTlZhMVUZVOGFgSe6Omf4DswcaBSLmUPer5a9LF8EEWHK6IrMgA62bg"
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

def _geocode(text):
    # Cache a bit, since that's easier than ensuring that our AJAX
    # code doesn't call it with the same params a bunch of times.
    text = text.strip()
    key = ('_geocode', text)
    result = cache.get(key)
    if result is None:
        result = list(geocoders.Google(GKEY).geocode(text, exactly_one=False))
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
        (new_place,new_point) = geocoders.Google(GKEY).reverse(point)
        result = new_place
        cache.set(key, result, 60 * 10)
    return HttpResponse(result)


def verify(request): 
    racks_query = Rack.objects.order_by(*DEFAULT_RACK_ORDER)
    return render_to_response('verify.html', { 
            'rack_query': racks_query,
            },
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
def rack_vote(request, rack_id):
    user = request.user
    value = request.POST.get('vote')
    rack = get_object_or_404(Rack, id=rack_id)
    if rack.user == user.username:
        flash_error(u"You can't vote on a rack you suggested.", request)
    elif value:
        value = int(value)
        if value > 0:
            value = 1
        elif value < 0:
            value = -1
        Vote.objects.record_vote(rack, user, value)
        flash('Your vote has been recorded.', request)
    return HttpResponseRedirect('/rack/%s/' % rack_id)


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

def rack_view(request, rack_id):
    rack = get_object_or_404(Rack, id=rack_id)
    statement_query = StatementOfSupport.objects.filter(s_rack=rack_id)
    context = RequestContext(request)
    if request.method == 'POST':
        # Maybe this should be AJAXy rather than a full page load?
        comment_form = _add_comment(request, rack)
    else:
        comment_form = ReCaptchaCommentForm(rack)
    user_likes_this_rack = Vote.objects.get_for_user(rack, request.user) > 0
    return render_to_response(
        'rack.html', { 
            'rack': rack,            
            'statement_query': statement_query,
            'user_suggested_this_rack': rack.user == context['user'].username,
            'user_likes_this_rack': user_likes_this_rack,
            'comment_form': comment_form,
            },
        context_instance=context)


def _add_comment(request, rack):
    # Simplified and hacked comment post function to change various things:
    #
    # 0. Skip all the model checking stuff as we assume we're just
    # working with racks.
    #
    # 1. get client IP address into the POST data, to make recaptcha happy.
    if '__recaptcha_ip' in request.POST:  
        return HttpResponseBadRequest()
    data = request.POST.copy()
    data['__recaptcha_ip'] = request.META['REMOTE_ADDR']

    # 2. Don't use a separate preview form to display errors.
    # Just validate and leave display up to the calling function.
    if request.user.is_authenticated():
        # We must first prepopulate logged-in user data;
        # copy-pasted from post_comment()
        if not data.get('name', ''):
            data["name"] = request.user.get_full_name() or request.user.username
        if not data.get('email', ''):
            data["email"] = request.user.email

    form = ReCaptchaCommentForm(rack, data,
                                need_captcha= not request.user.is_authenticated())
            
    if form.is_valid():
        flash(u"Your comment has been saved", request)
        comment = form.get_comment_object()
        comment.save()
    else:
        flash_error(u"Please correct errors in your comment", request)
    return form

@login_required
def votes(request, rack_id):
    # AJAX back-end for getting / incrementing votes on a rack.
    rack = get_object_or_404(Rack, id=rack_id)
    if request.method == 'POST':
        Vote.objects.record_vote(rack, request.user, 1)
    votes = Vote.objects.get_score(rack)
    response = HttpResponse(content_type='application/json')
    response.write(json.dumps({'votes': votes['score']}))
    return response


class ReCaptchaCommentForm(CommentForm):  

    # See http://arcticinteractive.com/2008/10/16/adding-recaptcha-support-django-10-comments/

    def __init__(self, target_object, data=None, initial=None, need_captcha=True):
        super(ReCaptchaCommentForm, self).__init__(target_object, data, initial)
        self.need_captcha = need_captcha
          
    def clean(self):
        if self.need_captcha:
            challenge_field = self.data.get('recaptcha_challenge_field')  
            response_field = self.data.get('recaptcha_response_field')  
            client = self.data.get('__recaptcha_ip') # always set by our code  
                  
            check_captcha = captcha.submit(
                challenge_field, response_field,
                settings.RECAPTCHA_PRIVATE_KEY, client)  
                  
            if check_captcha.is_valid is False:  
                self.errors['recaptcha'] = 'Invalid captcha value'  
  
        return self.cleaned_data 


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
        racks = Rack.objects.filter(location__contained=geom)
    else:
        racks = Rack.objects.all()
    racks = racks.order_by(*DEFAULT_RACK_ORDER)
    paginator = Paginator(racks, page_size)
    page_number = min(page_number, paginator.num_pages)
    page = paginator.page(page_number)
    votes = Vote.objects.get_scores_in_bulk(racks)
    return render_to_kml("placemarkers.kml", {'racks' : racks,
                                              'page': page,
                                              'page_size': page_size,
                                              'votes': votes,
                                              }) 


def community_board_kml(request): 
    community_boards = CommunityBoard.objects.all()
    return render_to_kml("community_board.kml",{'community_boards': community_boards})
 

def community_board_kml_by_id(request,cb_id): 
    community_boards = CommunityBoard.objects.filter(gid=cb_id)
    return render_to_kml("community_board.kml",{'community_boards': community_boards})



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

