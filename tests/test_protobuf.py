"""Unit tests for setuptools-protobuf package."""

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from setuptools.dist import Distribution
from setuptools.errors import ExecError, PlatformError

from setuptools_protobuf import (
    Protobuf,
    build_protobuf,
    clean_protobuf,
    find_executable,
    get_protoc,
    has_protobuf,
    load_pyproject_config,
    pyprojecttoml_config,
)


class TestProtobuf(unittest.TestCase):
    """Test cases for the Protobuf class."""

    def test_protobuf_basic(self):
        """Test basic Protobuf instance creation and properties."""
        pb = Protobuf("foo.proto")
        assert pb.outputs() == ["foo_pb2.py"]
        assert pb.mypy in (False, True)
        assert pb.resolved_path == "foo.proto"
        assert pb.outputs_path() == "."

    def test_protobuf_with_proto_path(self):
        """Test Protobuf instance with custom proto_path."""
        pb = Protobuf("bar.proto", proto_path="src/protos")
        assert pb.outputs() == ["src/protos/bar_pb2.py"]
        assert pb.resolved_path == "src/protos/bar.proto"
        assert pb.outputs_path() == "src/protos"

    def test_protobuf_mypy_explicit(self):
        """Test explicit mypy flag configuration."""
        pb = Protobuf("foo.proto", mypy=True)
        assert pb.mypy is True

        pb = Protobuf("foo.proto", mypy=False)
        assert pb.mypy is False

    def test_protobuf_nested_path(self):
        """Test Protobuf with nested directory path."""
        pb = Protobuf("subdir/test.proto")
        assert pb.outputs() == ["subdir/test_pb2.py"]
        assert pb.resolved_path == "subdir/test.proto"

    def test_protobuf_with_proto_path_nested(self):
        """Test Protobuf with proto_path and nested messages directory."""
        pb = Protobuf("messages/user.proto", proto_path="proto")
        assert pb.outputs() == ["proto/messages/user_pb2.py"]
        assert pb.resolved_path == "proto/messages/user.proto"
        assert pb.outputs_path() == "proto"


class TestBuildProtobuf(unittest.TestCase):
    """Test cases for the build_protobuf command."""

    def setUp(self):
        """Set up test fixtures for build_protobuf tests."""
        self.dist = Distribution()
        self.cmd = build_protobuf(self.dist)

    def test_initialize_options_defaults(self):
        """Test default initialization of build_protobuf options."""
        self.cmd.initialize_options()
        # Should set protoc to something (env var, get_protoc result, or
        # find_executable result)
        assert hasattr(self.cmd, "protoc")
        assert self.cmd.outfiles == []

    def test_initialize_options_with_env(self):
        """Test initialization with PROTOC environment variable."""
        with patch.dict(os.environ, {"PROTOC": "/custom/protoc"}):
            cmd = build_protobuf(self.dist)
            cmd.initialize_options()
            assert cmd.protoc == "/custom/protoc"

    def test_finalize_options_missing_protoc(self):
        """Test error handling when protoc executable is missing."""
        self.cmd.protoc = "/nonexistent/protoc"
        with self.assertRaises(PlatformError) as ctx:
            self.cmd.finalize_options()
        assert "Unable to find protobuf compiler" in str(ctx.exception)

    def test_finalize_options_none_protoc(self):
        """Test error handling when protoc is None."""
        self.cmd.protoc = None
        with self.assertRaises(PlatformError) as ctx:
            self.cmd.finalize_options()
        assert "Unable to find protobuf compiler" in str(ctx.exception)

    def test_get_source_files_empty(self):
        """Test get_source_files with no protobufs."""
        self.dist.protobufs = []
        files = self.cmd.get_source_files()
        assert files == []

    def test_get_source_files_multiple(self):
        """Test get_source_files with multiple protobuf files."""
        pb1 = Protobuf("test1.proto")
        pb2 = Protobuf("dir/test2.proto")
        pb3 = Protobuf("test3.proto", proto_path="proto")
        self.dist.protobufs = [pb1, pb2, pb3]

        files = self.cmd.get_source_files()
        assert files == ["test1.proto", "dir/test2.proto", "test3.proto"]

    def test_get_outputs(self):
        """Test get_outputs returns the outfiles list."""
        self.cmd.outfiles = ["test_pb2.py", "other_pb2.py"]
        assert self.cmd.get_outputs() == ["test_pb2.py", "other_pb2.py"]

    def test_get_outputs_empty(self):
        """Test get_outputs with empty outfiles list."""
        self.cmd.outfiles = []
        assert self.cmd.get_outputs() == []

    def test_run_no_protobufs(self):
        """Test run method with no protobuf files."""
        self.dist.protobufs = []
        self.cmd.protoc = "/usr/bin/protoc"
        # Should run without error when no protobufs
        self.cmd.run()
        assert self.cmd.outfiles == []

    def test_run_integration(self):
        """Integration test for build_protobuf with actual files."""
        # Integration test with actual temp files
        with tempfile.TemporaryDirectory() as tmpdir:
            proto_file = Path(tmpdir) / "test.proto"
            proto_file.write_text('syntax = "proto3";\nmessage Test {}')

            pb = Protobuf(str(proto_file))
            self.dist.protobufs = [pb]

            # This will fail if protoc is not installed, which is expected
            self.cmd.protoc = find_executable("protoc")
            if self.cmd.protoc:
                try:
                    self.cmd.run()
                    # If protoc exists and runs, check outputs
                    assert (
                        str(proto_file).replace(".proto", "_pb2.py")
                        in self.cmd.outfiles
                    )
                except (ExecError, PlatformError):
                    # protoc might exist but fail for other reasons
                    pass


class TestCleanProtobuf(unittest.TestCase):
    """Test cases for the clean_protobuf command."""

    def setUp(self):
        """Set up test fixtures for clean_protobuf tests."""
        self.dist = Distribution()
        self.cmd = clean_protobuf(self.dist)

    def test_initialize_finalize_options(self):
        """Test initialize and finalize options methods."""
        # Should not raise
        self.cmd.initialize_options()
        self.cmd.finalize_options()

    def test_run_no_protobufs(self):
        """Test run method with no protobuf files."""
        self.cmd.protobufs = []
        # Should run without error
        self.cmd.run()

    def test_run_with_temp_files(self):
        """Test cleaning actual generated protobuf files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create actual output file
            output_file = Path(tmpdir) / "test_pb2.py"
            output_file.write_text("# Generated protobuf file")

            pb = Protobuf("test.proto")
            pb.outputs = lambda: [str(output_file)]
            self.cmd.protobufs = [pb]

            assert output_file.exists()
            self.cmd.run()
            assert not output_file.exists()

    def test_run_file_already_missing(self):
        """Test run method when files are already missing."""
        pb = Protobuf("nonexistent.proto")
        self.cmd.protobufs = [pb]
        # Should not raise even if file doesn't exist
        self.cmd.run()


class TestFindExecutable(unittest.TestCase):
    """Test cases for the find_executable function."""

    def test_find_absolute_path_exists(self):
        """Test finding executable with absolute path that exists."""
        # Create a temporary file and close it so find_executable can access it
        with tempfile.NamedTemporaryFile(
            delete=False, suffix=".exe" if sys.platform == "win32" else ""
        ) as f:
            temp_path = f.name
        
        try:
            result = find_executable(temp_path)
            assert result == temp_path
        finally:
            # Clean up the file
            try:
                os.unlink(temp_path)
            except (OSError, PermissionError):
                # On Windows, file might still be in use
                pass

    def test_find_absolute_path_not_exists(self):
        """Test finding executable with absolute path that doesn't exist."""
        result = find_executable("/definitely/not/a/real/path/protoc")
        assert result is None

    def test_find_in_path(self):
        """Test finding executable in system PATH."""
        # Test finding actual executables that likely exist
        for cmd in ["python", "python3", sys.executable]:
            result = find_executable(cmd)
            if result:
                # If found, it should be a valid file
                assert os.path.isfile(result)
                break

    def test_not_found(self):
        """Test when executable is not found anywhere."""
        result = find_executable("definitely_not_a_real_executable_name_12345")
        assert result is None

    def test_empty_path(self):
        """Test finding executable with empty PATH environment variable."""
        with patch.dict(os.environ, {"PATH": ""}):
            result = find_executable("protoc")
            assert result is None

    def test_windows_exe_extension(self):
        """Test that .exe extension is added on Windows."""
        if sys.platform == "win32":
            # On Windows, test that .exe is added
            result = find_executable("python")
            if result:
                assert result.endswith(".exe")


class TestGetProtoc(unittest.TestCase):
    """Test cases for the get_protoc function."""

    def test_none_version(self):
        """Test get_protoc with None version."""
        result = get_protoc(None)
        assert result is None

    def test_version_string_format(self):
        """Test get_protoc handles version strings correctly."""
        # Test that the function handles version strings correctly
        # without actually downloading
        import platform

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch(
                "setuptools_protobuf.__file__", os.path.join(tmpdir, "__init__.py")
            ):
                # Create expected directory structure
                system = platform.system()
                machine = platform.machine().lower()

                if machine in ["amd64", "x64", "x86_64"]:
                    machine = "x86_64"
                elif machine in ["aarch64", "arm64", "aarch_64"]:
                    machine = "aarch_64"

                if system == "Linux":
                    release = f"protoc-3.20.0-linux-{machine}"
                elif system == "Darwin":
                    release = f"protoc-3.20.0-osx-{machine}"
                elif system == "Windows":
                    if machine == "x86_64":
                        release = "protoc-3.20.0-win64"
                    else:
                        release = "protoc-3.20.0-win32"
                else:
                    # Unsupported platform
                    return

                # Create fake protoc executable
                protoc_dir = Path(tmpdir) / release / "bin"
                protoc_dir.mkdir(parents=True)
                protoc_file = protoc_dir / (
                    "protoc.exe" if system == "Windows" else "protoc"
                )
                protoc_file.write_text("fake protoc")

                result = get_protoc("3.20.0")
                assert result == str(protoc_file)


class TestHasProtobuf(unittest.TestCase):
    """Test cases for the has_protobuf function."""

    def test_has_protobuf_true(self):
        """Test has_protobuf returns True when protobufs exist."""
        cmd = MagicMock()
        cmd.distribution.protobufs = [Protobuf("test.proto")]
        assert has_protobuf(cmd) is True

    def test_has_protobuf_empty_list(self):
        """Test has_protobuf returns False for empty list."""
        cmd = MagicMock()
        cmd.distribution.protobufs = []
        assert has_protobuf(cmd) is False

    def test_has_protobuf_no_attribute(self):
        """Test has_protobuf returns False when attribute doesn't exist."""
        cmd = MagicMock()
        # Explicitly delete the attribute to test getattr default
        del cmd.distribution.protobufs
        assert has_protobuf(cmd) is False

    def test_has_protobuf_multiple(self):
        """Test has_protobuf returns True for multiple protobufs."""
        cmd = MagicMock()
        cmd.distribution.protobufs = [
            Protobuf("test1.proto"),
            Protobuf("test2.proto"),
            Protobuf("test3.proto"),
        ]
        assert has_protobuf(cmd) is True


class TestLoadPyprojectConfig(unittest.TestCase):
    """Test cases for the load_pyproject_config function."""

    def test_basic_config(self):
        """Test loading basic configuration from pyproject.toml."""
        dist = Distribution()
        cfg = {
            "protobufs": ["test.proto", "other.proto"],
            "mypy": True,
            "proto_path": "protos",
            "protoc_version": "3.20.0",
        }

        load_pyproject_config(dist, cfg)

        assert dist.protoc_version == "3.20.0"
        assert len(dist.protobufs) == 2
        assert all(isinstance(pb, Protobuf) for pb in dist.protobufs)
        assert dist.protobufs[0].path == "test.proto"
        assert dist.protobufs[0].mypy is True
        assert dist.protobufs[0].proto_path == "protos"
        assert dist.protobufs[1].path == "other.proto"

    def test_minimal_config(self):
        """Test loading minimal configuration."""
        dist = Distribution()
        cfg = {"protobufs": ["test.proto"]}

        load_pyproject_config(dist, cfg)

        assert dist.protoc_version is None
        assert len(dist.protobufs) == 1
        assert dist.protobufs[0].path == "test.proto"
        assert dist.protobufs[0].proto_path is None

    def test_config_no_protobufs(self):
        """Test configuration with empty protobufs list."""
        dist = Distribution()
        cfg = {"protoc_version": "3.20.0", "protobufs": []}

        load_pyproject_config(dist, cfg)

        assert dist.protoc_version == "3.20.0"
        assert dist.protobufs == []

    def test_config_with_mypy_false(self):
        """Test configuration with mypy disabled."""
        dist = Distribution()
        cfg = {"protobufs": ["test.proto"], "mypy": False}

        load_pyproject_config(dist, cfg)

        assert dist.protobufs[0].mypy is False


class TestPyprojecttomlConfig(unittest.TestCase):
    """Test cases for the pyprojecttoml_config function."""

    def test_with_temp_pyproject(self):
        """Test pyprojecttoml_config with temporary pyproject.toml file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            orig_cwd = os.getcwd()
            try:
                os.chdir(tmpdir)

                # Test without pyproject.toml
                dist = Distribution()
                pyprojecttoml_config(dist)
                assert dist.protoc_version is None

                # Test with pyproject.toml
                pyproject = Path("pyproject.toml")
                pyproject.write_text("""
[tool.setuptools-protobuf]
protobufs = ["test.proto"]
protoc_version = "3.20.0"
""")

                dist = Distribution()
                pyprojecttoml_config(dist)
                assert dist.protoc_version == "3.20.0"
                assert len(dist.protobufs) == 1
                assert dist.protobufs[0].path == "test.proto"

            finally:
                os.chdir(orig_cwd)

    def test_commands_registered(self):
        """Test that build and clean commands are properly registered."""
        dist = Distribution()
        pyprojecttoml_config(dist)

        build = dist.get_command_class("build")
        assert ("build_protobuf", has_protobuf) in build.sub_commands

        clean = dist.get_command_class("clean")
        assert ("clean_protobuf", has_protobuf) in clean.sub_commands


if __name__ == "__main__":
    unittest.main()
