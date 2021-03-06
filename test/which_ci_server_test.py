# Copyright (c) 2015 Lars Hupfeldt Nielsen, Hupfeldt IT
# All rights reserved. This work is under a BSD license, see LICENSE.TXT.

import os, multiprocessing
import bottle

from pytest import raises

from jenkinsflow import jenkins_api
from .cfg import ApiType
from .framework import api_select
from .framework.utils import assert_lines_in


here = os.path.abspath(os.path.dirname(__file__))


@bottle.route('/')
def index():
    return bottle.static_file('which_ci_server.html', root=here)


@bottle.route('/api/json')
def api():
    return bottle.static_file('which_ci_server.html', root=here)


_host = 'localhost'
_port = 8082


def server():
    bottle.run(host=_host, port=_port, debug=True)


def test_which_ci_server_not_ci():
    proc = None
    try:
        with api_select.api(__file__) as api:
            if api.api_type != ApiType.JENKINS:
                return

            proc = multiprocessing.Process(target=server)
            proc.start()

            with raises(Exception) as exinfo:
                jenkins_api.Jenkins("http://" + _host + ':' + repr(_port), "dummy").poll()
    
            assert_lines_in(
                exinfo.value.message,
                 "Not connected to Jenkins or Hudson (expected X-Jenkins or X-Hudson header, got: "
            )

    finally:
        if proc:
            proc.terminate()
