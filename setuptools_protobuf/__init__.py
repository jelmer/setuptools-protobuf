import os
import sys
import subprocess

from distutils.spawn import find_executable
from setuptools import Command
import setuptools.command.build


__version__ = (0, 1, 4)


def has_protobuf(command):
    return bool(getattr(command.distribution, 'protobufs', []))


class build_protobuf(Command):
    user_options = [('protoc', None, 'path of compiler protoc')]
    description = 'build .proto files'

    def initialize_options(self):
        self.protoc = os.environ.get('PROTOC') or find_executable('protoc')

    def finalize_options(self):
        if self.protoc is None or not os.path.exists(self.protoc):
            raise RuntimeError(
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
            subprocess.check_call(command)


setuptools.command.build.build.sub_commands.insert(
    0, ('build_protobuf', has_protobuf))


class clean_protobuf(Command):
    description = 'clean .proto files'

    def run(self):
        for protobuf in getattr(self, 'protobufs', []):
            for output in protobuf.outputs():
                try:
                    os.unlink(output)
                except FileNotFoundError:
                    pass


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
