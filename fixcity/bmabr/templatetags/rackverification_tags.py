from django import template

register = template.Library()


verification_details = {
    'surface': [
        "11' from public sidewalk",
        "Un-cracked concrete surface",
        "3' clearance from utility covers, tree pit edges, grates with hinges",
        ],
    'objects': [
        "5' from signs, parking meters, lamp posts, standpipes",
        "5' from benches, planters, mailboxes",
        ],
    'access': [
        "15' from crosswalks, bus stops, taxi stands, hotel loading zones, sidewalk cafes, bus &#038; bike shelters",
        "8' from fire hydrants",
        "5' from building entrances &#038; driveways",
        "3' from hatches &#038; subway entrances",
        ],
    }


class RequirementsNode(template.Node):
    def __init__(self, context_var):
        self.context_var = context_var

    def render(self, context):
        context[self.context_var] = verification_details
        return ''


def do_rack_requirements(parser, token):
    """
    return a dictionary of requirements for easy template subsitution

    Example usage:
        {% rack_requirements as requirements %}
        <li>{{ requirements.surface }}</li>
    """
    bits = token.contents.split()
    if len(bits) != 3:
        raise template.TemplateSyntaxError("'%s' tag takes exactly 3 arguments" % bits[0])
    return RequirementsNode(bits[2])


register.tag('rack_requirements', do_rack_requirements)
