# Copyright (c) 2012 - 2015 Lars Hupfeldt Nielsen, Hupfeldt IT
# All rights reserved. This work is under a BSD license, see LICENSE.TXT.

from jenkinsflow.flow import parallel, serial
from .framework import api_select


def test_single_level_serial():
    with api_select.api(__file__) as api:
        api.job('quick', 0.01, max_fails=0, expect_invocations=1, expect_order=1, params=(('s1', 'Hi', 'desc'), ('c1', ('true', 'maybe', 'false'), 'desc')))
        api.job('wait10', 10, max_fails=0, expect_invocations=1, expect_order=2, serial=True)
        api.job('wait5', 5, max_fails=0, expect_invocations=1, expect_order=3, serial=True)

        with serial(api, timeout=40, job_name_prefix=api.job_name_prefix, report_interval=1) as ctrl:
            ctrl.invoke('quick', password='X', s1='HELLO', c1=True)
            ctrl.invoke('wait10')
            ctrl.invoke('wait5')


def test_single_level_parallel():
    with api_select.api(__file__) as api:
        api.job('quick', 0.01, max_fails=0, expect_invocations=1, expect_order=1, params=(('s1', 'Hi', 'desc'), ('c1', ('true', 'maybe', 'false'), 'desc')))
        api.job('wait10', 10, max_fails=0, expect_invocations=1, expect_order=1)
        api.job('wait5', 5, max_fails=0, expect_invocations=1, expect_order=1)

        with parallel(api, timeout=20, job_name_prefix=api.job_name_prefix, report_interval=3) as ctrl:
            ctrl.invoke('quick', password='Y', s1='WORLD', c1='maybe')
            ctrl.invoke('wait10')
            ctrl.invoke('wait5')
