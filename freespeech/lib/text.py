import re
from typing import Iterator, Sequence


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

    # replace dot within break marker like #1.5# so it does not make a sentence border.
    text = re.sub(r"(#(\d*)(\.)(\d*)#)", r"#\2*\4#", text)

    # If capturing parentheses are used in pattern,
    # then the text of all groups in the pattern
    # are also returned as part of the resulting list.
    sentences = (s for s in re.split(r"(\!|\?|\.)", text))

    def chunk_sentences() -> Iterator[str]:
        res = ""
        for s in sentences:
            if len(res) + len(s) > max_chars:
                yield res.strip()
                res = s
            else:
                res += s
        if res:
            yield res.strip()

    # return the dot back to time marker
    return [re.sub(r"(#(\d*)(\*)(\d*)#)", r"#\2.\4#", s) for s in chunk_sentences()]


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
