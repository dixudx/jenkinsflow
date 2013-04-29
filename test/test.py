#!/usr/bin/python

import sys, os
from os.path import join as jp
here = os.path.abspath(os.path.dirname(__file__))

sys.path.extend([jp(here, '../..'), jp(here, '../demo'), jp(here, '../../jenkinsapi')])
from jenkinsflow.jobcontrol import JobControlFailException
import nested, single_level, prefix, hide_password
import single_level_errors, multi_level_errors1, multi_level_errors2
import multi_level_mixed, no_args

os.chdir(here)

print "Runnning tests"
for test in no_args, multi_level_mixed:
    print ""
    print "==== Test:", test.__name__, "===="
    test.main()

print "Validating demos"
for demo in nested, single_level, single_level_errors, prefix:
    print ""
    print "==== Demo:", demo.__name__, "===="
    demo.main()

print "Validating demos"
for demo in hide_password, multi_level_errors1, multi_level_errors2:    
    print ""
    print "==== Demo:", demo.__name__, "===="
    try:
        demo.main()
    except JobControlFailException as ex:
        print "Ok, got exception:", ex
    else:
        raise Exception("Expected exception")
