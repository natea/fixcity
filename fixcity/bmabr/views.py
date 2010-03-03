# Create your views here.
from django.db import transaction
from django.http import HttpResponse, HttpResponseRedirect
from django.http import HttpResponseNotAllowed
from django.http import HttpResponseServerError
from django.http import HttpResponseBadRequest
from django.shortcuts import render_to_response
from django.template import RequestContext
from django.core.cache import cache
from django.core.files.uploadhandler import FileUploadHandler
from django.core.mail import EmailMessage
from django.core.mail import send_mail
from django.core.paginator import EmptyPage
from django.core.paginator import InvalidPage
from django.core.paginator import Paginator
from django.core import urlresolvers

from django.contrib.auth.decorators import permission_required
from django.contrib.auth.forms import SetPasswordForm
from django.contrib.auth.models import User, Group
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

from fixcity.bmabr import bulkorder
from fixcity.bmabr.models import Borough
from fixcity.bmabr.models import CityRack
from fixcity.bmabr.models import Rack
from fixcity.bmabr.models import CommunityBoard
from fixcity.bmabr.models import NYCDOTBulkOrder, BulkOrderForm
from fixcity.bmabr.models import RackForm, SupportForm
from fixcity.bmabr.models import StatementOfSupport
from fixcity.bmabr.models import Source, TwitterSource, EmailSource
from fixcity.flash_messages import flash
from fixcity.flash_messages import flash_error

from geopy import geocoders

from django.utils import simplejson as json
from django.conf import settings

from recaptcha.client import captcha

from voting.models import Vote

import cStringIO
import datetime
import logging
import sys
import traceback
import urllib

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

def blank_page(request):
    """ Useful for pages that just need to deplay a flash message and
    nothing else, eg. after submitting a form where there's no other
    obvious next page to redirect to.
    """
    return render_to_response(
        'base.html', {}, context_instance=RequestContext(request))
                      
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

_geocoder = geocoders.Google(settings.GOOGLE_MAPS_KEY)

def _geocode(text):
    # Cache a bit, since that's easier than ensuring that our AJAX
    # code doesn't call it with the same params a bunch of times.
    text = text.strip()
    key = ('_geocode', text)
    result = cache.get(key)
    if result is None:
        result = list(_geocoder.geocode(text, exactly_one=False))
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
        (new_place,new_point) = geocoders.Google(settings.GOOGLE_MAPS_KEY).reverse(point)
        result = new_place
        cache.set(key, result, 60 * 10)
    return HttpResponse(result)

def make_paginator(objs, start_page, per_page):
    """create a paginator and page object from a list"""
    paginator = Paginator(objs, per_page)
    try:
        page = paginator.page(start_page)
    except (EmptyPage, InvalidPage):
        page = paginator.page(paginator.num_pages)
    return (page, paginator)

def racks_index(request):
    # might be creating a new rack...
    if request.method == 'POST' and \
            request.META.get('CONTENT_TYPE') == 'application/json':
        return newrack_json(request)

    # determine the appropriate racks query
    racks = Rack.objects.all()
    try:
        board_gid = int(request.GET.get('cb', '0'))
    except ValueError:
        board_gid = 0
    if board_gid != 0:
        # racks for a particular community board
        cb = get_object_or_404(CommunityBoard, gid=board_gid)
        racks = cb.racks
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
    racks = filter_by_verified(racks, vrfy)

    # set up pagination information
    try:
        cur_page_num = int(request.GET.get('page', '1'))
    except ValueError:
        cur_page_num = 1
    per_page = 7
    page, paginator = make_paginator(racks, cur_page_num, per_page)
    template_params = {'paginator': paginator,
                       'page_obj': page,
                       }
    # and return the appropriate template based on on request type
    if request.is_ajax():
        return render_to_response('racklist.html',
                                        template_params,
                                        context_instance=RequestContext(request))
    else:
        boards = CommunityBoard.objects.filter(borough=Borough.brooklyn())
        template_params['boards'] = boards
        return render_to_response('verify.html',
                                  template_params,
                                  context_instance=RequestContext(request))

def racks_by_communityboard(request, cb_id):
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
    to create, if any.

    Returns a tuple of (Source, created) where created is a boolean:
    True if the source was created anew, False if it already existed.
    """
    if data.get('source'):
        source = Source.objects.filter(id=data['source']).all()
        assert len(source) == 1, \
               "Unexpectedly got %d sources with id %s" % (len(source), data['source'])
        source = source[0]
        # Try to get a more specific subclass instance.
        source = source.get_child_source() or source
        return (source, False)

    source = None
    source_type = data.get('source_type')
    if source_type == 'twitter':
        source = TwitterSource(name='twitter', user=data['twitter_user'],
                               status_id=data['twitter_id'])
    elif source_type == 'email' and data.has_key('email'):
        source = EmailSource(name='email', address=data['email'])
    # XXX handle SeeClickFixSource here
    if source:
        # We need to save it to get the ID.  This means we'll need to
        # roll back the transaction if there are later validation
        # problems in the Rack.
        source.save()
    return (source, source is not None)


def newrack_form(request):
    if request.method == 'POST':
        _preprocess_rack_form(request.POST)
        result = _newrack(request.POST, request.FILES)
        form = result['form']
        if not result['errors']:
            message = '''<h2>Thank you for your suggestion!</h2><p>Racks can take six months or more for the DOT to install, but we\'ll be in touch about its progress.</p><a href="/racks/new/">Add another rack</a> or continue to see other suggestions.'''
            flash(message, request)
            return HttpResponseRedirect(urlresolvers.reverse(racks_index))
        else:
            flash_error('Please correct the following errors.', request)
    else:
        form = RackForm()
    return render_to_response('newrack.html', {
            'form': form,
           },
           context_instance=RequestContext(request))


@transaction.commit_manually
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
    source, is_new_source = source_factory(post)
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
        transaction.rollback()
    else:
        status = 200
        rack = rackresult['rack']
        output = {'rack': rack.id,
                  'message': rackresult['message'],
                  'photo_post_url': '/racks/%d/photos/' % rack.id,
                  'rack_url': '/racks/%d/' % rack.id,
                  'user': rack.user,
                  'email': rack.email,
                  # XXX what about other Sources?
                  }
        transaction.commit()
    return HttpResponse(json.dumps(output), mimetype='application/json',
                        status=status)



def support(request, rack_id):
    """Add a statement of support."""
    if request.method == "POST":
        form_support = SupportForm(request.POST,request.FILES)
        if form_support.is_valid():
            new_support = form_support.save()
            return HttpResponseRedirect(urlresolvers.reverse(rack_view, rack_id=rack_id))
        else:
            return HttpResponse('something went wrong')
    else:
        return HttpResponse('not allowed')


@login_required
def rack_edit(request,rack_id):
    rack = get_object_or_404(Rack, id=rack_id)
    form = RackForm()
    if rack.locked:
        flash_error('This rack is locked and cannot be edited.', request)
    elif request.method == 'POST':
        # For now, preserve the original creator.
        request.POST[u'email'] = rack.email
        request.POST[u'user'] = rack.user
        _preprocess_rack_form(request.POST)
        form = RackForm(request.POST, request.FILES, instance=rack)
        if form.is_valid():
            x = form.save()
            flash('Your changes have been saved.', request)
            return HttpResponseRedirect(
                urlresolvers.reverse(rack_edit, kwargs={'rack_id': rack.id}))
        else:
            flash_error('Please correct the following errors.', request)

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
    return render_to_response(
        'rack.html', {
            'rack': rack,
            'statement_query': statement_query,
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
    user = request.user
    rack = get_object_or_404(Rack, id=rack_id)
    result = {}
    if request.method == 'POST':
        user_voted = Vote.objects.get_for_user(rack, request.user)
        if user_voted is not None:
            result['error'] = u"Already voted on rack"
        elif rack.user == user.username:
            result['error'] = u"You can't vote on a rack you suggested."
        else:
            Vote.objects.record_vote(rack, request.user, 1)
    votes = Vote.objects.get_score(rack)
    result['votes'] = votes['score']
    status = 'error' in result and 400 or 200
    response = HttpResponse(content_type='application/json', status=status)
    response.write(json.dumps(result))
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
#@cache_page(60 * 10)
def rack_search_kml(request):
    racks = Rack.objects.all()
    try:
        page_number = int(request.REQUEST.get('page_number', '1'))
    except ValueError:
        page_number = 1
    try:
        page_size = int(request.REQUEST.get('page_size', sys.maxint))
    except ValueError:
        page_size = sys.maxint

    status = request.GET.get('status')
    if status:
        racks = racks.filter(status=status)

    verified = request.GET.get('verified')
    racks = filter_by_verified(racks, verified)

    # Get bounds from request.
    bbox = request.REQUEST.get('bbox')
    if bbox:
        bbox = [float(n) for n in bbox.split(',')]
        assert len(bbox) == 4
        geom = Polygon.from_bbox(bbox)
        racks = racks.filter(location__within=geom)
    cb = request.GET.get('cb')
    boro = request.GET.get('boro')
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


def community_board_kml(request, cb_id):
    try:
        cb_id = int(cb_id)
    except ValueError:
        raise Http404
    community_board = get_object_or_404(CommunityBoard, gid=cb_id)
    return render_to_kml("community_board.kml",
                         {'communityboard': community_board})

def borough_kml(request, boro_id):
    try:
        boro_id = int(boro_id)
    except ValueError:
        raise Http404
    borough = get_object_or_404(Borough, gid=boro_id)
    return render_to_kml('borough.kml',
                         {'borough': borough})

def cityracks_kml(request):
    bbox = request.REQUEST.get('bbox')
    if bbox:
        bbox = [float(n) for n in bbox.split(',')]
        assert len(bbox) == 4
        geom = Polygon.from_bbox(bbox)
        cityracks = CityRack.objects.filter(the_geom__within=geom)
    else:
        cityracks = CityRack.objects.all()
    return render_to_kml('cityracks.kml',
                         {'cityracks': cityracks})

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
                        return HttpResponseRedirect(urlresolvers.reverse(index))

    # Post-activation: Modify anonymous racks.
    context_instance['activation_key'] = activation_key
    if account:
        Rack.objects.filter(email=account.email, user=u'').update(user=account.username)

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

def cbs_for_boro(request, boro):
    """return json results for ajax call to fetch boards for a borough
    """
    try:
        boro = int(boro)
    except ValueError:
        raise Http404
    borough = get_object_or_404(Borough, gid=boro)
    board_tuple = [(cb.board, cb.gid)
                   for cb in CommunityBoard.objects.filter(borough=borough)]
    board_tuple.sort()
    return HttpResponse(json.dumps(board_tuple), mimetype='application/json')

def redirect_rack_urls(request):
    assert request.path_info.startswith('/rack/'), "invalid path info"
    no_rack_path = request.path_info[len('/rack/'):]
    new_path = '/racks/' + no_rack_path
    from django.http import HttpResponsePermanentRedirect
    return HttpResponsePermanentRedirect(new_path)


def bulk_order_edit_form(request, bo_id):
    if not request.user.has_perm('bmabr.add_nycdotbulkorder'):
        error = """Only approved users can edit bulk orders. Please
        <a href="/contact/">contact us</a> to ask for approval."""
        flash_error(error, request)
        url = '%s?%s' % (
            urlresolvers.reverse('django.contrib.auth.views.login'),
            urllib.urlencode({'next': request.get_full_path()}))
        return HttpResponseRedirect(url)

    bulk_order = get_object_or_404(NYCDOTBulkOrder, id=bo_id)
    cb = bulk_order.communityboard
    form = BulkOrderForm()

    if request.method == 'POST':
        post = request.POST.copy()
        next_state = post.get('next_state')
        if next_state == 'completed':
            # The DOT has apparently completed building this order. Yay!!
            flash(u'Marking bulk order as completed.', request)
            bulk_order.racks.update(status=next_state)
            bulk_order.status = next_state
            bulk_order.save()
        else:
            post[u'communityboard'] = post.get('cb_gid')
            post[u'user'] = request.user.pk
            form = BulkOrderForm(post)
            if form.is_valid():
                form.save()
            else:
                flash_error('Please correct the following errors.', request)

    return render_to_response(
        'bulk_order_edit_form.html',
        {'request': request,
         'bulk_order': bulk_order,
         'cb': cb,
         'form': form,
         'status': dict(form.fields['status'].choices).get(bulk_order.status),
         },
        context_instance=RequestContext(request)
        )

@permission_required('bmabr.add_nycdotbulkorder')
def bulk_order_submit_form(request, bo_id):
    bulk_order = get_object_or_404(NYCDOTBulkOrder, id=bo_id)
    next_state = request.POST.get('next_state')
    if request.method == 'POST' and next_state == 'pending':
        # Submit this to the DOT!
        _bulk_order_submit(bulk_order, next_state, request.POST)
        flash(u'Your order has been submitted to the DOT. '
              u'or rather, it would have been if the code was done!',
              request)
    return render_to_response(
        'bulk_order_submit_form.html',
        {'request': request,
         'bulk_order': bulk_order,
         'cb': bulk_order.communityboard,
         },
        context_instance=RequestContext(request)
        )

def _bulk_order_submit(bo, next_state, postdata):
    user_message = postdata['message']
    name = postdata['name']
    organization = postdata['organization']
    email = postdata['email']
    cb = bo.communityboard

    subject = 'New bulk order for bike racks in %s' % bo.communityboard
    date = datetime.datetime.now().isoformat()
    user_message = '\n'.join(('====== Begin message from user =====\n',
                              user_message,
                              '\n====== End message from user ====='))
    body = '''This an automatic notification from http://fixcity.org.

A user named %(name)s <%(email)s> from the organization %(organization)s
has created a new bulk order for %(cb)s.

A zip file is attached to this email, containing:

* A .csv file with information about the requested bike racks.
  This is suitable for importing into an Excel spreadsheet or eg.
  an Access database.

* A PDF with photos and information about the requested bike racks.

* Any attachments the user may have added to the bulk order, such as
  letters of support.

The user included the following message:

%(user_message)s
    ''' % locals()
    message = EmailMessage(subject, body, settings.DEFAULT_FROM_EMAIL,
                           [settings.BULK_ORDER_SUBMISSION_EMAIL])

    zipdata = cStringIO.StringIO()
    bulkorder.make_zip(bo, zipdata)
    zipdata.seek(0)
    message.attach(bulkorder.make_filename(bo, 'zip'), zipdata.read(),
                   'application/zip')
    bo.submit()
    message.send(fail_silently=False)

@login_required
def bulk_order_add_form(request):
    cb = None
    form = BulkOrderForm()
    if request.method == 'POST':
        cb_gid = request.POST.get('cb_gid')
        post = request.POST.copy()
        post[u'communityboard'] = cb_gid
        post[u'user'] = request.user.pk
        form = BulkOrderForm(post)
        if form.is_valid():
            bulk_order = NYCDOTBulkOrder.objects.filter(communityboard=cb_gid)
            if bulk_order:
                flash_error("There is already a bulk order for this CB.", request)
            else:
                bulk_order = form.save()
                if request.user.has_perm('bmabr.add_nycdotbulkorder'):
                    flash("Bulk order created! Follow the directions below to complete it.", request)
                    bulk_order.approve()
                    bulk_order.save()
                    return HttpResponseRedirect(
                        urlresolvers.reverse(bulk_order_edit_form,
                                             kwargs={'bo_id': bulk_order.id}))
                
                else:
                    flash("Thanks for your request. "
                          "The site admins will check out your request and "
                          "get back to you soon!",
                          request
                          )
                    subject = 'New bulk order request needs approval'
                    approval_uri = request.build_absolute_uri(
                        urlresolvers.reverse(
                            bulk_order_approval_form, args=[bulk_order.id]))
                    body = """
A new bulk order has been submitted.
To approve this user and this order, go to:
%s
""" % approval_uri
                    send_mail(subject, body, settings.DEFAULT_FROM_EMAIL,
                              settings.BULK_ORDER_APPROVAL_EMAIL,
                              fail_silently=False)
                    return HttpResponseRedirect(urlresolvers.reverse(blank_page))
        else:
            flash_error('Please correct the following errors.', request)
    return render_to_response(
        'bulk_order_add_form.html',
        {'request': request,
         'cb': cb,
         'form': form,
         },
        context_instance=RequestContext(request)
        )

@permission_required('auth.change_user')
def bulk_order_approval_form(request, bo_id):
    """Some privileged users can approve bulk orders created by
    unprivileged users.
    """
    bo = get_object_or_404(NYCDOTBulkOrder, id=bo_id)
    if request.method == 'POST':
        bo.approve()
        bo.save()
        group = Group.objects.get(name='bulk_ordering')
        bo.user.groups.add(group)
        bo.user.save()
        subject = 'Your bulk order has been approved for submission to the DOT'
        body = """
Thanks for your bulk order request. Our site admins have given
you approval to submit this bulk order to the NYC Department of
Transportation.

To finish your bulk order, follow this link:
%s
""" % request.build_absolute_uri(urlresolvers.reverse(
                bulk_order_edit_form, kwargs={'bo_id': bo.id}))

        send_mail(subject, body, settings.DEFAULT_FROM_EMAIL,
                  [bo.user.email],
                  fail_silently=False)

    return render_to_response('bulk_order_approval_form.html',
       {'request':request,
        'bulk_order': bo,
        'cb': bo.communityboard,
        },
       context_instance=RequestContext(request))


def bulk_order_csv(request, bo_id):
    from fixcity.bmabr import bulkorder

    bo = get_object_or_404(NYCDOTBulkOrder, id=bo_id)
    cb = bo.communityboard
    response = HttpResponse(mimetype='text/csv')
    filename = bulkorder.make_filename(bo, 'csv')
    response['Content-Disposition'] = 'attachment; filename=%s' % filename
    bulkorder.make_csv(bo, response)
    return response

def bulk_order_pdf(request, bo_id):
    from fixcity.bmabr import bulkorder
    bo = get_object_or_404(NYCDOTBulkOrder, id=bo_id)
    response = HttpResponse(mimetype='application/pdf')
    filename = bulkorder.make_filename(bo, 'pdf')
    response['Content-Disposition'] = 'attachment; filename=%s' % filename
    bulkorder.make_pdf(bo, response)
    return response


def bulk_order_zip(request, bo_id):
    from fixcity.bmabr import bulkorder
    bo = get_object_or_404(NYCDOTBulkOrder, id=bo_id)
    response = HttpResponse(mimetype='application/zip')
    filename = bulkorder.make_filename(bo, 'zip')
    response['Content-Disposition'] = 'attachment; filename=%s' % filename
    bulkorder.make_zip(bo, response)
    return response

def neighborhood_for_rack(rack):
    # Unfortunately, django doesn't support ordering by sql functions.
    # http://code.djangoproject.com/ticket/5293
    # So we'll use raw SQL.
    from django.db import connection
    cursor = connection.cursor()
    cursor.execute("""
      SELECT name FROM gis_neighborhoods
        WHERE ST_DWithin(the_geom, ST_GeomFromText(%r, %d), 1.0)
        ORDER BY ST_Distance(the_geom, ST_GeomFromText(%r, %d)) LIMIT 1
   """ % (rack.location.wkt, SRID, rack.location.wkt, SRID))
    row = cursor.fetchone()
    if row is None:
        return '<unknown>'
    return row[0]
    
    
def cross_streets_for_rack(rack):
    from django.db import connection
    cursor = connection.cursor()
    # The WHERE clause is an optimization that avoids looking at
    # any intersections far away.  The third arg was arrived at
    # empirically.
    cursor.execute(
        """SELECT street, nodeidfrom, nodeidto FROM gis_nycstreets
        WHERE ST_DWithin(the_geom, ST_PointFromText(%s, %s), .003)
        ORDER BY ST_Distance(the_geom, ST_PointFromText(%s, %s))
        LIMIT 1;
        """, [rack.location.wkt, SRID, rack.location.wkt, SRID])
    rack_info = cursor.fetchone()
    if rack_info is None:
        return (None, None)
    else:
        street, nodeidfrom, nodeidto = rack_info

    # Occasionally this fails to find any cross streets when there
    # really is one.  Don't know why.

    cursor.execute(
        """SELECT street FROM gis_nycstreets
        WHERE nodeidto = %s AND street != %s
        """, [nodeidfrom, street])
    previous_cross_street = cursor.fetchone()
    if previous_cross_street is not None:
        previous_cross_street = previous_cross_street[0]

    cursor.execute(
        """SELECT street FROM gis_nycstreets
        WHERE nodeidfrom = %s AND street != %s
        """, [nodeidto, street])
    next_cross_street = cursor.fetchone()
    if next_cross_street is not None:
        next_cross_street = next_cross_street[0]
    return (previous_cross_street, next_cross_street)

def filter_by_verified(racks, verified):
    """Since 'verified' is really three fields, this needs a bit of
    encapsulating other than just the rack.verified property, because
    you can't filter a query set on a property.
    """
    if verified == 'verified':
        racks = racks.filter(verify_surface=True,
                             verify_objects=True,
                             verify_access=True)
    elif verified == 'unverified':
        from django.db.models import Q
        racks = racks.filter(Q(verify_surface=False) |
                             Q(verify_access=False) |
                             Q(verify_objects=False))
    # Otherwise assume we want all racks.
    return racks

