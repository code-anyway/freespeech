import functools
import re
from itertools import zip_longest
from typing import Iterator, Sequence

import spacy

from freespeech.types import Language, assert_never


@functools.cache
def _nlp(lang: Language):
    match lang:
        case "en-US":
            nlp = spacy.load("en_core_web_sm")
        case "de-DE":
            nlp = spacy.load("de_core_news_sm")
        case "fr-FR":
            nlp = spacy.load("fr_core_news_sm")
        case "pt-PT" | "pt-BR":
            nlp = spacy.load("pt_core_news_sm")
        case "es-US" | "es-MX" | "es-ES":
            nlp = spacy.load("es_core_news_sm")
        case "uk-UA":
            nlp = spacy.load("uk_core_news_sm")
        case "ru-RU":
            nlp = spacy.load("ru_core_news_sm")
        case "sv-SE":
            nlp = spacy.load("sv_core_news_sm")
        case never:
            # (astaff, 20221109): when adding a new language make sure
            # to install the spacy model for it in setup.py.
            assert_never(never)

    return nlp


def is_sentence(s: str) -> bool:
    # TODO astaff: consider using text processing libraries like spacy
    # as we keep introducing stuff like this.
    s = s.strip()
    return s.endswith(".") or s.endswith("!") or s.endswith("?")


def capitalize_sentence(s: str):
    """Capitalizes only the first letter of the string."""
    if s.isspace():
        return s

    if not s:
        return s

    _s = s.lstrip()

    return s[0 : len(s) - len(_s)] + _s[0].upper() + _s[1:]


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


def split_sentences_nlp(s: str, lang: Language) -> Sequence[str]:
    """Split string into sentences using nlp.
    Args:
        s: string to split
    Returns:
        Sequence of strings representing sentences.
    """
    nlp = _nlp(lang)
    doc = nlp(s)
    senter = nlp.get_pipe("senter")
    sentences = [span.text for span in senter(doc).sents]
    return sentences


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


def sentences(s: str, lang: Language) -> Sequence[str]:
    """Break string sentences.
    Args:
        paragraph: input paragraph.
    Returns:
        Sequence of strings representing sentences.
    """
    if lang == "tr-TR":
        return split_sentences(s)

    nlp = _nlp(lang)
    doc = nlp(s)
    senter = nlp.get_pipe("senter")
    sentences = [span.text for span in senter(doc).sents]
    return [
        sentence
        for sentence in sentences
        # We want to remove artifacts of the sentence splitter.
        # For example in fr-FR "Et zéro." produces ["Et zéro", "."]
        if sentence not in ("", " ", "!", ".", "?")
    ]


def lemmas(s: str, lang: Language) -> Sequence[str]:
    """Break string into lemmas.
    Args:
        paragraph: input paragraph.
    Returns:
        Sequence of strings representing lemmas.
    """
    if lang == "tr-TR":
        return [lemma for lemma in s.split() if lemma]

    nlp = _nlp(lang)
    lemmatizer = nlp.get_pipe("lemmatizer")
    return [token.lemma_ for token in lemmatizer(nlp(s))]
