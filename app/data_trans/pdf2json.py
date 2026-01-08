"""
PDF 文件解析器
支持电子版 PDF 和扫描版 PDF (降级使用 OCR)
"""

from pathlib import Path
from typing import Any, Dict, Union

from .base_parser import BaseParser


class PDFParser(BaseParser):
    """PDF 文件解析器"""

    SUPPORTED_EXTENSIONS = [".pdf"]

    def __init__(self):
        self._pdfplumber = None
        self._ocr = None

    def _get_pdfplumber(self):
        """懒加载 pdfplumber"""
        if self._pdfplumber is None:
            try:
                import pdfplumber

                self._pdfplumber = pdfplumber
            except ImportError:
                raise ImportError("请安装 pdfplumber: pip install pdfplumber")
        return self._pdfplumber

    def _get_ocr(self):
        """懒加载 OCR (用于扫描版 PDF)"""
        if self._ocr is None:
            try:
                from paddleocr import PaddleOCR

                self._ocr = PaddleOCR(use_angle_cls=True, lang="ch", show_log=False)
            except ImportError:
                raise ImportError(
                    "请安装 PaddleOCR: pip install paddleocr paddlepaddle"
                )
        return self._ocr

    def parse(self, file_path: Union[str, Path]) -> Dict[str, Any]:
        """
        解析 PDF 文件

        优先使用 pdfplumber 提取电子版文本，
        如果提取不到内容，则降级使用 OCR 处理扫描版
        """
        file_path = Path(file_path)
        pdfplumber = self._get_pdfplumber()

        extracted_text = ""
        is_scanned = False

        try:
            with pdfplumber.open(file_path) as pdf:
                for page in pdf.pages:
                    text = page.extract_text()
                    if text:
                        extracted_text += text + "\n"

            # 如果提取的文本太少，可能是扫描版
            if len(extracted_text.strip()) < 20:
                is_scanned = True
                extracted_text = self._ocr_fallback(file_path)

            return {
                "success": True,
                "file_path": str(file_path),
                "content": extracted_text.strip(),
                "is_scanned": is_scanned,
                "error": None,
            }

        except Exception as e:
            return {
                "success": False,
                "file_path": str(file_path),
                "content": None,
                "is_scanned": None,
                "error": str(e),
            }

    def _ocr_fallback(self, file_path: Path) -> str:
        """
        OCR 降级处理：将 PDF 转为图片后进行 OCR
        """
        try:
            import fitz  # PyMuPDF
        except ImportError:
            raise ImportError("扫描版 PDF 需要 PyMuPDF: pip install pymupdf")

        ocr = self._get_ocr()
        all_text = []

        doc = fitz.open(file_path)
        for page_num in range(len(doc)):
            page = doc.load_page(page_num)
            # 将页面渲染为图片
            pix = page.get_pixmap(dpi=200)
            img_bytes = pix.tobytes("png")

            # 新版 PaddleOCR 使用 __call__ 方法替代已弃用的 .ocr() 方法
            result = ocr(img_bytes)
            if result and result[0]:
                page_text = "\n".join([line[1][0] for line in result[0]])
                all_text.append(page_text)

        doc.close()
        return "\n".join(all_text)
