# flash message wrapper around django flash

def flash(msg, request, msg_type='confirm'):
    request.flash.add(msg_type, msg)

def flash_error(msg, request):
    flash(msg, request, msg_type='error')
