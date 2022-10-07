import os
import sys
import subprocess

from distutils.spawn import find_executable
from setuptools.command.build_py import build_py


def protoc():
    try:
        return os.environ['PROTOC']
    except KeyError:
        pass

    protoc = find_executable('protoc')

    if protoc is None:
        sys.stderr.write('protoc not found. Is it installed?\n')
        sys.exit(1)

    return protoc


class build_protobuf(build_py):

    def run(self):
        for package in self.packages:
            packagedir = self.get_package_dir(package)

            for entry in os.scandir(packagedir):
                if not entry.name.endswith('.proto'):
                    continue

                output = entry.path[:-len('.proto')] + '_pb2.py'

                if (not os.path.exists(output)
                        or os.path.getmtime(entry.apth)
                        > os.path.getmtime(output)):
                    sys.stderr.write('Compiling protobuf file %s\n'
                                     % entry.path)
                    # TODO(jelmer): Support e.g. building mypy ?
                    subprocess.check_call(
                        [protoc(), '--python_out=.', entry.path])
