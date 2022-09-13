import difflib
import re
from itertools import zip_longest
from typing import Iterator, List, Sequence, Tuple

import spacy

from freespeech.types import Language


def is_sentence(s: str) -> bool:
    # TODO astaff: consider using text processing libraries like spacy
    # as we keep introducing stuff like this.
    s = s.strip()
    return s.endswith(".") or s.endswith("!") or s.endswith("?")


def make_sentence(s: str):
    if is_sentence(s):
        return s

    return f"{s}."


def split_sentences(s: str) -> Sequence[str]:
    """Split into sentences broken down by the punctuation followed by space.

    Args:
        s: string to split
    Returns:
        Sequence of strings representing sentences.
    """
    # If capturing parentheses are used in pattern,
    # then the text of all groups in the pattern
    # are also returned as part of the resulting list.
    split = re.split(r"(\!|\?|\.\s+)", s)
    return [
        a + b for a, b in zip_longest(split[0::2], split[1::2], fillvalue="") if a + b
    ]


def chunk(text: str, max_chars: int, sentence_overhead: int = 0) -> Sequence[str]:
    """Split text into chunks.

    Args:
        text: Original text.
        max_chars: Character limit for each chunk.
        sentence_overhead: Extra limit used by each sentence.

    Returns:
        Chunks of text containing one or more sentences, each chunk
        will be less than `max_chars`. Also overall text overhead and sentence
        overhead are accounted for `max_chars`. Text is broken down on sentence border.
    """
    if not text:
        return [text]

    def chunk_sentences() -> Iterator[str]:
        res = ""
        chunk_limit = max_chars

        for s in split_sentences(text):
            if len(res) + len(s) > chunk_limit:
                if res:
                    chunk_limit = max_chars
                    yield res.strip()
                chunk_limit -= sentence_overhead
                res = s
            else:
                chunk_limit -= sentence_overhead
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


def break_sentences(
    text: str, words: List[Tuple[str, int, int]], lang: Language
) -> Sequence[Tuple[str, int, int]]:
    match lang:
        case "en-US":
            nlp = spacy.load("en_core_web_sm")
        case _:
            raise NotImplementedError(f"Language {lang} is not supported.")

    doc = nlp(text)

    senter = nlp.get_pipe("senter")
    doc = senter(doc)
    sentences = [span.text for span in doc.sents]

    lemmatizer = nlp.get_pipe("lemmatizer")
    sentence_tokens = [
        (token.lemma_.lower(), num)
        for num, sentence in enumerate(sentences)
        for token in lemmatizer(nlp(sentence))
    ]

    matcher = difflib.SequenceMatcher(
        a=[token for token, _ in sentence_tokens],
        b=[word.lower() for word, *_ in words],
        autojunk=False,
    )

    matches = matcher.get_matching_blocks()

    matched_tokens: list[tuple[str, int]] = sum(
        [sentence_tokens[i : i + n] for i, _, n in matches], []
    )
    matched_words: list[tuple[str, int, int]] = sum(
        [words[j : j + n] for _, j, n in matches], []
    )
