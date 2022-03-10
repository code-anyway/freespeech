#!/usr/bin/env python3

import sys
import re


from typing import List

def chunk(text: str, max_chars: int) -> List[str]:
    # If capturing parentheses are used in pattern,
    # then the text of all groups in the pattern
    # are also returned as part of the resulting list.
    sentences = re.split(r"(\!|\?|\.)", text)
    def chunk_sentences():
        res = ""
        for s in sentences:
            if len(res) + len(s) > max_chars:
                yield res
                res = s
            else:
                res += s
        if res:
            yield res

    return list(chunk_sentences())