"""
Work around Django only supporting a single tests.py file by default.

This will load test suites from all files named test*py in the tests package.

Could have been done by creating a custom test runner as per
http://docs.djangoproject.com/en/dev/topics/testing/#using-different-testing-frameworks
but this is easier.

A more complete version was posted here:
http://www.djangosnippets.org/snippets/1972/

"""

import glob
import os
import unittest

def suite():
    # for some reason django does not expect this to be a TestSuite instance;
    # rather it must be a zero-arg callable that returns a TestSuite.

    here = os.path.abspath(os.path.dirname(__file__))
    testfiles = glob.glob(here + '/test*py')
    testmodules = [os.path.splitext(os.path.basename(name))[0]
                   for name in testfiles]
    testmodules = [__name__ + '.' + name for name in testmodules]
    
    #_suite = unittest.TestSuite()
    return unittest.defaultTestLoader.loadTestsFromNames(testmodules)
    #return _suite

