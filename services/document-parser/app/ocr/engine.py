from dataclasses import dataclass
from typing import Protocol

from PIL import Image


@dataclass
class OcrPageResult:
    page: int
    text: str
    confidence: float


@dataclass
class OcrResult:
    text: str
    page_count: int
    pages: list[OcrPageResult]
    average_confidence: float


class OcrEngine(Protocol):
    def extract(self, images: list[Image.Image]) -> OcrResult: ...
