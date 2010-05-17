from django import template

from voting.models import Vote

register = template.Library()

class CanUserHeartNode(template.Node):
    def __init__(self, user, rack, context_var):
        self.user = user
        self.rack = rack
        self.context_var = context_var

    def render(self, context):
        try:
            user = template.resolve_variable(self.user, context)
            rack = template.resolve_variable(self.rack, context)
        except template.VariableDoesNotExist:
            context[self.context_var] = False
        else:
            if (user.is_authenticated() and
                rack.user != user.username and
                Vote.objects.get_for_user(rack, user) is None):
                context[self.context_var] = True
            else:
                context[self.context_var] = False
        return u''

def do_can_heart(parser, token):
    """
    return whether a particular user can vote on a rack

    to vote on a rack, you must satisfy the following:
    1. you cannot vote on a rack you requested
    2. you cannot vote multiple times on a rack
    3. you must be logged in

    Example usage:
        {% can_heart user rack as canheart %}
    """
    bits = token.contents.split()
    if len(bits) != 5:
        raise template.TemplateSyntaxError("'%s' tag takes exactly 4 arguments" % bits[0])
    return CanUserHeartNode(bits[1], bits[2], bits[4])

register.tag('can_heart', do_can_heart)
