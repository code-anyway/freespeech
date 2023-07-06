import hashlib
import json
from collections.abc import Iterable
from dataclasses import asdict, is_dataclass
from pathlib import Path


def file(filename: Path) -> str:
    """Get SHA256 hash of a file contents as a hex digest."""
    sha256_hash = hashlib.sha256()

    with open(filename, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)

    return sha256_hash.hexdigest()


def string(s: str) -> str:
    """Get SHA256 hash of a string as a hex digest."""
    sha256_hash = hashlib.sha256(s.encode())
    return sha256_hash.hexdigest()


def obj(obj: object) -> str:
    """Get SHA256 hash of an object as a hex digest."""

    def descend_tuple(o: tuple):
        f, s = o
        return (dataclasses_to_dicts(f), dataclasses_to_dicts(s))

    def dataclasses_to_dicts(o: object):
        if is_dataclass(o) and not isinstance(o, type):
            return dataclasses_to_dicts(asdict(o))
        if type(o) is dict and not isinstance(o, type):
            return dict(map(descend_tuple, o.items()))
        if isinstance(o, Iterable) and not isinstance(o, str):
            return list(map(dataclasses_to_dicts, o))
        return o

    sha256_hash = hashlib.sha256(json.dumps(dataclasses_to_dicts(obj)).encode())
    return sha256_hash.hexdigest()
