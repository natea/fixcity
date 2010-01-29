BikeRaction aka BuildMeABikeRack aka Fixcity
============================================

This is the code behind http://fixcity.org/ , a site that aims to help
get bike racks built in New York City, by allowing ordinary people to
combine efforts and get bulk orders submitted to the NYC Department of
Transportation.

It was built by TOPP Labs, a division of The Open Planning Project,
http://openplans.org.

The canonical source code is at http://github.com/slinkp/fixcity

The project wiki is at https://projects.openplans.org/fixcity/wiki
and the bug tracker is at https://projects.openplans.org/fixcity/report

What's In a Name?
=================

This project has been through several names already. Sorry :)

If you see "bmabr" in code, it's just an acronym for "Build Me A Bike
Rack", one of the older names. Don't worry about it...


License
=======


Released under the terms of the GNU Affero General Public License (GNU
AGPL). See COPYING.txt for details.


INSTALLATION
=============

Prerequisites
=============

Things you will need.

On Ubuntu 9.04 - 9.10:
----------------------

 sudo apt-get install \
  build-essential \
  libgeos-dev \
  libjpeg-dev \
  libpq-dev \
  libxml2-dev \
  libxslt1-dev \
  postgis \
  postgresql-8.3 \
  postgresql-server-dev-8.3 \
  proj \
  python \
  python-dev

postgresql-8.4 also should work.

I had some trouble on Ubuntu 9.10; I was able to proceed by installing
postgis from source according to the instructions here:
http://biodivertido.blogspot.com/2009/10/install-postgresql-84-and-postgis-140.html

Add info for other systems here...


Installation
============

Given all the prerequisites above, just run `python setup.py develop`,
preferably in a virtualenv to avoid installing stuff into your global
python site-packages.


Bootstrapping a Database
========================

This application requires a PostGIS database and some shape data. To
get started:

 1) Copy the config.ini.in file to config.ini.  Edit database settings
    in config.ini as needed.  You MUST change the value of the
    'SECRET_KEY' setting.

 2) Create your database:

  createdb -T template_postgis bmabr

  ... the last parameter should be the name of your database.
  If you don't have a template_postgis database, Google will tell you
  how to create one ;)

 3) Load the data:

   psql -d bmabr -f fixcity/sql/gis_community_board.sql

 4) Bootstrap the django models:

  cd fixcity
  ./manage.py syncdb
  ./manage.py migrate

 5) Visit the /admin/sites/site UI to change the domain name and
    display name of the website. These are used eg. in account
    confirmation email sent to users who register.


Deployment
==========

If you want to deploy under mod_wsgi, there's an appropriate handler
script in fixcity/wsgi/.  Point your apache config at it, something
like this:


 <VirtualHost ...>
 ServerName ...
 
 <Directory /PATH/TO/fixcity/wsgi/>
    Order allow,deny
    Allow from all
 </Directory>
 
 WSGIScriptAlias / /PATH/TO/fixcity/wsgi/fixcity.wsgi

 </VirtualHost>


