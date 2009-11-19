# -*- mode: python ;-*-

down_page = '''
<html>
<head><title>FixCity.org is currently down for
maintenance.</title></head>

<body>
<h1>FixCity.org is currently down for maintenance.</h1>
<p>Come back soon!</p>
</body>
</html>
'''

def application(environ, start_response):
    status = '200 OK'
    response_headers = [('Content-type','text/html')]
    start_response(status, response_headers)
    return [down_page]

