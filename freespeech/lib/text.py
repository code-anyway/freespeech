import difflib
import functools
import re
from itertools import groupby, zip_longest
from typing import Iterator, Sequence, Tuple

import spacy

from freespeech.types import Event, Language, assert_never


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


@functools.cache
def _nlp(lang: Language):
    match lang:
        case "en-US":
            nlp = spacy.load("en_core_web_sm")
        case "de-DE":
            nlp = spacy.load("de_core_news_sm")
        case "pt-PT" | "pt-BR":
            nlp = spacy.load("pt_core_news_sm")
        case "es-US":
            nlp = spacy.load("es_core_news_sm")
        case "uk-UA":
            nlp = spacy.load("uk_core_news_sm")
        case "ru-RU":
            nlp = spacy.load("ru_core_news_sm")
        case never:
            assert_never(never)

    return nlp


def words(text: str, lang: Language) -> Sequence[str]:
    """Returns words from text.

    Args:
        text: Paragraph of text with one or more sentences.

    Returns:
        Sequence of words as strings.
    """
    nlp = _nlp(lang=lang)

    _words = [
        "".join(
            token.text for token in nlp(word) if token.pos_ not in {"PUNCT", "SYM", "X"}
        )
        for word in text.split(" ")
    ]

    return [w for w in _words if w]


def _break_phrase(
    text: str,
    words: Sequence[Tuple[str, int, int]],
    nlp: spacy.language.Language,
) -> Sequence[Tuple[str, int | None, int | None]]:
    """Breaks down a single phrase into separate sentences with start time and duration.

    Args:
        text: Paragraph of text with one or more sentences.
        words: Sequence of tuples representing a single word from the phrase,
            it's start time and duration.
        nlp: Instance of Spacy language model.

    Returns:
        Sequence of tuples representing a sentence, it's start time and duration.
    """
    doc = nlp(text)
    senter = nlp.get_pipe("senter")
    sentences = [span.text for span in senter(doc).sents]

    # reduce each word in text and words down to lemmas to avoid
    # mismatches due to effects of ASR's language model.
    lemmatizer = nlp.get_pipe("lemmatizer")
    display_tokens = [
        (token.lemma_.lower(), num)
        for num, sentence in enumerate(sentences)
        for token in lemmatizer(nlp(sentence))
    ]
    lexical_tokens = [
        (token.lemma_.lower(), start, duration)
        for word, start, duration in words
        for token in lemmatizer(nlp(word))
    ]

    # Find the longest common sequences between lemmas in text
    # and lemmatized words.
    matcher = difflib.SequenceMatcher(
        a=[token for token, *_ in display_tokens],
        b=[token for token, *_ in lexical_tokens],
        autojunk=False,
    )
    matches = [
        (num, (start, duration))
        for i, j, n in matcher.get_matching_blocks()
        for (_, num), (_, start, duration) in zip(
            display_tokens[i : i + n], lexical_tokens[j : j + n]
        )
    ]

    # Group matches by sentence number. The first and the last item
    # in the group will represent the first and last overlaps with the timed words.
    sentence_timings = {
        num: (start := timings[0][0], timings[-1][0] + timings[-1][1] - start)
        for num, timings in [
            (num, [(start, duration) for _, (start, duration) in timings])
            for num, timings in groupby(matches, key=lambda a: a[0])
        ]
    }

    # Return sentences and their timings. If there were no overlaps for a
    # sentence, we will set start and duration to None.
    return [
        (sentence, *sentence_timings[num])
        if num in sentence_timings
        else (sentence, None, None)
        for num, sentence in enumerate(sentences)
    ]


def break_speech(
    phrases: Sequence[Tuple[str, Sequence[Tuple[str, int, int]]]], lang: Language
) -> Sequence[Event]:
    """Breaks down multiple phrases into separate sentences
    with start time and duration.

    Args:
        phrases: A sequence of paragraphs of text, containing one or more sentences
            and the lexical output of ASR model with word-level timings.
        lang: Language code.

    Returns:
        Sequence of tuples representing a sentence, it's start time and duration.
    """
    nlp = _nlp(lang)
    return [
        Event(time_ms=start, duration_ms=duration, chunks=[text])
        for text, start, duration in sum(
            (list(_break_phrase(text, words, nlp)) for text, words in phrases), []
        )
    ]
