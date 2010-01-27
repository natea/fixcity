from django import template

register = template.Library()


verification_details = {
    'surface': [
        "11' wide public widewalk",
        "3' Utility covers, tree pit edges, grates with hinges",
        "Un-cracked concrete surface",
        ],
    'objects': [
        "5' Benches, planters, telephones, mailboxes",
        "5' Signs, parking meters, lamp posts, standpipes, etc.)",
        ],
    'access': [
        "15' Crosswalks &#038; special curb areas: bus stops, taxi stands, hotel loading zones Franchised structures: sidewalk cafes, bus &#038; bike shelters, toilets, newstands",
        "8' Fire hydrants",
        "5' Building entrances &#038; driveways",
        "3' Hatches &#038; subway entrances  (railings, stairs, elevators, etc.)",
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
