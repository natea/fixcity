# -*- mode: python ;-*-

import os
import sys
import site

# Some libraries (eg. geopy) have an annoying habit of printing to stdout,
# which is a no-no under mod_wsgi.
# Workaround as per http://code.google.com/p/modwsgi/wiki/ApplicationIssues
sys.stdout = sys.stderr

# Try to find a virtualenv in our parent chain.
HERE = env_root = os.path.abspath(os.path.dirname(__file__))
found = False
while env_root != '/':
    env_root = os.path.abspath(os.path.dirname(env_root))
    if os.path.exists(os.path.join(env_root, 'bin', 'activate')):
        found = True
        break
assert found, "didn't find a virtualenv in any parent of %s" % HERE

sitepackages_root = os.path.join(env_root, 'lib')
assert os.path.exists(sitepackages_root), "no such dir %s" % sitepackages_root
for d in os.listdir(sitepackages_root):
    if d.startswith('python'):
        site.addsitedir(os.path.join(sitepackages_root, d, 'site-packages'))
        break
else:
    raise RuntimeError("Could not find any site-packages to add in %r" % env_root)

os.environ['DJANGO_SETTINGS_MODULE'] = 'fixcity.settings'
os.environ['PYTHON_EGG_CACHE'] = '/tmp/fixcity-python-eggs'

import django.core.handlers.wsgi
from wsgilog import WsgiLog

application = django.core.handlers.wsgi.WSGIHandler()

# Log uncaught exceptions to stderr via WSGI middleware.
#
# This isn't usually necessary: when settings.DEBUG is true, the
# default behavior is to dump errors to stdout and show them nicely in
# the browser; when settings.DEBUG is false, our custom 500 error view
# takes care of logging. But if for any reason *that* view blows up,
# we fall back to this.  (I wouldn't have bothered except I figured
# out how to get this working before I hooked up logging in that
# view.)

# WsgiLog is a bit funny about keyword args: it checks for presence,
# not value, so passing eg. tofile=False means "log to the default
# file", not "don't do file logging".  So I'm not passing any of those
# args.
application = WsgiLog(application, tostream=True)
