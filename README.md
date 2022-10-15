# protobuf support for setuptools

Plugin for `setuptools` that adds support for compiling protobuf files.

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
```
