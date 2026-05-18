import logging
from concurrent.futures import ProcessPoolExecutor, as_completed

import pytesseract
from pdf2image import convert_from_path
from PIL import Image

from app.core.config import get_settings
from app.ocr.engine import OcrPageResult, OcrResult
from app.ocr.preprocess import preprocess_page

logger = logging.getLogger(__name__)


def _ocr_single_page(args: tuple[int, Image.Image, str | None]) -> OcrPageResult:
    page_num, image, tesseract_cmd = args
    if tesseract_cmd:
        pytesseract.pytesseract.tesseract_cmd = tesseract_cmd
    processed = preprocess_page(image)
    data = pytesseract.image_to_data(processed, output_type=pytesseract.Output.DICT)
    text_parts: list[str] = []
    confidences: list[float] = []
    for word, conf in zip(data.get("text", []), data.get("conf", [])):
        if not word or not str(word).strip():
            continue
        try:
            conf_value = float(conf)
        except (TypeError, ValueError):
            continue
        if conf_value < 0:
            continue
        text_parts.append(str(word))
        confidences.append(conf_value)
    page_text = " ".join(text_parts)
    avg_conf = sum(confidences) / len(confidences) if confidences else 0.0
    return OcrPageResult(page=page_num, text=page_text, confidence=avg_conf / 100.0)


class TesseractOcrEngine:
    def __init__(self) -> None:
        settings = get_settings()
        self._dpi = settings.ocr_dpi
        self._max_workers = settings.ocr_max_workers
        self._tesseract_cmd = settings.tesseract_cmd

    def extract_from_pdf(self, pdf_path: str) -> OcrResult:
        images = convert_from_path(pdf_path, dpi=self._dpi)
        return self.extract(images)

    def extract(self, images: list[Image.Image]) -> OcrResult:
        if not images:
            return OcrResult(text="", page_count=0, pages=[], average_confidence=0.0)

        page_results: list[OcrPageResult] = []
        worker_count = min(self._max_workers, len(images))
        tasks = [
            (index + 1, image, self._tesseract_cmd) for index, image in enumerate(images)
        ]

        if worker_count <= 1:
            page_results = [_ocr_single_page(task) for task in tasks]
        else:
            with ProcessPoolExecutor(max_workers=worker_count) as pool:
                futures = {pool.submit(_ocr_single_page, task): task[0] for task in tasks}
                for future in as_completed(futures):
                    page_results.append(future.result())

        page_results.sort(key=lambda item: item.page)
        combined_text = "\n".join(page.text for page in page_results if page.text)
        confidences = [page.confidence for page in page_results if page.confidence > 0]
        avg_conf = sum(confidences) / len(confidences) if confidences else 0.0
        return OcrResult(
            text=combined_text,
            page_count=len(images),
            pages=page_results,
            average_confidence=avg_conf,
        )
