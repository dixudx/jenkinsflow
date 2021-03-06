# Copyright (c) 2012 - 2015 Lars Hupfeldt Nielsen, Hupfeldt IT
# All rights reserved. This work is under a BSD license, see LICENSE.TXT.

from __future__ import print_function

import sys, os, shutil, importlib, datetime, tempfile, psutil, setproctitle
from os.path import join as jp
import multiprocessing
from .api_base import BuildResult, Progress, UnknownJobException, ApiInvocationMixin

here = os.path.abspath(os.path.dirname(__file__))

def _mkdir(path):
    try:
        os.mkdir(path)
    except OSError:
        if not os.path.exists(path):
            raise


def _pgrep(proc_name):
    """Returns True if a process with name 'proc_name' is running, else False"""
    try:
        for proc in psutil.process_iter():
            if proc_name == proc.name():
                return True
    except psutil.NoSuchProcess:
        return False
    return False


_build_res = None


def set_build_result(res):
    global _build_res
    _build_res = res


def _get_build_result():
    return _build_res


class LoggingProcess(multiprocessing.Process):
    proc_name_prefix = "jenkinsflow_script_api_"

    def __init__(self, group=None, target=None, output_file_name=None, workspace=None, name=None, args=()):
        self.user_target = target
        super(LoggingProcess, self).__init__(group=group, target=self.run_job_wrapper, name=name, args=args)
        self.output_file_name = output_file_name
        self.workspace = workspace

    def run_job_wrapper(self, *args):
        setproctitle.setproctitle(self.proc_name_prefix + self.name)

        rc = 0
        set_build_result(None)
        os.chdir(self.workspace)
        try:
            rc = self.user_target(*args)
        except Exception as ex:  # pylint: disable=broad-except
            print("jenkinsflow.script_api: Caught exception from job script:", ex)
            rc = 1

        sbr = _get_build_result()
        if sbr == None:
            sys.exit(rc)
        if sbr == 'unstable':
            sys.exit(2)
        print("jenkinsflow.script_api: Unknown requested build result:", sbr)
        sys.exit(1)

    def run(self):
        sys.stdout = sys.stderr = open(self.output_file_name, 'w', buffering=0)
        super(LoggingProcess, self).run()


class Jenkins(object):
    """Optimized minimal set of methods needed for jenkinsflow to directly execute python code instead of invoking Jenkins jobs.

    THIS IS CONSIDERED EXPERIMENTAL
    THIS DOES NOT SUPPORT CONCURRENT INVOCATIONS OF FLOW

    There is no concept of job queues or executors, so if your flow depends on these for correctness, you wil experience different behaviour
    when using this api instead of the real Jenkins.

    Args:
        direct_uri (str): Path to dir with 'job' method python modules. Modules named <job-name>.py will be imported from this directory.
            If no module exists for a specific jobname, the module called 'default.py' will be imported.
            The modules must contain at method called 'run_job' with the following signature:

                run_job(job_name, job_prefix_filter, username, password, securitytoken, cause, build_params)

                A return value of 0 is 'SUCCESS'
                A return value of 1 or any exception raised is 'FAILURE'
                Other return values means 'UNSTABLE'

                set_build_result.set_build_result() can be used in run_job to set result to 'unstable' (executing `jenkinsflow set_build_result` has no effect)
                    This is mainly for compatibility with the other APIs, it is simpler to return 2 from run_job.

        job_prefix_filter (str): Passed to 'run_job'. ``jenkinsflow`` puts no meaning into this parameter.
        username (str): Passed to 'run_job'. ``jenkinsflow`` puts no meaning into this parameter.
        password (str): Passed to 'run_job'. ``jenkinsflow`` puts no meaning into this parameter.
        **kwargs: Ignored for compatibility with the other jenkins apis
    """

    def __init__(self, direct_uri, job_prefix_filter=None, username=None, password=None, log_dir=tempfile.gettempdir(), **kwargs):
        self.job_prefix_filter = job_prefix_filter
        self.username = username
        self.password = password
        self.public_uri = self.baseurl = direct_uri
        self.log_dir = log_dir
        self.jobs = {}

    def poll(self):
        pass

    def quick_poll(self):
        pass

    def queue_poll(self):
        pass

    def _script_file(self, job_name):
        return jp(self.public_uri, job_name + '.py')

    def _workspace(self, job_name):
        return jp(self.public_uri, job_name)

    def get_job(self, name):
        job = self.jobs.get(name)
        if not job:
            script_file = script_file1 = self._script_file(name)
            if not os.path.exists(script_file):
                script_file = self._script_file('default')
                if not os.path.exists(script_file):
                    raise UnknownJobException(script_file1 + ' or ' + script_file)

            script_dir = os.path.dirname(script_file)
            if script_dir not in sys.path:
                sys.path.append(script_dir)

            try:
                user_module = importlib.import_module(os.path.basename(script_file).replace('.py', ''), package=None)
            except (ImportError, SyntaxError) as ex:
                raise UnknownJobException(repr(script_file) + ' ' + repr(ex))

            try:
                func = user_module.run_job
            except AttributeError as ex:
                raise UnknownJobException(script_file + repr(ex))
            job = self.jobs[name] = ApiJob(jenkins=self, name=name, script_file=script_file, workspace=self._workspace(name), func=func)
        return job

    def create_job(self, job_name, config_xml):
        script_file = self._script_file(job_name)
        _mkdir(os.path.dirname(script_file))
        with open(script_file, 'w') as ff:
            ff.write(config_xml)

    def delete_job(self, job_name):
        script_file = self._script_file(job_name)
        try:
            os.unlink(script_file)
        except OSError as ex:
            if not os.path.exists(script_file):
                raise UnknownJobException(script_file + repr(ex))
            raise

        try:
            shutil.rmtree(self._workspace(job_name))
        except OSError as ex:
            if os.path.exists(script_file):
                raise

    def set_build_description(self, job_name, build_number, description, replace=False, separator='\n'):
        """Utility to set/append build description. :py:obj:`description` will be written to a file in the workspace.
        Args
            job_name (str)
            build_number (int)
            description (str): The description to set on the build
            append (bool):     If True append to existing description, if any
            separator (str):   A separator to insert between any existing description and the new :py:obj:`description` if :py:obj:`append` is True.
        """
        workspace = self._workspace(job_name)
        mode = 'w' if replace else 'a'
        with open(jp(workspace, 'description.txt'), mode) as ff:
            ff.write(description)


class ApiJob(object):
    def __init__(self, jenkins, name, script_file, workspace, func):
        self.jenkins = jenkins
        self.name = name

        self.build = None
        self.public_uri = self.baseurl = script_file
        self.workspace = workspace
        self.func = func
        self.log_file = jp(self.jenkins.log_dir, self.name + '.log')
        self.build_num = None
        self._invocations = []
        self.queued_why = None
        self.old_build_number = None

    def invoke(self, securitytoken, build_params, cause, description):
        _mkdir(self.jenkins.log_dir)
        _mkdir(self.workspace)
        self.build_num = self.build_num or 0
        self.build_num += 1
        fixed_args = [self.name, self.jenkins.job_prefix_filter, self.jenkins.username, self.jenkins.password, securitytoken, cause]
        fixed_args.append(build_params if build_params else {})
        proc = LoggingProcess(target=self.func, output_file_name=self.log_file, workspace=self.workspace, name=self.name, args=fixed_args)
        self.build = Invocation(self, proc, self.build_num)
        self._invocations.append(self.build)
        return self.build

    def poll(self):
        pass

    def job_status(self):
        """Result, progress and latest buildnumber info for the JOB NOT the invocation

        Return (result, progress_info, latest_build_number) (str, str, int or None):
            Note: Always returns result == BuildResult.UNKNOWN and latest_build_number == None
        """

        progress = Progress.RUNNING if _pgrep(LoggingProcess.proc_name_prefix + self.name) else Progress.IDLE
        result = BuildResult.UNKNOWN
        return (result, progress, None)

    def stop_all(self):
        # TODO stop ALL
        if self.build:
            self.build.proc.terminate()

    def update_config(self, config_xml):
        _mkdir(os.path.dirname(self.public_uri))
        with open(self.public_uri, 'w') as ff:
            ff.write(config_xml)

    def __repr__(self):
        return str(self.name)


class Invocation(ApiInvocationMixin):
    def __init__(self, job, proc, build_number):
        self.job = job
        self.proc = proc
        self.build_number = build_number
        self.queued_why = None

        # Export some of the same variables that Jenkins does
        os.environ.update(dict(
            BUILD_NUMBER=repr(self.build_number),
            BUILD_ID=datetime.datetime.isoformat(datetime.datetime.utcnow()),
            BUILD_DISPLAY_NAME='#' + repr(self.build_number),
            JOB_NAME=self.job.name,
            BUILD_TAG='jenkinsflow-' + self.job.name + '-' + repr(self.build_number),
            EXECUTOR_NUMBER=repr(self.proc.pid),
            NODE_NAME='master',
            NODE_LABELS='',
            WORKSPACE=self.job.workspace,
            JENKINS_HOME=self.job.jenkins.public_uri,
            JENKINS_URL=self.job.jenkins.public_uri,
            HUDSON_URL=self.job.jenkins.public_uri,
            BUILD_URL=jp(self.job.public_uri, repr(self.build_number)),
            JOB_URL=self.job.public_uri,
        ))

        self.proc.start()

    def status(self):
        if self.proc.is_alive():
            return (BuildResult.UNKNOWN, Progress.RUNNING)
        rc = self.proc.exitcode
        if rc == 0:
            return (BuildResult.SUCCESS, Progress.IDLE)
        if rc == 1:
            return (BuildResult.FAILURE, Progress.IDLE)
        return (BuildResult.UNSTABLE, Progress.IDLE)

    def stop(self, dequeue):  # pylint: disable=unused-argument
        self.proc.terminate()

    def console_url(self):
        # return self.job.public_uri + ' - ' + self.job.log_file
        return self.job.log_file

    def __repr__(self):
        return self.job.name + " #" + repr(self.build_number)
