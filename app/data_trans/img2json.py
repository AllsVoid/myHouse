"""
图片文件解析器
使用 PaddleOCR 进行中文文字识别
支持普通 OCR 和表格识别两种模式
参考文档: https://www.paddleocr.ai/latest/version3.x/pipeline_usage/PP-StructureV3.html
"""

from pathlib import Path
from typing import Any, Dict, Literal, Union

from .base_parser import BaseParser


class ImageParser(BaseParser):
    """图片文件解析器 (OCR)"""

    SUPPORTED_EXTENSIONS = [".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".tif", ".webp"]

    def __init__(self):
        self._ocr = None
        self._structure = None

    def _get_ocr(self):
        """懒加载 PaddleOCR"""
        if self._ocr is None:
            try:
                from paddleocr import PaddleOCR

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

    def _get_structure(self):
        """懒加载 PP-StructureV3（用于表格识别）"""
        if self._structure is None:
            try:
                from paddleocr import PPStructureV3

                self._structure = PPStructureV3()
            except ImportError:
                raise ImportError(
                    "请安装 PaddleOCR: pip install paddleocr paddlepaddle"
                )
        return self._structure

    def parse(
        self,
        file_path: Union[str, Path],
        mode: Literal["ocr", "table"] = "table",
    ) -> Dict[str, Any]:
        """
        解析图片文件，提取其中的文字

        Args:
            file_path: 图片文件路径
            mode: 解析模式
                - "ocr": 普通文字识别（默认）
                - "table": 表格识别，使用 PP-StructureV3，适合表格类图片

        Returns:
            {
                "success": bool,
                "file_path": str,
                "content": str,  # ocr 模式返回纯文本，table 模式返回 Markdown
                "confidence": float | None,
                "error": str | None
            }
        """
        file_path = Path(file_path)

        try:
            if mode == "table":
                return self._parse_table(file_path)
            else:
                return self._parse_ocr(file_path)

        except Exception as e:
            return {
                "success": False,
                "file_path": str(file_path),
                "content": None,
                "confidence": None,
                "error": str(e),
            }

    def _parse_ocr(self, file_path: Path) -> Dict[str, Any]:
        """普通 OCR 模式"""
        ocr = self._get_ocr()
        result = ocr.predict(str(file_path))

        if not result or len(result) == 0:
            return {
                "success": True,
                "file_path": str(file_path),
                "content": "",
                "confidence": 0,
                "error": None,
            }

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

        avg_confidence = sum(scores) / len(scores) if scores else 0

        return {
            "success": True,
            "file_path": str(file_path),
            "content": "\n".join(texts),
            "confidence": round(avg_confidence, 4),
            "error": None,
        }

    def _parse_table(self, file_path: Path) -> Dict[str, Any]:
        """
        表格识别模式，使用 PP-StructureV3
        适合处理包含表格的图片，能正确识别单元格内换行的文字
        """
        structure = self._get_structure()
        result = structure.predict(str(file_path))

        if not result or len(result) == 0:
            return {
                "success": True,
                "file_path": str(file_path),
                "content": "",
                "confidence": None,
                "error": None,
            }

        structure_result = result[0]
        content_parts = []

        # 从 parsing_res_list 提取内容（LayoutBlock 对象列表）
        parsing_res = structure_result.get("parsing_res_list", [])
        for item in parsing_res:
            # LayoutBlock 对象，使用属性访问
            if hasattr(item, "content") and item.content:
                content_parts.append(item.content)

        # 如果没有 parsing_res_list，尝试从 table_res_list 获取
        if not content_parts:
            table_res = structure_result.get("table_res_list", [])
            for item in table_res:
                if isinstance(item, dict) and "pred_html" in item:
                    content_parts.append(item["pred_html"])

        # 如果还是没有，从 ocr_res 提取文本
        if not content_parts:
            ocr_res = structure_result.get("ocr_res", {})
            texts = ocr_res.get("rec_texts", [])
            if texts:
                content_parts.append("\n".join(texts))

        return {
            "success": True,
            "file_path": str(file_path),
            "content": "\n\n".join(content_parts),
            "confidence": None,
            "error": None,
        }
