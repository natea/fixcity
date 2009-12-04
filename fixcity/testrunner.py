"""
GIS-enabled test runner with code coverage support.
Based on http://www.thoughtspark.org/node/6

"""

from django.conf import settings
from django.contrib.gis.tests import run_tests as django_test_runner
import coverage
 
def test_runner_with_coverage(test_labels, verbosity=1, interactive=True,
                              extra_tests=[]):
    """Custom test runner.  Follows the django.test.simple.run_tests()
    interface."""

    do_coverage = hasattr(settings, 'COVERAGE_MODULES') and settings.COVERAGE_MODULES
    # Start code coverage before anything else if necessary
    if do_coverage:
        coverage.use_cache(0) # Do not cache any of the coverage.py stuff
        coverage.start()
 
    test_results = django_test_runner(test_labels, verbosity, interactive, extra_tests)
 

    if do_coverage:
        coverage.stop()
        # Print code metrics header
        print
        print '-' * 60
        print ' Unit Test Code Coverage Results'
        print '-' * 60
 
        coverage_modules = []
        for module in settings.COVERAGE_MODULES:
            coverage_modules.append(__import__(module, globals(), locals(),
                                               ['']))
 
        coverage.report(coverage_modules, show_missing=1)
 
        # Print code metrics footer
        print '-' * 60
 
    return test_results
