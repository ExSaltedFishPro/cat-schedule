from __future__ import annotations

import io
import logging
import re
from collections import Counter
from dataclasses import dataclass

from PIL import Image, ImageChops, ImageDraw, ImageFont, ImageOps

from app.core.config import settings
#from config import settings

logger = logging.getLogger(__name__)


@dataclass
class CaptchaResult:
    code: str
    confidence: float


class BaseCaptchaSolver:
    name = "base"

    def solve(self, image_bytes: bytes) -> CaptchaResult:
        raise NotImplementedError


class FixedValueCaptchaSolver(BaseCaptchaSolver):
    name = "fixed"

    def __init__(self, fixed_value: str) -> None:
        self.fixed_value = self._normalize_code(fixed_value)

    def _normalize_code(self, value: str) -> str:
        return value.strip()

    def solve(self, image_bytes: bytes) -> CaptchaResult:
        return CaptchaResult(code=self.fixed_value, confidence=1.0)


class TemplateCaptchaSolver(BaseCaptchaSolver):
    """
    轻量 fallback。

    当更强的 OCR provider 不可用时，仍然提供一个不依赖额外模型的本地方案。
    """

    name = "template"
    charset = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"

    def _binarize(self, image_bytes: bytes) -> Image.Image:
        image = Image.open(io.BytesIO(image_bytes)).convert("L")
        image = ImageOps.autocontrast(image)
        return image.point(lambda pixel: 255 if pixel > 170 else 0)

    def _segment(self, image: Image.Image) -> list[Image.Image]:
        width, height = image.size
        dark_columns: list[int] = []
        for x in range(width):
            if any(image.getpixel((x, y)) == 0 for y in range(height)):
                dark_columns.append(x)
        if not dark_columns:
            return []
        segments: list[tuple[int, int]] = []
        start = dark_columns[0]
        previous = dark_columns[0]
        for x in dark_columns[1:]:
            if x - previous > 1:
                segments.append((start, previous + 1))
                start = x
            previous = x
        segments.append((start, previous + 1))
        images = [image.crop((left, 0, right, height)) for left, right in segments if right - left >= 2]
        if len(images) in {0, 1}:
            slice_width = max(1, width // 4)
            return [
                image.crop((index * slice_width, 0, min(width, (index + 1) * slice_width), height))
                for index in range(4)
            ]
        return images

    def _build_templates(self, size: tuple[int, int]) -> dict[str, Image.Image]:
        font = ImageFont.load_default()
        templates: dict[str, Image.Image] = {}
        for char in self.charset:
            canvas = Image.new("L", size, color=255)
            draw = ImageDraw.Draw(canvas)
            bbox = draw.textbbox((0, 0), char, font=font)
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]
            draw.text(
                ((size[0] - text_width) / 2, (size[1] - text_height) / 2),
                char,
                fill=0,
                font=font,
            )
            templates[char] = canvas
        return templates

    def _normalize_code(self, code: str) -> str:
        return _normalize_captcha_code(code)

    def solve(self, image_bytes: bytes) -> CaptchaResult:
        image = self._binarize(image_bytes)
        segments = self._segment(image)
        if not segments:
            logger.warning("Template captcha segmentation returned no character slices")
            return CaptchaResult(code="", confidence=0.0)
        templates = self._build_templates((20, image.size[1]))
        result_chars: list[str] = []
        confidences: list[float] = []
        for segment in segments[:6]:
            normalized = ImageOps.pad(segment, (20, image.size[1]), color=255)
            best_char = ""
            best_score = float("inf")
            for char, template in templates.items():
                diff = ImageChops.difference(normalized, template)
                score = sum(diff.getdata())
                if score < best_score:
                    best_score = score
                    best_char = char
            result_chars.append(best_char)
            confidences.append(max(0.0, 1.0 - best_score / 100000))
        return CaptchaResult(
            code=self._normalize_code("".join(result_chars)),
            confidence=sum(confidences) / max(len(confidences), 1),
        )


class DdddOcrCaptchaSolver(BaseCaptchaSolver):
    """
    更适合生产环境的本地 OCR 方案。

    - 完全本地识别
    - 不依赖外部验证码服务
    - 对常见中文教务系统的简单图形验证码通常明显强于模板法
    """

    name = "ddddocr"

    def __init__(self) -> None:
        try:
            import ddddocr  # type: ignore
        except ImportError as exc:
            raise RuntimeError("ddddocr is not installed") from exc
        self._ocr = ddddocr.DdddOcr(show_ad=False, beta=True)

    def _to_png_bytes(self, image: Image.Image) -> bytes:
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        return buffer.getvalue()

    def _build_variants(self, image_bytes: bytes) -> list[tuple[str, bytes]]:
        image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        grayscale = ImageOps.grayscale(image)
        variants = [
            ("original", self._to_png_bytes(image)),
            ("grayscale", self._to_png_bytes(grayscale.convert("RGB"))),
            ("threshold-150", self._to_png_bytes(grayscale.point(lambda pixel: 255 if pixel > 150 else 0).convert("RGB"))),
            ("threshold-180", self._to_png_bytes(grayscale.point(lambda pixel: 255 if pixel > 180 else 0).convert("RGB"))),
            ("invert-threshold", self._to_png_bytes(ImageOps.invert(grayscale).point(lambda pixel: 255 if pixel > 120 else 0).convert("RGB"))),
        ]
        return variants

    def solve(self, image_bytes: bytes) -> CaptchaResult:
        candidates: list[str] = []
        variants = self._build_variants(image_bytes)
        for variant_name, variant_bytes in variants:
            try:
                raw_text = self._ocr.classification(variant_bytes)
            except Exception as exc:
                logger.warning("ddddocr failed on variant %s: %s", variant_name, exc)
                continue
            normalized = _normalize_captcha_code(raw_text)
            if normalized:
                candidates.append(normalized)

        if not candidates:
            return CaptchaResult(code="", confidence=0.0)

        counter = Counter(candidates)
        best_code, best_count = counter.most_common(1)[0]
        confidence = best_count / len(candidates)
        if settings.portal_captcha_expected_length and len(best_code) != settings.portal_captcha_expected_length:
            confidence *= 0.65
        logger.info(
            "DdddOcrCaptchaSolver candidates: %s, selected: %s with confidence %.2f",
            dict(counter),
            best_code,
            confidence,
        )
        return CaptchaResult(code=best_code, confidence=confidence)


class CompositeCaptchaSolver(BaseCaptchaSolver):
    name = "composite"

    def __init__(self, solvers: list[BaseCaptchaSolver]) -> None:
        self.solvers = solvers

    def solve(self, image_bytes: bytes) -> CaptchaResult:
        best_result = CaptchaResult(code="", confidence=0.0)
        for solver in self.solvers:
            try:
                result = solver.solve(image_bytes)
            except Exception as exc:
                logger.warning("Captcha solver %s failed: %s", solver.name, exc)
                continue
            if result.code and result.confidence >= best_result.confidence:
                best_result = result
            if result.code and result.confidence >= 0.95:
                break
        return best_result


def _normalize_captcha_code(value: str | None) -> str:
    text = re.sub(r"\s+", "", (value or ""))
    allowed = settings.portal_captcha_charset
    text = "".join(char for char in text if char in allowed)
    expected_length = settings.portal_captcha_expected_length
    if expected_length and len(text) > expected_length:
        text = text[:expected_length]
    return text


def build_captcha_solver() -> BaseCaptchaSolver:
    if settings.portal_fixed_captcha:
        return FixedValueCaptchaSolver(settings.portal_fixed_captcha)

    solver_name = settings.portal_captcha_solver.lower().strip()
    if solver_name == "template":
        return TemplateCaptchaSolver()
    if solver_name == "ddddocr":
        return DdddOcrCaptchaSolver()
    if solver_name == "auto":
        solvers: list[BaseCaptchaSolver] = []
        try:
            solvers.append(DdddOcrCaptchaSolver())
        except Exception as exc:
            logger.warning("ddddocr unavailable, falling back to template solver: %s", exc)
        solvers.append(TemplateCaptchaSolver())
        return CompositeCaptchaSolver(solvers)
    raise RuntimeError(f"Unsupported captcha solver: {settings.portal_captcha_solver}")
