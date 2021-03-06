# Copyright (c) 2012 - 2015 Lars Hupfeldt Nielsen, Hupfeldt IT
# All rights reserved. This work is under a BSD license, see LICENSE.TXT.

from pytest import raises

import re

from jenkinsflow.flow import parallel, serial, MissingJobsException, FailedChildJobsException, FailedChildJobException, UnknownJobException
from .framework import api_select
from .framework.utils import assert_lines_in
from .cfg import ApiType


def test_missing_jobs_not_allowed():
    with api_select.api(__file__) as api:
        api.flow_job()
        api.job('j1', 0.01, max_fails=0, expect_invocations=0, expect_order=None)
        api.job('j2', 0.01, max_fails=0, expect_invocations=0, expect_order=None)

        with raises(MissingJobsException) as exinfo:
            with serial(api, 20, job_name_prefix=api.job_name_prefix) as ctrl1:
                ctrl1.invoke('j1')
                ctrl1.invoke('missingA')
                ctrl1.invoke('j2')

        assert_lines_in(
            exinfo.value.message,
            re.compile("^Job not found: .*jenkinsflow_test__missing_jobs_not_allowed__missingA")
        )

        with raises(MissingJobsException):
            with serial(api, 20, job_name_prefix=api.job_name_prefix) as ctrl1:
                ctrl1.invoke('j1')
                ctrl1.invoke('missingA')
                with ctrl1.parallel() as ctrl2:
                    ctrl2.invoke('missingB')
                    ctrl2.invoke('j2')
                ctrl1.invoke('missingC')


def test_missing_jobs_allowed_still_missing_parallel():
    with api_select.api(__file__) as api:
        api.flow_job()
        api.job('j1', 0.01, max_fails=0, expect_invocations=1, expect_order=1)
        api.job('j2', 0.01, max_fails=0, expect_invocations=1, expect_order=1)

        with raises(FailedChildJobsException):
            with parallel(api, 20, job_name_prefix=api.job_name_prefix, allow_missing_jobs=True) as ctrl1:
                ctrl1.invoke('j1')
                ctrl1.invoke('missingA')
                ctrl1.invoke('j2')


def test_missing_jobs_allowed_still_missing_serial():
    with api_select.api(__file__) as api:
        api.flow_job()
        api.job('j1', 0.01, max_fails=0, expect_invocations=1, expect_order=1)
        api.job('j2', 0.01, max_fails=0, expect_invocations=0, expect_order=None)

        with raises(FailedChildJobException):
            with serial(api, 20, job_name_prefix=api.job_name_prefix, allow_missing_jobs=True) as ctrl1:
                ctrl1.invoke('j1')
                ctrl1.invoke('missingA')
                ctrl1.invoke('j2')


def test_missing_jobs_allowed_still_missing_parallel_serial():
    with api_select.api(__file__) as api:
        api.flow_job()
        api.job('j1', 0.01, max_fails=0, expect_invocations=1, expect_order=1)
        api.job('j2', 0.01, max_fails=0, expect_invocations=0, expect_order=None)

        with raises(FailedChildJobsException):
            with parallel(api, 20, job_name_prefix=api.job_name_prefix, allow_missing_jobs=True) as ctrl1:
                ctrl1.invoke('j1')
                ctrl1.invoke('missingA')
                with ctrl1.serial() as ctrl2:
                    ctrl2.invoke('missingB')
                    ctrl2.invoke('j2')
                ctrl1.invoke('missingC')


def test_missing_jobs_allowed_created_serial_parallel():
    with api_select.api(__file__) as api:
        if api.api_type == ApiType.SCRIPT:
            # TODO: Handle ApiType.SCRIPT
            return

        with api.job_creator():
            api.flow_job()
            api.job('j1', 0.01, max_fails=0, expect_invocations=1, expect_order=1, create_job='missingA')
            api.job('missingA', 0.01, max_fails=0, expect_invocations=1, expect_order=2, flow_created=True, create_job='missingB')
            api.job('missingB', 0.01, max_fails=0, expect_invocations=1, expect_order=3, flow_created=True)
            api.job('j2', 0.01, max_fails=0, expect_invocations=1, expect_order=3, create_job='missingC')
            api.job('missingC', 0.01, max_fails=0, expect_invocations=1, expect_order=4, flow_created=True)

        with serial(api, 20, job_name_prefix=api.job_name_prefix, allow_missing_jobs=True) as ctrl1:
            ctrl1.invoke('j1')
            ctrl1.invoke('missingA')
            with ctrl1.parallel() as ctrl2:
                ctrl2.invoke('missingB')
                ctrl2.invoke('j2')
            ctrl1.invoke('missingC')

        # TODO: Validate output


def test_missing_jobs_job_disappeared():
    with api_select.api(__file__) as api:
        if api.api_type in (ApiType.SCRIPT, ApiType.MOCK):
            # TODO: Handle ApiTypes
            return

        with api.job_creator():
            api.flow_job()
            api.job('j1', 0.01, max_fails=0, expect_invocations=1, expect_order=1)
            api.job('disappearing', 0.01, max_fails=0, expect_invocations=0, expect_order=None, disappearing=True)

        with raises(UnknownJobException):
            with serial(api, 20, job_name_prefix=api.job_name_prefix, allow_missing_jobs=True) as ctrl1:
                ctrl1.invoke('j1')
                ctrl1.invoke('disappearing')

        # TODO: Validate output
