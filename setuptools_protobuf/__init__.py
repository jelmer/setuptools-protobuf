import os
import platform
import subprocess
import sys
import urllib.request
import zipfile

from setuptools import Command
from setuptools.dist import Distribution
from setuptools.errors import ExecError, PlatformError  # type: ignore

__version__ = (0, 1, 12)


def has_protobuf(command):
    return bool(getattr(command.distribution, 'protobufs', []))


class build_protobuf(Command):
    user_options = [('protoc', None, 'path of compiler protoc')]
    description = 'build .proto files'

    def initialize_options(self):
        self.protoc = (
            os.environ.get('PROTOC')
            or get_protoc(getattr(self.distribution, 'protoc_version'))
            or find_executable('protoc'))
        self.outfiles = []

    def finalize_options(self):
        if self.protoc is None or not os.path.exists(self.protoc):
            raise PlatformError(
                "Unable to find protobuf compiler %s"
                % (self.protoc or 'protoc'))

    def run(self):
        for protobuf in getattr(self.distribution, 'protobufs', []):
            source_mtime = os.path.getmtime(protobuf.path)
            for output in protobuf.outputs():
                try:
                    output_mtime = os.path.getmtime(output)
                except FileNotFoundError:
                    break
                else:
                    if output_mtime < source_mtime:
                        break
            else:
                continue
            command = [self.protoc, '--python_out=.']
            if protobuf.mypy:
                command.append('--mypy_out=.')
            command.append(protobuf.path)
            sys.stderr.write(
                'creating %r from %s\n' % (protobuf.outputs(), protobuf.path))
            # TODO(jelmer): Support e.g. building mypy ?
            try:
                subprocess.check_call(command, )
            except subprocess.CalledProcessError as e:
                raise ExecError(f'error running protoc: {e.returncode}')
            self.outfiles.extend(protobuf.outputs())

    def get_inputs(self):
        return [
            protobuf.path
            for protobuf in self.distribution.protobufs]  # type: ignore

    def get_outputs(self):
        return self.outfiles


class clean_protobuf(Command):
    description = 'clean .proto files'

    def run(self):
        for protobuf in getattr(self, 'protobufs', []):
            for output in protobuf.outputs():
                try:
                    os.unlink(output)
                except FileNotFoundError:
                    pass

    def initialize_options(self):
        pass

    def finalize_options(self):
        pass


def load_pyproject_config(dist: Distribution, cfg) -> None:
    mypy = cfg.get("mypy")
    dist.protoc_version = cfg.get("protoc_version")  # type: ignore
    dist.protobufs = [  # type: ignore
        Protobuf(pb, mypy=mypy) for pb in cfg.get("protobufs")]


def pyprojecttoml_config(dist: Distribution) -> None:
    build = dist.get_command_class("build")
    build.sub_commands.insert(0, ("build_protobuf", has_protobuf))
    clean = dist.get_command_class("clean")
    clean.sub_commands.insert(0, ("clean_protobuf", has_protobuf))

    dist.protoc_version = None  # type: ignore

    if sys.version_info[:2] >= (3, 11):
        from tomllib import load as toml_load
    else:
        from tomli import load as toml_load
    try:
        with open("pyproject.toml", "rb") as f:
            cfg = toml_load(f).get("tool", {}).get("setuptools-protobuf")
    except FileNotFoundError:
        pass
    else:
        if cfg:
            load_pyproject_config(dist, cfg)


class Protobuf:

    def __init__(self, path, mypy=None):
        self.path = path
        if mypy is None:
            mypy = find_executable('protoc-gen-mypy') is not None
        self.mypy = mypy

    def outputs(self):
        return [self.path[:-len('.proto')] + '_pb2.py']


def protobufs(dist, keyword, value):
    for protobuf in value:
        if not isinstance(protobuf, Protobuf):
            raise TypeError(protobuf)

    dist.protobufs = value


def find_executable(executable):
    _, ext = os.path.splitext(executable)
    if sys.platform == 'win32' and ext != '.exe':
        executable = executable + '.exe'

    if os.path.isfile(executable):
        return executable

    path = os.environ.get('PATH', os.defpath)
    # PATH='' doesn't match, whereas PATH=':' looks in the current directory
    if not path:
        return None

    paths = path.split(os.pathsep)
    for p in paths:
        f = os.path.join(p, executable)
        if os.path.isfile(f):
            return f
    return None


def get_protoc(version):
    # handle if no version requested (use system/env)
    if version is None:
        return None

    # determine the release string including system and machine info of protoc
    machine = platform.machine()
    if machine in ['amd64', 'x64', 'x86_64']:
        machine = 'x86_64'
    elif machine in ['aarch64', 'arm64', 'aarch_64']:
        machine = 'aarch_64'
    elif machine in ['i386', 'i686', 'x86', 'x86_32']:
        machine = 'x86_32'
    elif machine in ['ppc64le', 'ppcle64', 'ppcle_64']:
        machine = 'ppcle_64'
    elif machine in ['s390', 's390x', 's390_64']:
        machine = 's390_64'

    system = platform.system()
    if system == 'Linux':
        release = f'protoc-{version}-linux-{machine}'
    elif system == 'Darwin':
        assert machine in ['x86_64', 'aarch_64']
        release = f'protoc-{version}-osx-{machine}'
    elif system == 'Windows':
        assert machine in ['x86_64', 'x86_32']
        if machine == 'x86_64':
            release = f'protoc-{version}-win64'
        elif machine == 'x86_32':
            release = f'protoc-{version}-win32'

    path = os.path.join(os.path.dirname(__file__), release)
    executable = os.path.join(path, 'bin', 'protoc')
    if system == 'Windows':
        executable = executable + '.exe'

    # if we already have it downloaded, return it
    if os.path.exists(executable):
        return executable

    # otherwise download
    zip_name = f'{release}.zip'
    zip_dest = os.path.join(os.path.dirname(__file__), zip_name)
    base_url = 'https://github.com/protocolbuffers/protobuf/releases/download'
    release_url = f'{base_url}/v{version}/{zip_name}'
    urllib.request.urlretrieve(url=release_url, filename=zip_dest)
    zipfile.ZipFile(zip_dest).extractall(path)

    assert os.path.exists(executable)
    if system != 'Windows':
        # zip format doesn't always handle unix permissions well
        # mark the executable as executable in case it isn't
        os.chmod(executable, 0o777)
    return executable
