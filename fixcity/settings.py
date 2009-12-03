# Django settings for fixcity project.
# Deployment-specific or sensitive settings must go in config.ini!

import os
import sys

HERE=os.path.abspath(os.path.dirname(__file__))


# Sensitive settings are read from config.ini.
import ConfigParser
config = ConfigParser.RawConfigParser()
try:
    config.readfp(open(os.path.join(HERE, 'config.ini')))
except IOError:
    sys.stderr.write('\n\nYou need to create a config.ini file. '
                     'See config.ini.in for a sample.\n\n')
    raise

DEBUG = config.getboolean('main', 'DEBUG')
TEMPLATE_DEBUG = DEBUG

ADMINS = (
    # ('Your Name', 'your_email@domain.com'),
)

MANAGERS = ADMINS

DEFAULT_FROM_EMAIL = config.get('main', 'DEFAULT_FROM_EMAIL')

DATABASE_ENGINE = config.get('db', 'DATABASE_ENGINE')
DATABASE_NAME = config.get('db', 'DATABASE_NAME')
DATABASE_USER = config.get('db', 'DATABASE_USER')
DATABASE_PASSWORD = config.get('db', 'DATABASE_PASSWORD')
DATABASE_HOST = config.get('db', 'DATABASE_HOST')
DATABASE_PORT = config.get('db', 'DATABASE_PORT')

# Local time zone for this installation. Choices can be found here:
# http://en.wikipedia.org/wiki/List_of_tz_zones_by_name
# although not all choices may be available on all operating systems.
# If running in a Windows environment this must be set to the same as your
# system time zone.
TIME_ZONE = 'America/New_York'

# Caching. If we end up using it a lot, consider memcached.
CACHE_BACKEND = 'locmem:///'

# Language code for this installation. All choices can be found here:
# http://www.i18nguy.com/unicode/language-identifiers.html
LANGUAGE_CODE = 'en-us'

SITE_ID = 1

# If you set this to False, Django will make some optimizations so as not
# to load the internationalization machinery.
USE_I18N = True

# change the default login redirect because the default goes to
# /accounts/profile/ which doesn't exist
LOGIN_REDIRECT_URL = '/'

# Absolute path that serves RESOURCE media (css, js, etc).
STATIC_DOC_ROOT = config.get('main', 'STATIC_DOC_ROOT')
if not STATIC_DOC_ROOT.startswith('/'):
    STATIC_DOC_ROOT = os.path.abspath(os.path.join(HERE, STATIC_DOC_ROOT))

# Absolute path to the directory that holds UPLOADED media.
MEDIA_ROOT = config.get('main', 'MEDIA_ROOT')
if not MEDIA_ROOT.startswith('/'):
    MEDIA_ROOT = os.path.abspath(os.path.join(HERE, MEDIA_ROOT))

# URL that handles the media served from MEDIA_ROOT. Make sure to use a
# trailing slash if there is a path component (optional in other cases).
# Examples: "http://media.lawrence.com", "http://example.com/media/"
MEDIA_URL = '/uploads/'

# URL prefix for admin media -- CSS, JavaScript and images. Make sure to use a
# trailing slash.
# Examples: "http://foo.com/media/", "/media/".
ADMIN_MEDIA_PREFIX = '/media/'

GOOGLE_ANALYTICS_KEY = config.get('main', 'GOOGLE_ANALYTICS_KEY')

# Make this unique, and don't share it with anybody.
SECRET_KEY = config.get('main', 'SECRET_KEY')

assert SECRET_KEY != 'YOU MUST CHANGE THIS', \
        'You really need to change the SECRET_KEY setting in your config.ini!'

SEECLICKFIX_JSON_URL = config.get('main', 'SEECLICKFIX_JSON_URL')
SEECLICKFIX_STATUS_PATH = config.get('main', 'SEECLICKFIX_STATUS_PATH')

TWITTER_USER = config.get('twitter', 'USER')
TWITTER_PASSWORD = config.get('twitter', 'PASSWORD')
TWITTER_STATUS_PATH = config.get('twitter', 'STATUS_FILE_PATH')

BITLY_USER = config.get('bitly', 'user')
BITLY_API_KEY = config.get('bitly', 'api_key')

# email address to mail when there is a failure with an integration service
SERVICE_FAILURE_EMAIL = config.get('main', 'SERVICE_FAILURE_EMAIL')

# URL where scripts can post new racks.
RACK_POSTING_URL = config.get('main', 'RACK_POSTING_URL')

# List of callables that know how to import templates from various sources.
TEMPLATE_LOADERS = (
    'django.template.loaders.filesystem.load_template_source',
    'django.template.loaders.app_directories.load_template_source',
    'django.template.loaders.eggs.load_template_source',
)

MIDDLEWARE_CLASSES = (
    'django.middleware.common.CommonMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.middleware.transaction.TransactionMiddleware',
    'djangoflash.middleware.FlashMiddleware',
    'django.contrib.flatpages.middleware.FlatpageFallbackMiddleware',
    'django.contrib.redirects.middleware.RedirectFallbackMiddleware',
)

ROOT_URLCONF = 'fixcity.urls'

TEMPLATE_DIRS = (
    # Put strings here, like "/home/html/django_templates" or "C:/www/django/templates".
    # Always use forward slashes, even on Windows.
    # Don't forget to use absolute paths, not relative paths.
    os.path.join(HERE, 'templates'),
)


# This should be the number of days an activation key will remain
# valid after an account is registered.
ACCOUNT_ACTIVATION_DAYS = 14

# Limit size of uploads, then fall back to standard upload behavior.
FILE_UPLOAD_HANDLERS = (
    "fixcity.bmabr.views.QuotaUploadHandler",
    "django.core.files.uploadhandler.MemoryFileUploadHandler",
    "django.core.files.uploadhandler.TemporaryFileUploadHandler",
    )

INSTALLED_APPS = (
    'sorl.thumbnail',
    'django.contrib.auth',
    'django.contrib.comments',
    'django.contrib.contenttypes',
    'django.contrib.markup',
    'django.contrib.sessions',
    'django.contrib.sites',
    'django.contrib.admin',
    'django.contrib.gis',
    'django.contrib.redirects',
    'django.contrib.flatpages',
    'registration',
    'fixcity.bmabr',
    'basic.blog',
    'basic.inlines',
    'tagging',
    'south',
    'django_flash_templatetag',
)


TEMPLATE_CONTEXT_PROCESSORS = (
    "django.core.context_processors.auth",
    "django.core.context_processors.debug",
    "django.core.context_processors.i18n",
    "django.core.context_processors.media",
    "fixcity.bmabr.views.user_context",
    "djangoflash.context_processors.flash",
    )


# Config needed for bootstrapping a spatial db for tests.
TEST_RUNNER='django.contrib.gis.tests.run_tests'
try:
    POSTGIS_SQL_PATH = config.get('db', 'POSTGIS_SQL_PATH')
except:
    # fall back to default behavior, which works on some systems
    # (notably not ubuntu, hence the need for a config option)
    pass

# Logging?
import logging
import sys

handler = logging.StreamHandler(sys.stderr)
handler.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(levelname)-8s %(message)s')
handler.setFormatter(formatter)
logger = logging.getLogger('')
logger.addHandler(handler) 
logger.setLevel(logging.DEBUG)
