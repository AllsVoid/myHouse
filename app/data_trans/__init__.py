"""
数据转换模块
用于将各种格式的文件 (PDF/图片/Word/Excel) 转换为结构化 JSON 数据
"""

from .ai_config import ArkConfig, get_config, set_config
from .base_parser import BaseParser
from .doc2json import DocParser
from .excel2json import ExcelParser
from .img2json import ImageParser
from .llm_client import ArkClient, chat, extract_geo_info
from .pdf2json import PDFParser
from .trans import DataTrans, process_files

__all__ = [
    # 核心调度器
    "DataTrans",
    "process_files",
    # 解析器
    "BaseParser",
    "PDFParser",
    "ImageParser",
    "DocParser",
    "ExcelParser",
    # LLM 客户端
    "ArkClient",
    "ArkConfig",
    "get_config",
    "set_config",
    "chat",
    "extract_geo_info",
]
