from django import template  
from django.conf import settings  
from recaptcha.client import captcha
  
register = template.Library()  
 
@register.simple_tag  
def recaptcha_html():  
    html = u"<script>var RecaptchaOptions = {theme : 'white'};</script>"
    html += captcha.displayhtml(settings.RECAPTCHA_PUBLIC_KEY)
    return html
