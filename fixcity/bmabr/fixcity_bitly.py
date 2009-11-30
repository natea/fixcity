# thin wrapper around bitly api

from bitly import Api
from django.conf import settings

bitly_login = settings.BITLY_USER
bitly_api_key = settings.BITLY_API_KEY

bitly_api = Api(login=bitly_login, apikey=bitly_api_key)

def shorten_url(url):
    return bitly_api.shorten(url)
