from setuptools_protobuf import Protobuf


def test_protobuf():
    pb = Protobuf('foo.proto')
    assert pb.outputs() == ['foo_pb2.py']
    assert pb.mypy in (False, True)
