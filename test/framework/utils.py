# Copyright (c) 2012 - 2014 Lars Hupfeldt Nielsen, Hupfeldt IT
# All rights reserved. This work is under a BSD license, see LICENSE.TXT.

import os, re, tempfile
from os.path import join as jp
import pytest

from .config import flow_graph_root_dir
from jenkinsflow.test import cfg as test_cfg
from jenkinsflow.test.cfg import ApiType


_console_url_script_api_log_file_msg_prefix = ' - ' + tempfile.gettempdir() + '/'
_result_msg_script_api_log_file_msg_prefix = tempfile.gettempdir() + '/'


def console_url(api, job_name, num):
    if api.api_type == ApiType.SCRIPT:
        return test_cfg.script_dir() + '/' + job_name + '.py' + _console_url_script_api_log_file_msg_prefix + job_name + '.log'
    return 'http://x.x/job/' + job_name + '/' + (str(num) + "/console" if api.api_type == ApiType.MOCK else "")


def result_msg(api, job_name, num=None):
    if api.api_type == ApiType.SCRIPT:
        return repr(job_name) + " - build: " + _result_msg_script_api_log_file_msg_prefix + job_name + '.log'
    return repr(job_name) + " - build: http://x.x/job/" + job_name + "/" + (str(num) + "/console" if api.api_type == ApiType.MOCK and num else "")


_http_re = re.compile(r'https?://.*?/job/([^/" ]*)(/?)')
if test_cfg.selected_api() != ApiType.SCRIPT:
    def replace_host_port(contains_url):
        return _http_re.sub(r'http://x.x/job/\1\2', contains_url)
else:
    def replace_host_port(contains_url):
        return _http_re.sub(r'/tmp/jenkinsflow-test/job/\1.py', contains_url)


def assert_lines_in(text, *expected_lines):
    """Assert that `*expected_lines` occur in order in the lines of `text`.

    Args:
        *expected_lines (str or RegexObject (hasattr `match`)): For each `expected_line` in expected_lines:
            If `expected_line` has a match method it is called and must return True for a line in `text`.
            Otherwise, if the `expected_line` starts with '^', a line in `text` must start with `expected_line[1:]`
            Otherwise `expected line` must simply occur in a line in `text`
    """
    assert expected_lines

    fixed_expected = []
    for expected in expected_lines:
        fixed_expected.append(replace_host_port(expected) if not hasattr(expected, 'match') else expected)

    max_index = len(fixed_expected)
    index = 0

    for line in text.split('\n'):
        line = replace_host_port(line)
        expected = fixed_expected[index]

        if hasattr(expected, 'match'):
            if expected.match(line):
                index += 1
                if index == max_index:
                    return
            continue

        if expected.startswith('^'):
            if line.startswith(expected[1:]):
                index += 1
                if index == max_index:
                    return
            continue

        if expected in line:
            index += 1
            if index == max_index:
                return

    if hasattr(expected, 'match'):
        pytest.fail("\n\nThe regex:\n\n" + repr(expected.pattern) + "\n\n    --- NOT MATCHED or OUT OF ORDER in ---\n\n" + text)  # pylint: disable=no-member

    if expected.startswith('^'):
        pytest.fail("\n\nThe text:\n\n" + repr(expected[1:]) + "\n\n    --- NOT FOUND, OUT OF ORDER or NOT AT START OF LINE in ---\n\n" + text)  # pylint: disable=no-member

    pytest.fail("\n\nThe text:\n\n" + repr(expected) + "\n\n    --- NOT FOUND OR OUT OF ORDER IN ---\n\n" + text)  # pylint: disable=no-member


def flow_graph_dir(flow_name):
    """Control which directory to put flow graph in.

    Put the generated graph in the workspace root if running from Jenkins.
    If running from commandline put it under config.flow_graph_root_dir/flow_name

    Return: dir-name
    """
    return '.' if os.environ.get('JOB_NAME') else jp(flow_graph_root_dir, flow_name)
