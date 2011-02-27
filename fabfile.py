# Fixcity Fabfile

from fabric.api import *
from fabric.contrib import files

"""
Base configuration
"""
env.project_name = 'fixcity'
env.database_name = 'bmabr'
env.database_password = '5IQZe7WEix'
env.site_media_prefix = "media"
env.admin_media_prefix = "admin_media"
env.path = '/home/ubuntu/%(project_name)s' % env
#env.log_path = '/home/ubuntu/logs/%(project_name)s' % env
#env.env_path = '%(path)s/env' % env
#env.repo_path = '%(path)s/repository' % env
env.apache_config_path = '/home/ubuntu/sites/apache/%(project_name)s' % env
env.python = 'python2.6'
env.repository_url = 'git://github.com/natea/fixcity.git'
# env.multi_server = False
# env.memcached_server_address = "cache.example.com"

"""
Environments
"""
def production():
    """
    Work on production environment
    """
    env.settings = 'production'
    env.user = 'newsapps'
    env.hosts = ['db.example.com']
    env.s3_bucket = 'media.apps.chicagotribune.com'

def staging():
    """
    Work on staging environment
    """
    env.settings = 'staging'
    env.user = 'ubuntu'
    env.hosts = ['ec2-72-44-55-154.compute-1.amazonaws.com'] 
#    env.s3_bucket = 'nate-geodjango'
    env.key_filename = 'fixcity.pem'
    
"""
Branches
"""
def stable():
    """
    Work on stable branch.
    """
    env.branch = 'stable'

def master():
    """
    Work on development branch.
    """
    env.branch = 'master'

def branch(branch_name):
    """
    Work on any specified branch.
    """
    env.branch = branch_name
    
"""
Commands - setup
"""
def setup():
    """
    Setup a fresh virtualenv, install everything we need, and fire up the database.
    
    Does NOT perform the functions of deploy().
    """
    require('settings', provided_by=[production, staging])
    require('branch', provided_by=[stable, master, branch])

    install_packages()
    checkout_code()
    create_virtualenv()
    install_app()
    setup_database()
    # clone_repo()
    # checkout_latest()
    # destroy_database()
    # create_database()
    # load_data()
    # install_requirements()
    # install_apache_conf()

def setup_database():
    """Set up the database for the first time"""
    _create_database()
    _load_data()

def _create_database():
    """Create the database"""
    sudo("sh %(path)s/%(project_name)s/scripts/create_template_postgis-debian.sh" % env, user='postgres')
    sudo('echo "CREATE USER %(project_name)s WITH PASSWORD \'%(database_password)s\';" | psql postgres' % env, user='postgres')
    sudo("createdb -O %(project_name)s -T template_postgis %(database_name)s || echo DB already exists." % env, user='postgres', shell=False)
    sudo(("""psql template1 -c "GRANT ALL ON DATABASE \"%(database_name)s\" to \"%(project_name)s\";" """) % env, user='postgres', shell=True)
         
def _load_data():
    """Load the data"""
    with cd("%(path)s" % env):
        sudo('psql -d %(database_name)s -f fixcity/sql/gis_community_board.sql' % env, user='postgres')
    sudo(("""psql template1 -c "GRANT ALL ON DATABASE \"%(database_name)s\" to \"%(project_name)s\";" """) % env, user='postgres', shell=True)
    
def install_packages():
    """Installs packages required by the djangozoom webapp & worker."""

    pkgs = ['build-essential',
            'libgeos-dev',
            'libjpeg-dev',
            'libpq-dev',
            'libxml2-dev',
            'libxslt1-dev',
            'postgresql-8.4-postgis',
            'proj',
            'python',
            'python-dev',
            'python-virtualenv',
            'git-core']
    sudo("apt-get update -y")
    sudo("apt-get upgrade -y")
    sudo('DEBIAN_FRONTEND=noninteractive apt-get install --no-install-recommends -q -y '+' '.join(pkgs))
    
def checkout_code():
    """Check out the Fixcity code from Github"""
    if not files.exists('%(path)s/.git' % env):
        run('git clone %(repository_url)s %(path)s' % env)
    
def create_virtualenv():
    """Make virtualenv"""
    if not files.exists('%(path)s/bin/activate' % env):
        run('virtualenv %(path)s' % env)
    
def install_app():
    """Run the setup.py"""
    with cd("%(path)s" % env):
        run('source bin/activate; python setup.py develop')    

def update_code():
    """Git pull the code repo"""
    with cd("%(path)s" % env):
        run('git pull origin master')
        
def setup_config():
    """Upload the config file which should not be checked into version control."""
    put("fixcity/config.ini", "%(path)s/fixcity/config.ini" % env)
    
def setup_apache():
    with cd("/etc/apache2/sites-available"):
        sudo("ln -s %(path)s/fixcity/apache/fixcity.conf ." % env)
    sudo("a2ensite fixcity.conf")
    sudo("/etc/init.d/apache2 restart")
