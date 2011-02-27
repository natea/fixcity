from setuptools import setup, find_packages

version='0.1dev'

install_requires=[
      'geopy>=geopy-0.93-f1',
      'sorl-thumbnail==3.2.2',
      'django>=1.1.1',
      'django-registration>=0.7',
      'psycopg2>=2.0.12',
      'PIL==1.1.6',
      'wsgilog>=0.2',
      'httplib2>=0.6',
      'poster',
      'mock',
      'south==0.7.3',
      'tweepy',
      'python-bitly',
      'django-basic-apps',
      'django-flash',
      'django_flash_templatetag',
      'django_pagination',
      'coverage',
      'django-voting==0.1',
      'django-attachments',
      'recaptcha-client',
      'lxml',
      'reportlab',
#      'django_compressor',
      'Fabric',
      ]

import sys
if sys.version_info[:2] < (2, 6):
    install_requires.append('ctypes>=1.0.2')


setup(name='fixcity',
      version=version,
      description="Build me a bike rack!",
      author="Ivan Willig, Paul Winkler, Sonali Sridhar, Andy Cochran, etc.",
      author_email="iwillig@opengeo.org",
      url="http://www.plope.com/software/ExternalEditor",
      zip_safe=False,
      scripts=[],
      license='AGPL',
      packages=find_packages(),
      dependency_links=[
        'http://svn.openplans.org/eggs/geopy-0.93-f1.tar.gz#egg=geopy-0.93-f1',
        'http://dist.repoze.org/PIL-1.1.6.tar.gz#egg=PIL-1.1.6',
        'http://sourceforge.net/projects/ctypes/files/ctypes/1.0.2/ctypes-1.0.2.tar.gz/download#egg=ctypes-1.0.2',
        'https://svn.openplans.org/eggs/httplib2-0.4.0.zip',
        'https://svn.openplans.org/eggs/python-bitly-0.1.tar.gz',
        'https://source.openplans.org/eggs/django-basic-apps-0.6.tar.gz',
        'https://source.openplans.org/eggs/django_flash_templatetag-0.1.tar.gz',
        'http://www.aeracode.org/releases/south/south-0.6.2.tar.gz',
        'http://svn.openplans.org/eggs/django-voting-0.1.tar.gz',
        'http://svn.openplans.org/eggs/wsgilog-0.2.tar.gz',
        ],
      install_requires=install_requires,
      )
