"""Setuptools extension for compiling .proto files."""

import os
import platform
import subprocess
import sys
import urllib.request
import zipfile
from pathlib import Path
from typing import Optional

from setuptools import Command
from setuptools.dist import Distribution
from setuptools.errors import ExecError, PlatformError  # type: ignore

__version__ = (0, 1, 14)


def has_protobuf(command):
    """Check if the command's distribution has protobuf files to compile.

    Args:
        command: A setuptools command instance.

    Returns:
        bool: True if the distribution has protobufs, False otherwise.
    """
    return bool(getattr(command.distribution, "protobufs", []))


class build_protobuf(Command):  # noqa: N801
    """Build .proto files."""

    user_options: list[tuple[str, Optional[str], str]] = [  # type: ignore
        ("protoc", None, "path of compiler protoc")
    ]
    description = "build .proto files"

    def initialize_options(self):
        """Initialize options for the build_protobuf command.

        Sets up the protoc compiler path and outfiles list.
        """
        self.protoc = (
            os.environ.get("PROTOC")
            or get_protoc(getattr(self.distribution, "protoc_version", None))
            or find_executable("protoc")
        )
        self.outfiles = []

    def finalize_options(self):
        """Finalize options for the build_protobuf command.

        Raises:
            PlatformError: If the protobuf compiler cannot be found.
        """
        if self.protoc is None or not os.path.exists(self.protoc):
            raise PlatformError(
                "Unable to find protobuf compiler %s" % (self.protoc or "protoc")
            )

    def run(self):
        """Execute the build_protobuf command.

        Compiles all .proto files in the distribution's protobufs list.
        Only recompiles if the source .proto file is newer than the output.

        Raises:
            ExecError: If protoc returns a non-zero exit code.
        """
        for protobuf in getattr(self.distribution, "protobufs", []):
            source_mtime = os.path.getmtime(protobuf.resolved_path)
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
            command = [self.protoc, f"--python_out={protobuf.outputs_path()}"]
            if protobuf.mypy:
                command.append(f"--mypy_out={protobuf.outputs_path()}")
            if protobuf.proto_path:
                command.append(f"--proto_path={protobuf.proto_path}")
            command.append(protobuf.resolved_path)
            sys.stderr.write(
                f"creating {protobuf.outputs()!r} from {protobuf.resolved_path}\n"
            )
            # TODO(jelmer): Support e.g. building mypy ?
            try:
                subprocess.check_call(
                    command,
                )
            except subprocess.CalledProcessError as e:
                raise ExecError(f"error running protoc: {e.returncode}")
            self.outfiles.extend(protobuf.outputs())

    def get_source_files(self) -> list[str]:
        """Return the list of source .proto files.

        Returns:
            list[str]: List of paths to .proto files.
        """
        return [protobuf.path for protobuf in self.distribution.protobufs]  # type: ignore

    def get_outputs(self) -> list[str]:
        """Return the list of output files for the command."""
        return self.outfiles


class clean_protobuf(Command):  # noqa: N801
    """Clean output of .proto files."""

    description = "clean .proto files"

    def run(self):
        """Execute the clean_protobuf command.

        Removes all generated Python files from .proto compilation.
        """
        for protobuf in getattr(self, "protobufs", []):
            for output in protobuf.outputs():
                try:
                    os.unlink(output)
                except FileNotFoundError:
                    pass

    def initialize_options(self):
        """Initialize options for the clean_protobuf command."""
        pass

    def finalize_options(self):
        """Finalize options for the clean_protobuf command."""
        pass


def load_pyproject_config(dist: Distribution, cfg) -> None:
    """Load setuptools-protobuf configuration from pyproject.toml.

    Args:
        dist: The setuptools Distribution instance.
        cfg: Configuration dictionary from pyproject.toml.
    """
    mypy = cfg.get("mypy")
    proto_path = cfg.get("proto_path")
    dist.protoc_version = cfg.get("protoc_version")  # type: ignore
    dist.protobufs = [  # type: ignore
        Protobuf(pb, mypy=mypy, proto_path=proto_path) for pb in cfg.get("protobufs")
    ]


def pyprojecttoml_config(dist: Distribution) -> None:
    """Configure the distribution from pyproject.toml.

    Registers build_protobuf and clean_protobuf commands and loads
    configuration from pyproject.toml if present.

    Args:
        dist: The setuptools Distribution instance.
    """
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
    """A protobuf file to compile."""

    def __init__(self, path, mypy=None, proto_path=None):
        """Initialize a Protobuf instance.

        Args:
            path: Path to the .proto file.
            mypy: Whether to generate mypy stubs. If None, auto-detects.
            proto_path: Base path for resolving imports in .proto files.
        """
        self.path = path
        self.proto_path = proto_path
        if self.proto_path:
            # Use Path for joining but convert to forward slashes for consistency
            self.resolved_path = str(Path(self.proto_path, self.path)).replace(os.sep, "/")
        else:
            self.resolved_path = self.path
        if mypy is None:
            mypy = find_executable("protoc-gen-mypy") is not None
        self.mypy = mypy

    def outputs(self) -> list[str]:
        """Get the list of output files that will be generated.

        Returns:
            list[str]: List of paths to generated Python files.
        """
        return [self.resolved_path[: -len(".proto")] + "_pb2.py"]

    def outputs_path(self) -> str:
        """Get the directory where output files will be generated.

        Returns:
            str: Path to the output directory.
        """
        return self.proto_path or "."


def protobufs(dist, keyword, value):
    """Process the 'protobufs' keyword for setuptools.

    Args:
        dist: The setuptools Distribution instance.
        keyword: The keyword name (should be 'protobufs').
        value: List of Protobuf instances.

    Raises:
        TypeError: If any item in value is not a Protobuf instance.
    """
    for protobuf in value:
        if not isinstance(protobuf, Protobuf):
            raise TypeError(protobuf)

    dist.protobufs = value


def find_executable(executable: str) -> Optional[str]:
    """Find an executable in the PATH.

    Args:
      executable: The name of the executable to find.
    """
    _, ext = os.path.splitext(executable)
    if sys.platform == "win32" and ext != ".exe":
        executable = executable + ".exe"

    if os.path.isfile(executable):
        return executable

    path = os.environ.get("PATH", os.defpath)
    # PATH='' doesn't match, whereas PATH=':' looks in the current directory
    if not path:
        return None

    paths = path.split(os.pathsep)
    for p in paths:
        f = os.path.join(p, executable)
        if os.path.isfile(f):
            return f
    return None


def get_protoc(version) -> Optional[str]:
    """Download and return the path to the protoc binary for the given version.

    If version is None, the system protoc is returned if available.

    Args:
      version: The version of protoc to download.

    Returns:
      path to the protoc binary
    """
    # handle if no version requested (use system/env)
    if version is None:
        return None

    # determine the release string including system and machine info of protoc
    machine = platform.machine().lower()
    if machine in ["amd64", "x64", "x86_64"]:
        machine = "x86_64"
    elif machine in ["aarch64", "arm64", "aarch_64"]:
        machine = "aarch_64"
    elif machine in ["i386", "i686", "x86", "x86_32"]:
        machine = "x86_32"
    elif machine in ["ppc64le", "ppcle64", "ppcle_64"]:
        machine = "ppcle_64"
    elif machine in ["s390", "s390x", "s390_64"]:
        machine = "s390_64"

    system = platform.system()
    if system == "Linux":
        release = f"protoc-{version}-linux-{machine}"
    elif system == "Darwin":
        assert machine in ["x86_64", "aarch_64"]
        release = f"protoc-{version}-osx-{machine}"
    elif system == "Windows":
        assert machine in ["x86_64", "x86_32"]
        if machine == "x86_64":
            release = f"protoc-{version}-win64"
        elif machine == "x86_32":
            release = f"protoc-{version}-win32"

    path = os.path.join(os.path.dirname(__file__), release)
    executable = os.path.join(path, "bin", "protoc")
    if system == "Windows":
        executable = executable + ".exe"

    # if we already have it downloaded, return it
    if os.path.exists(executable):
        return executable

    # otherwise download
    zip_name = f"{release}.zip"
    zip_dest = os.path.join(os.path.dirname(__file__), zip_name)
    base_url = "https://github.com/protocolbuffers/protobuf/releases/download"
    release_url = f"{base_url}/v{version}/{zip_name}"
    urllib.request.urlretrieve(url=release_url, filename=zip_dest)
    zipfile.ZipFile(zip_dest).extractall(path)

    assert os.path.exists(executable)
    if system != "Windows":
        # zip format doesn't always handle unix permissions well
        # mark the executable as executable in case it isn't
        os.chmod(executable, 0o777)
    return executable
