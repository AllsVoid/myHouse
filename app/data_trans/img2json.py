"""
图片文件解析器
使用 PaddleOCR 进行中文文字识别
"""

from pathlib import Path
from typing import Any, Dict, Union

from .base_parser import BaseParser


class ImageParser(BaseParser):
    """图片文件解析器 (OCR)"""

    SUPPORTED_EXTENSIONS = [".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".tif", ".webp"]

    def __init__(self):
        self._ocr = None

    def _get_ocr(self):
        """懒加载 PaddleOCR"""
        if self._ocr is None:
            try:
                from paddleocr import PaddleOCR

                # use_angle_cls: 开启方向分类，适合旋转的图片
                # lang="ch": 中文模式
                self._ocr = PaddleOCR(
                    use_doc_orientation_classify=False,
                    use_doc_unwarping=False,
                    use_textline_orientation=False,
                    lang="ch",
                )
            except ImportError:
                raise ImportError(
                    "请安装 PaddleOCR: pip install paddleocr paddlepaddle"
                )
        return self._ocr

    def parse(self, file_path: Union[str, Path]) -> Dict[str, Any]:
        """
        解析图片文件，提取其中的文字
        """
        file_path = Path(file_path)

        try:
            ocr = self._get_ocr()
            # PaddleOCR 3.x 使用 predict 方法，返回 OCRResult 对象列表
            result = ocr.predict(str(file_path))

            if not result or len(result) == 0:
                return {
                    "success": True,
                    "file_path": str(file_path),
                    "content": "",
                    "confidence": 0,
                    "error": None,
                }

            # 从 OCRResult 对象中提取 rec_texts 和 rec_scores
            ocr_result = result[0]
            texts = ocr_result.get("rec_texts", [])
            scores = ocr_result.get("rec_scores", [])

            if not texts:
                return {
                    "success": True,
                    "file_path": str(file_path),
                    "content": "",
                    "confidence": 0,
                    "error": None,
                }

            # 计算平均置信度
            avg_confidence = sum(scores) / len(scores) if scores else 0

            return {
                "success": True,
                "file_path": str(file_path),
                "content": "\n".join(texts),
                "confidence": round(avg_confidence, 4),
                "error": None,
            }

        except Exception as e:
            return {
                "success": False,
                "file_path": str(file_path),
                "content": None,
                "confidence": None,
                "error": str(e),
            }
