import cv2
import numpy as np
from PIL import Image


def pil_to_cv(image: Image.Image) -> np.ndarray:
    rgb = np.array(image.convert("RGB"))
    return cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)


def cv_to_pil(matrix: np.ndarray) -> Image.Image:
    rgb = cv2.cvtColor(matrix, cv2.COLOR_BGR2RGB)
    return Image.fromarray(rgb)


def deskew(image: Image.Image) -> Image.Image:
    matrix = pil_to_cv(image)
    gray = cv2.cvtColor(matrix, cv2.COLOR_BGR2GRAY)
    gray = cv2.bitwise_not(gray)
    coords = np.column_stack(np.where(gray > 0))
    if coords.size == 0:
        return image
    angle = cv2.minAreaRect(coords)[-1]
    if angle < -45:
        angle = 90 + angle
    angle = -angle
    if abs(angle) < 0.5:
        return image
    height, width = matrix.shape[:2]
    center = (width // 2, height // 2)
    rotation = cv2.getRotationMatrix2D(center, angle, 1.0)
    rotated = cv2.warpAffine(
        matrix,
        rotation,
        (width, height),
        flags=cv2.INTER_CUBIC,
        borderMode=cv2.BORDER_REPLICATE,
    )
    return cv_to_pil(rotated)


def denoise(image: Image.Image) -> Image.Image:
    matrix = pil_to_cv(image)
    cleaned = cv2.fastNlMeansDenoisingColored(matrix, None, 10, 10, 7, 21)
    return cv_to_pil(cleaned)


def preprocess_page(image: Image.Image) -> Image.Image:
    return denoise(deskew(image))
