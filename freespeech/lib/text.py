import re
from itertools import zip_longest
from typing import Iterator, Sequence


def is_sentence(s: str) -> bool:
    # TODO astaff: consider using text processing libraries like spacy
    # as we keep introducing stuff like this.
    s = s.strip()
    return s.endswith(".") or s.endswith("!") or s.endswith("?")


def make_sentence(s: str):
    if is_sentence(s):
        return s

    return f"{s}."


def chunk(text: str, max_chars: int) -> Sequence[str]:
    """Split text into chunks.

    Args:
        text: Original text.
        max_chars: Character limit for each chunk.

    Returns:
        Chunks of text containing one or more sentences, each chunk
        will be less than `max_chars`. Text is broken down on sentence border.
    """
    if not text:
        return [text]

    # If capturing parentheses are used in pattern,
    # then the text of all groups in the pattern
    # are also returned as part of the resulting list.
    split = re.split(r"(\!|\?|\.\s+)", text)
    sentences = [
        a + b for a, b in zip_longest(split[0::2], split[1::2], fillvalue="") if a + b
    ]

    def chunk_sentences() -> Iterator[str]:
        res = ""
        for s in sentences:
            if len(res) + len(s) > max_chars:
                if res:
                    yield res.strip()
                res = s
            else:
                res += s
        if res:
            yield res.strip()

    # return the dot back to time marker
    return list(chunk_sentences())


def chunk_raw(s: str, length: int) -> Sequence[str]:
    assert length > 0
    remainder = len(s) % length
    args = [iter(s)] * length
    res = ["".join(chunk) for chunk in zip(*args)]

    if remainder:
        return res + [s[-remainder:]]
    else:
        return res


def remove_symbols(s: str, symbols: str) -> str:
    t = str.maketrans(s, s, symbols)
    return str.translate(s, t)
