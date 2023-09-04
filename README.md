# protobuf support for setuptools

Plugin for `setuptools` that adds support for compiling protobuf files.

## Dependencies

The plugin requires the external ``protoc`` executable that is part of the
[protobuf project](https://github.com/protocolbuffers/protobuf) to be present.
On Debian systems, this executable is shipped in the ``protobuf-compiler`` package.

Optionally, it can also generate typing hints if the ``mypy`` extra is selected.

## Usage

You can configure `setuptools-protobuf` in either `setup.py`, `setup.cfg` or `pyproject.toml`.

## setup.py

```python
from setuptools_protobuf import Protobuf

setup(
...
    setup_requires=['setuptools-protobuf'],
    protobufs=[Protobuf('example/foo.proto')],
)
```

## setup.cfg

```ini
...

[options]
setup_requires =
    setuptools
    setuptools-protobuf
```

## pyproject.toml

```toml
[build-system]
requires = ["setuptools", "setuptools-protobuf"]

[tool.setuptools-protobuf]
protobufs = ["example/foo.proto"]
```
