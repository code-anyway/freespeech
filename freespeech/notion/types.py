from dataclasses import dataclass
from typing import Any, Dict, List


@dataclass(frozen=True)
class Content:
    title: str | None
    text: str | None
    children: List["Content"]


@dataclass(frozen=True)
class Document:
    title: str | None
    properties: Dict[str, Any]
    content: List[Content]
