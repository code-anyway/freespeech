import re

from typing import List


def chunk(text: str, max_chars: int) -> List[str]:
    """Split text into chunks.

    Args:
        text: Original text.
        max_chars: Character limit for each chunk.

    Returns:
        Chunks of tests containing one or more sentences, each chunk
        will be less than `max_chars`.
    """
    # If capturing parentheses are used in pattern,
    # then the text of all groups in the pattern
    # are also returned as part of the resulting list.
    sentences = (s for s in re.split(r"(\!|\?|\.)", text))

    def chunk_sentences():
        res = ""
        for s in sentences:
            if len(res) + len(s) > max_chars:
                yield res.strip()
                res = s
            else:
                res += s
        if res:
            yield res.strip()

    return list(chunk_sentences())
