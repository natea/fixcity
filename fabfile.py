# Fixcity Fabfile

from fabric.api import *

"""
Base configuration
"""
env.project_name = 'fixcity'
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
    # setup_virtualenv()
    # clone_repo()
    # checkout_latest()
    # destroy_database()
    # create_database()
    # load_data()
    # install_requirements()
    # install_apache_conf()

def install_packages():
    """Installs packages required by the djangozoom webapp & worker."""

    pkgs = ['build-essential',
            'libgeos-dev',
            'libjpeg-dev',
            'libpq-dev',
            'libxml2-dev',
            'libxslt1-dev',
            'postgis',
            'postgresql-8.4',
            'postgresql-server-dev-8.4',
            'proj',
            'python',
            'python-dev']
    sudo("apt-get update -y")
    sudo("apt-get upgrade -y")
    sudo('DEBIAN_FRONTEND=noninteractive apt-get install --no-install-recommends -q -y '+' '.join(pkgs))
    
def checkout_code():
    """Check out the Fixcity code from Github"""
    run('git clone %(repository_url)s %(path)s' % env)
    