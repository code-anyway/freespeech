import hashlib
from freespeech.types import path


def file(filename: path) -> str:
    """Get SHA256 hash of a file contents as a hex digest."""
    sha256_hash = hashlib.sha256()

    with open(filename, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)

    return sha256_hash.hexdigest()


def string(s: str) -> str:
    """Get SHA256 hash of a string as a hext digest."""
    sha256_hash = hashlib.sha256(s.encode())
    return sha256_hash.hexdigest()
