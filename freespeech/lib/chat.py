import logging
import random
import warnings
from dataclasses import asdict, dataclass
from typing import (
    Any,
    Dict,
    Generator,
    List,
    Literal,
    MutableMapping,
    Sequence,
    Tuple,
    TypeGuard,
)

import hypothesis
from azure.ai.language.conversations.aio import ConversationAnalysisClient
from azure.core.credentials import AzureKeyCredential
from hypothesis.strategies import from_regex

from freespeech import env

logger = logging.getLogger(__name__)


LANGUAGES = ["Russian", "English", "Spanish", "Ukrainian", "German", "Portuguese"]
METHODS = ["Machine A", "Machine B", "Machine C", "R2D2", "C3PO", "BB8", "Subtitles"]


Entity = Literal["language", "url", "method"]


def is_entity(val: str) -> TypeGuard[Entity]:
    return val in ("language", "url", "method")


Intent = Literal["transcribe", "dub", "translate"]


def is_intent(val: str) -> TypeGuard[Intent]:
    return val in ("transcribe", "dub", "translate")


@dataclass(frozen=True)
class EntityRecord:
    category: Entity
    offset: int
    length: int


@dataclass(frozen=True)
class UtteranceRecord:
    intent: Intent
    language: str
    text: str
    entities: Sequence[EntityRecord]


def random_case(s: str) -> str:
    return "".join(c.upper() if random.random() > 0.5 else c.lower() for c in s)


ENTITIES = {
    "language": lambda: random_case(random.choice(LANGUAGES)),
    "method": lambda: random_case(random.choice(METHODS)),
    "url": lambda: from_regex(
        r"^((https://www\.youtube\.com/watch\?v=)|(https://youtu\.be/))[A-Za-z0-9_]+$"
    )
    .example()
    .strip(),
}

PHRASES = {
    "transcribe": [
        "{url} with {language} {method}",
        "{url} with {language} transcript using {method}",
        "load {url} with {language} {method}",
        "load {url} with {language} transcript using {method}",
        "create transcript from {url} using {language} {method}",
        "create transcript from {url} and use {language} {method}",
        "Create {language} transcript for {url} using {method}",
        "Create {language} transcript for {url} from {method}",
        "transcribe {url} from {language} using {method}",
    ],
    "dub": [
        "dub {url}",
        "dub using transcript {url}",
        "dub using {url}",
    ],
    "translate": ["translate {url} to {language}"],
}


def parse_intent(
    prediction: MutableMapping[str, Any],
    intent_confidence: float,
    entity_confidence: float,
) -> Tuple[str, Dict[str, List]]:
    intent, *other_intents = [
        intent["category"]
        for intent in sorted(
            prediction["intents"], key=lambda p: p["confidenceScore"], reverse=True
        )
        if intent["confidenceScore"] > intent_confidence
    ]

    if other_intents:
        all_intents = intent + other_intents
        logger.warn(
            f"Multiple intents with confidence > {intent_confidence}: {all_intents}"
        )

    entities: Dict[str, List] = dict()
    for entity in sorted(
        prediction["entities"], key=lambda e: e["confidenceScore"], reverse=True
    ):
        if entity["confidenceScore"] > entity_confidence:
            category = entity["category"]
            key = [
                info["key"]
                for info in entity.get("extraInformation", [])
                if info["extraInformationKind"] == "ListKey"
            ]
            entities[category] = entities.get(category, []) + (key or [entity["text"]])

    def _fix_method(method: str) -> str:
        match method.lower().strip():
            case "subtitles":
                return "Subtitles"
            case "machine a":
                return "Machine A"
            case "machine b":
                return "Machine B"
            case "machine c":
                return "Machine C"
            case _:
                return method

    # TODO (astaff): refactor this to user types/validation when cleaning up the API
    if "method" in entities:
        entities["method"] = [_fix_method(method) for method in entities["method"]]

    return intent, entities


async def _intent_api_call(text: str) -> MutableMapping[str, Any]:
    # Inspired by:
    # https://github.com/Azure/azure-sdk-for-python/blob/main/sdk/cognitivelanguage/azure-ai-language-conversations/samples/sample_analyze_conversation_app.py  # noqa: E501
    token = env.get_azure_conversations_token()

    # TODO (astaff): extract into config
    url = "https://freespeech-chatbot.cognitiveservices.azure.com"
    project_name = "chat-bot"
    deployment_name = "prod"

    # todo (astaff 07/06/2022) remove type ignore after fixing
    # https://github.com/astaff/freespeech/issues/76
    client = ConversationAnalysisClient(url, AzureKeyCredential(token))  # type: ignore
    async with client:
        result = await client.analyze_conversation(
            task={
                "kind": "Conversation",
                "analysisInput": {
                    "conversationItem": {
                        "participantId": "1",
                        "id": "1",
                        "modality": "text",
                        "language": "en",
                        "text": text,
                    },
                    # TODO: verify it's OK to keep it True for PII and privacy reasons
                    "isLoggingEnabled": True,
                },
                "parameters": {
                    "projectName": project_name,
                    "deploymentName": deployment_name,
                    "verbose": True,
                },
            }
        )

    return result["result"]["prediction"]


async def intent(
    text: str, intent_confidence: float = 0.95, entity_confidence: float = 0.95
) -> Tuple[str, Dict[str, List]]:
    # Take normal case text and extract all URLs in their
    # original case
    prediction = await _intent_api_call(text)
    _, entities = parse_intent(
        prediction,
        intent_confidence=intent_confidence,
        entity_confidence=entity_confidence,
    )
    urls = entities.get("url", None)

    # Make it lower case, detect command and get all
    # entities in lower case
    prediction = await _intent_api_call(text.lower())
    command, entities = parse_intent(
        prediction,
        intent_confidence=intent_confidence,
        entity_confidence=entity_confidence,
    )
    # If there is a URL, replace it with original case URLs
    # that start with "http"
    if urls:
        entities["url"] = [url for url in urls if url.startswith("http")]

    return command, entities


def example(
    template: str, entities: Dict[str, str]
) -> Tuple[str, Sequence[EntityRecord]]:
    utterance = template.format(**entities)

    return utterance, [
        EntityRecord(
            category=category, offset=utterance.index(value), length=len(value)
        )
        for category, value in entities.items()
        if value in utterance
        if is_entity(category)
    ]


def generate_examples(intent: str, n: int) -> Generator[UtteranceRecord, None, None]:
    with warnings.catch_warnings():
        warnings.simplefilter(
            "ignore", category=hypothesis.errors.NonInteractiveExampleWarning
        )
        for _ in range(n):
            text, entities = example(
                random.choice(PHRASES[intent]),
                {name: func() for name, func in ENTITIES.items()},
            )
            assert is_intent(intent)

            yield UtteranceRecord(
                intent=intent, language="en-us", text=text, entities=entities
            )


def generate_training_data(
    intents: Sequence[Intent], sample_sizes: List[int]
) -> Sequence[Dict]:
    """Given list of intents and corresponding training set sample size for each intent
    generate training data that classifies intents and highlighs entities.
    """
    utterances: List[UtteranceRecord] = sum(
        [
            list(generate_examples(intent, n))
            for intent, n in zip(intents, sample_sizes)
        ],
        [],
    )

    unique_utterances = list(
        {utterance.text: asdict(utterance) for utterance in utterances}.values()
    )

    return unique_utterances
