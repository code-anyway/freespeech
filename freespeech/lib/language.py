import logging
import re
from dataclasses import replace
from typing import Any, Dict, List, MutableMapping, Sequence, Tuple

from azure.ai.language.conversations.aio import ConversationAnalysisClient
from azure.core.credentials import AzureKeyCredential
from google.cloud import translate as translate_api

from freespeech import env
from freespeech.types import Event

logger = logging.getLogger(__name__)


def translate_text(text: str, source: str, target: str) -> str:
    if source == target:
        return text

    if not text:
        return text

    client = translate_api.TranslationServiceClient()
    parent = f"projects/{env.get_project_id()}/locations/global"

    # Detail on supported types can be found here:
    # https://cloud.google.com/translate/docs/supported-formats
    response = client.translate_text(
        request={
            "parent": parent,
            "contents": [text],
            "mime_type": "text/plain",  # or text/html
            "source_language_code": source,
            "target_language_code": target,
        }
    )

    result = "\n".join([t.translated_text for t in response.translations])

    # Some translations turn "#1#" into "# 1 #", so this should undo that.
    return re.sub(r"#\s*(\d+(\.\d+)?)\s*#", r"#\1#", result)


def translate_events(
    events: Sequence[Event], source: str, target: str
) -> Sequence[Event]:
    return [
        replace(
            event,
            chunks=[translate_text(text, source, target) for text in event.chunks],
        )
        for event in events
    ]


def parse_intent(
    prediction: MutableMapping[str, Any],
    intent_confidence: float,
    entity_confidence: float,
) -> Tuple[str, Dict[str, List]]:
    intent, *_ = [
        intent["category"]
        for intent in sorted(
            prediction["intents"], key=lambda p: p["confidenceScore"], reverse=True
        )
        if intent["confidenceScore"] > intent_confidence
    ]

    if _:
        logger.warn(
            f"Multiple intents with confidence > {intent_confidence}: {intent + _}"
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

    return intent, entities


async def intent(
    text: str, intent_confidence: float = 0.95, entity_confidence: float = 0.95
) -> Tuple[str, Dict[str, List]]:
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

    return parse_intent(
        result["result"]["prediction"],
        intent_confidence=intent_confidence,
        entity_confidence=entity_confidence,
    )
