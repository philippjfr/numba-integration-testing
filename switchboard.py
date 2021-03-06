#!/usr/bin/env python

import argparse
import inspect
import os
import shlex
import subprocess
import sys
import json

MINICONDA_BASE_URL = "https://repo.continuum.io/miniconda/"
MINCONDA_FILE_TEMPLATE = "Miniconda3-latest-{}.sh"
MINCONDA_INSTALLER = "miniconda.sh"
MINCONDA_PATH = "miniconda3"
MINCONDA_FULL_PATH = os.path.join(os.getcwd(), MINCONDA_PATH)
MINCONDA_BIN_PATH = os.path.join(MINCONDA_FULL_PATH, "bin")
MINCONDA_CONDABIN_PATH = os.path.join(MINCONDA_FULL_PATH, "condabin")

LINUX_X86 = "Linux-x86"
LINUX_X86_64 = "Linux-x86_64"
MACOSX_X86_64 = "MacOSX-x86_64"

STAGE_MINICONDA = "miniconda"
STAGE_CLONE = "clone"
STAGE_ENVIRONMENT = "environment"
STAGE_INSTALL = "install"
STAGE_TESTS = "tests"
ALL_STAGES = [
    STAGE_MINICONDA,
    STAGE_CLONE,
    STAGE_ENVIRONMENT,
    STAGE_INSTALL,
    STAGE_TESTS,
]


PREFIX = "::>>"


def echo(value):
    print("{} {}".format(PREFIX, value))


def execute(command, capture=False):
    echo("running: '{}'".format(command))
    if capture:
        return subprocess.check_output(shlex.split(command))
    else:
        subprocess.check_call(shlex.split(command))


UNAME = execute("uname", capture=True).strip().decode("utf-8")


def miniconda_url():
    if UNAME == "Linux":
        filename = MINCONDA_FILE_TEMPLATE.format(LINUX_X86_64)
    elif UNAME == "Darwin":
        filename = MINCONDA_FILE_TEMPLATE.format(MACOSX_X86_64)
    else:
        raise ValueError("Unsupported OS")
    return MINICONDA_BASE_URL + filename


def wget_conda(url, output):
    execute("wget {} -O {}".format(url, output))


def install_miniconda(install_path):
    execute("bash miniconda.sh -b -p {}".format(install_path))


def inject_conda_path():
    os.environ["PATH"] = ":".join(
        [MINCONDA_BIN_PATH, MINCONDA_CONDABIN_PATH]
        + os.environ["PATH"].split(":")
    )


def switch_environment_path(env):
    os.environ["PATH"] = ":".join(
        [os.path.join(conda_environments()[env], "bin")]
        + os.environ["PATH"].split(":")[1:]
    )


def git_clone(url):
    execute("git clone {}".format(url))


def git_clone_tag(url, tag, directory):
    execute("git clone -b {} {} --depth=1 {}".format(tag, url, directory))


def git_tag():
    return execute("git tag", capture=True).split('\n')


def git_ls_remote_tags(url):
    return [os.path.basename(line.split("\t")[1])
            for line in execute("git ls-remote --tags --refs {}".format(url),
            capture=True).decode("utf-8").split("\n") if line]


def git_checkout(tag):
    execute("git checkout {}".format(tag))


def conda_update_conda():
    execute("conda update -y -n base -c defaults conda")


def conda_environments():
    return dict(
        (
            (os.path.basename(i), i)
            for i in json.loads(
                execute("conda env list --json", capture=True)
            )["envs"]
        )
    )


def conda_create_env(name):
    execute("conda create -y -n {}".format(name))


def conda_install_numba_dev(env):
    execute("conda install -y -n {} -c numba/label/dev numba numpy"
            .format(env))


def conda_install(env, target):
    execute("conda install -y -n {} {}".format(env, target))


class NumbaIntegrationTestTarget(object):
    """ Subclass this to add metadata for a target. """
    @property
    def name(self):
        """ Name of the target.

        This will be used as the directory to clone into as well as selecting
        the target from the command line.

        Returns
        -------
        name : str
            The name of the target.

        """
        raise NotImplementedError

    @property
    def clone_url(self):
        """ Canonical clone url for the target.

        This will be used to clone the project if needed. If you omit this, the
        project will not be cloned and it is assumed that the target ships
        with tests. The url will be handed of directly to 'git
        clone' so it has to be compatible with that.

        Returns
        -------
        url : str
            A 'git clone' compatible url.

        """
        raise NotImplementedError

    @property
    def target_tag(self):
        """ The target tag to checkout.

        This function must work out which tag should be checked out and
        return that. A good start is to use `git_ls_remote_tags(self.clone_url)`
        to obtain a list of tags from the remote. If you specify `clone_url`
        you should also specify this.

        Returns
        -------
        tag : str
            The target tag to checkout.

        """
        raise NotImplementedError

    @property
    def conda_dependencies(self):
        """ Conda dependencies for this project.

        The conda dependencies for this project. If you need to install things
        in a specific order with multiple, subsequent, `conda` calls, use
        multiple strings. You can include any channel information such as `-c
        numba` in the string.

        Returns
        -------
        dependencies : list of str
            All conda dependencies.
        """
        raise NotImplementedError

    def install(self):
        """ Execute command to install the target.

        Use this to execute the command or commands you need to install the
        project. If you specified a `clone_url` you may assume that the
        commands will be executed inside the root directory of your clone.

        """
        raise NotImplementedError

    def run_tests(self):
        """ Execute command to run tests.

        Use this to execute the command or commands you need to run the
        test-suite. If you specified a `clone_url` you may assume that the
        commands will be executed inside the root directory of your clone.

        """
        raise NotImplementedError

    @property
    def needs_clone(self):
        try:
            self.clone_url
        except NotImplementedError:
            return False
        else:
            return True

    @property
    def needs_checkout(self):
        try:
            self.target_tag
        except NotImplementedError:
            return False
        else:
            return True


class UmapTests(NumbaIntegrationTestTarget):
    @property
    def name(self):
        return "umap"

    @property
    def clone_url(self):
        return "https://github.com/lmcinnes/umap"

    @property
    def target_tag(self):
        return([t for t in git_ls_remote_tags(self.clone_url) if not
                t.startswith("v")][-1])

    @property
    def conda_dependencies(self):
        return ["numpy scikit-learn scipy nose"]

    def install(self):
        execute("pip install -e .")

    def run_tests(self):
        execute("nosetests -s umap")


class HpatTests(NumbaIntegrationTestTarget):
    @property
    def name(self):
        return "hpat"

    @property
    def conda_dependencies(self):
        return ["pyspark openjdk scipy", "-c ehsantn h5py"]

    def install(self):
        conda_install(
            self.name, "-c ehsantn -c anaconda -c conda-forge hpat"
        )

    def run_tests(self):
        execute("python -m hpat.tests.gen_test_data")
        execute("python -m hpat.runtests")


class LibrosaTests(NumbaIntegrationTestTarget):
    @property
    def name(self):
        return "librosa"

    @property
    def clone_url(self):
        return "https://github.com/librosa/librosa.git"

    @property
    def target_tag(self):
        return([t for t in git_ls_remote_tags(self.clone_url) if not
                t.startswith("v")][-1])

    @property
    def conda_dependencies(self):
        return [
            "pip numpy scipy coverage scikit-learn matplotlib pytest",
            "-c conda-forge ffmpeg pysoundfile",
        ]

    def install(self):
        execute("pip install --pre -e .[tests]")

    def run_tests(self):
        execute("pytest")


class CliffordTests(NumbaIntegrationTestTarget):

    @property
    def name(self):
        return "clifford"

    @property
    def clone_url(self):
        return "https://github.com/pygae/clifford.git"

    @property
    def target_tag(self):
        return(git_ls_remote_tags(self.clone_url)[-1])

    @property
    def conda_dependencies(self):
        return [
            "future numpy scipy numba pip nose h5py",
        ]

    def install(self):
        execute("python setup.py install")

    def run_tests(self):
        execute("nosetests")


class AwkwardTests(NumbaIntegrationTestTarget):
    @property
    def name(self):
        return "awkward"

    @property
    def clone_url(self):
        return "https://github.com/scikit-hep/awkward-array"

    @property
    def target_tag(self):
        return([t for t in git_ls_remote_tags(self.clone_url)
                if "rc" not in t][-1])

    @property
    def conda_dependencies(self):
        return ["numpy pytest"]

    def install(self):
        execute("python setup.py install")
        os.chdir("awkward-numba")
        execute("python setup.py install")
        os.chdir("..")

    def run_tests(self):
        execute("pytest -v tests/test_numba.py")   # only the test that uses Numba


class SparseTests(NumbaIntegrationTestTarget):

    @property
    def name(self):
        return "sparse"

    @property
    def clone_url(self):
        return "https://github.com/pydata/sparse.git"

    @property
    def target_tag(self):
        return git_ls_remote_tags(self.clone_url)[-1]

    @property
    def conda_dependencies(self):
        return ["pip numpy scipy"]

    def install(self):
        execute("pip install -e .[all]")

    def run_tests(self):
        execute("pytest")


class FastparquetTests(NumbaIntegrationTestTarget):

    @property
    def name(self):
        return "fastparquet"

    @property
    def clone_url(self):
        return "https://github.com/dask/fastparquet.git"

    @property
    def target_tag(self):
        return([t for t in git_ls_remote_tags(self.clone_url)
                if not t == "1.1"][-1])

    @property
    def conda_dependencies(self):
        return ["numpy pandas pytest<5.0.0"
                "brotli thrift python-snappy lz4 s3fs moto cython setuptools ",
                "-c conda-forge bson zstandard python-lzo",
                ]

    def install(self):
        execute("python setup.py install")

    def run_tests(self):
        os.environ["AWS_ACCESS_KEY_ID"] = "1111"
        os.environ["AWS_SECRET_ACCESS_KEY"] = "2222"
        execute("python setup.py test")
        os.environ.pop("AWS_ACCESS_KEY_ID")
        os.environ.pop("AWS_SECRET_ACCESS_KEY")


class PygbmTests(NumbaIntegrationTestTarget):

    @property
    def name(self):
        return "pygbm"

    @property
    def clone_url(self):
        return "https://github.com/ogrisel/pygbm.git"

    @property
    def target_tag(self):
        return(git_ls_remote_tags(self.clone_url)[-1])

    @property
    def conda_dependencies(self):
        return ["scipy scikit-learn pytest joblib lightgbm"]

    def install(self):
        execute("pip install --editable .")

    def run_tests(self):
        execute("pytest")


def bootstrap_miniconda():
    url = miniconda_url()
    if not os.path.exists(MINCONDA_INSTALLER):
        wget_conda(url, MINCONDA_INSTALLER)
    if not os.path.exists(MINCONDA_FULL_PATH):
        install_miniconda(MINCONDA_FULL_PATH)
    inject_conda_path()
    conda_update_conda()


def setup_git(target):
    if target.needs_clone:
        if not os.path.exists(target.name):
            git_clone_tag(target.clone_url, target.target_tag, target.name)
        os.chdir(target.name)


def setup_environment(target):
    if target.name not in conda_environments():
        conda_create_env(target.name)
        conda_install_numba_dev(target.name)
        for dep in target.conda_dependencies:
            conda_install(target.name, dep)


def switch_environment(target):
    switch_environment_path(target.name)


def print_environment_details(target):
    execute("conda env export -n {}".format(target.name))
    execute("numba -s")


def find_all_targets():
    return [
        obj()
        for name, obj in inspect.getmembers(sys.modules[__name__])
        if inspect.isclass(obj)
        and issubclass(obj, NumbaIntegrationTestTarget)
        and obj is not NumbaIntegrationTestTarget
    ]


AVAILABLE_TARGETS = dict(
    (target.name, target) for target in find_all_targets()
)


def parse_arguments():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-s",
        "--stages",
        nargs="*",
        type=str,
        choices=ALL_STAGES,
        default=ALL_STAGES,
        metavar="STAGE",
    )
    parser.add_argument(
        "-t",
        "--targets",
        nargs="*",
        type=str,
        choices=list(AVAILABLE_TARGETS.keys()),
        default=list(AVAILABLE_TARGETS.keys()),
        metavar="TARGET",
    )
    return parser.parse_args()


def main(stages, targets):
    failed = []
    basedir = os.getcwd()
    if STAGE_MINICONDA in stages:
        bootstrap_miniconda()
    else:
        inject_conda_path()
    for name, target in AVAILABLE_TARGETS.items():
        if name in targets:
            os.chdir(basedir)
            if STAGE_CLONE in stages:
                setup_git(target)
            if STAGE_ENVIRONMENT in stages:
                setup_environment(target)
            switch_environment(target)
            if STAGE_INSTALL in stages:
                target.install()
            print_environment_details(target)
            if STAGE_TESTS in stages:
                try:
                    target.run_tests()
                except subprocess.CalledProcessError:
                    failed.append(target.name)
    if STAGE_TESTS in stages:
        if failed:
            echo("The following tests failed: '{}'".format(failed))
            sys.exit(23)
        else:
            echo("All integration tests successful")


if __name__ == "__main__":
    args = parse_arguments()
    echo("stages are: '{}'".format(args.stages))
    echo("targets are: '{}'".format(args.targets))
    main(args.stages, args.targets)
