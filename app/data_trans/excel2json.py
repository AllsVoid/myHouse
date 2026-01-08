"""
Excel 文件解析器
支持 .xlsx 和 .xls 格式
"""

from pathlib import Path
from typing import Any, Dict, List, Union

from .base_parser import BaseParser


class ExcelParser(BaseParser):
    """Excel 文件解析器"""

    SUPPORTED_EXTENSIONS = [".xlsx", ".xls"]

    def __init__(self):
        self._pd = None

    def _get_pandas(self):
        """懒加载 pandas"""
        if self._pd is None:
            try:
                import pandas as pd

                self._pd = pd
            except ImportError:
                raise ImportError("请安装 pandas: pip install pandas openpyxl xlrd")
        return self._pd

    def parse(
        self,
        file_path: Union[str, Path],
        school_col: str = None,
        zone_col: str = None,
    ) -> Dict[str, Any]:
        """
        解析 Excel 文件为施教区记录列表

        Args:
            file_path: Excel 文件路径
            school_col: 学校名称列名（不指定则自动识别）
            zone_col: 施教区描述列名（不指定则自动识别）

        Returns:
            {
                "success": bool,
                "file_path": str,
                "content": [{"school": "实验小学", "zone_desc": "..."}, ...],
                "error": str | None
            }
        """
        file_path = Path(file_path)
        pd = self._get_pandas()

        try:
            excel_file = pd.ExcelFile(file_path)
            records = []

            for sheet_name in excel_file.sheet_names:
                df = pd.read_excel(excel_file, sheet_name=sheet_name)
                df = df.ffill()  # 处理合并单元格

                # 自动识别学校列
                _school_col = school_col
                if _school_col is None:
                    for col in df.columns:
                        if "学校" in str(col) or "名称" in str(col):
                            _school_col = col
                            break

                # 自动识别施教区列
                _zone_col = zone_col
                if _zone_col is None:
                    for col in df.columns:
                        if (
                            "施教" in str(col)
                            or "范围" in str(col)
                            or "区域" in str(col)
                        ):
                            _zone_col = col
                            break

                if _school_col and _zone_col:
                    for _, row in df.iterrows():
                        records.append(
                            {
                                "school": str(row.get(_school_col, "")).strip(),
                                "zone_desc": str(row.get(_zone_col, "")).strip(),
                            }
                        )

            return {
                "success": True,
                "file_path": str(file_path),
                "content": records,
                "error": None,
            }

        except Exception as e:
            return {
                "success": False,
                "file_path": str(file_path),
                "content": None,
                "error": str(e),
            }
