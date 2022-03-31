from typing import List, Dict, Any
from dataclasses import dataclass


@dataclass(frozen=True)
class Content:
    title: str | None
    text: str | None
    children: List['Content']


@dataclass(frozen=True)
class Document:
    title: str | None
    properties: Dict[str, Any]
    content: List[Content]
