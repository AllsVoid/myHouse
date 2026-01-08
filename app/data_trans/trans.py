"""
文件类型分发器
根据文件类型自动选择对应的解析器进行处理
"""

import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Type, Union

from .base_parser import BaseParser
from .doc2json import DocParser
from .excel2json import ExcelParser
from .img2json import ImageParser
from .pdf2json import PDFParser


class DataTrans:
    """
    数据转换调度器

    使用示例:
        # 单文件处理
        trans = DataTrans()
        result = trans.process("./document.pdf")

        # 批量处理
        results = trans.process(["./a.pdf", "./b.xlsx", "./c.png"])

        # 处理整个目录
        results = trans.process_directory("./uploads/")
    """

    # 注册所有可用的解析器
    PARSERS: List[Type[BaseParser]] = [
        PDFParser,
        ImageParser,
        DocParser,
        ExcelParser,
    ]

    # 文件扩展名 -> 解析器类型 的映射 (自动构建)
    _EXT_PARSER_MAP: Dict[str, Type[BaseParser]] = {}

    def __init__(self):
        """初始化时构建扩展名映射表"""
        self._build_extension_map()

    def _build_extension_map(self):
        """根据注册的解析器，构建文件扩展名到解析器的映射"""
        for parser_cls in self.PARSERS:
            for ext in parser_cls.SUPPORTED_EXTENSIONS:
                self._EXT_PARSER_MAP[ext.lower()] = parser_cls

    def get_parser(self, file_path: Union[str, Path]) -> Optional[BaseParser]:
        """
        根据文件路径获取对应的解析器实例

        Args:
            file_path: 文件路径

        Returns:
            解析器实例，如果没有匹配的解析器则返回 None
        """
        ext = Path(file_path).suffix.lower()
        parser_cls = self._EXT_PARSER_MAP.get(ext)

        if parser_cls:
            return parser_cls()
        return None

    def process(
        self, files: Union[str, Path, List[Union[str, Path]]]
    ) -> Union[Dict[str, Any], List[Dict[str, Any]]]:
        """
        处理单个或多个文件

        Args:
            files: 单个文件路径，或文件路径列表

        Returns:
            单文件返回单个结果字典，多文件返回结果列表
        """
        # 统一转为列表处理
        if isinstance(files, (str, Path)):
            file_list = [files]
            is_single = True
        else:
            file_list = files
            is_single = False

        results = []
        for file_path in file_list:
            result = self._process_single(file_path)
            results.append(result)

        # 单文件直接返回结果，多文件返回列表
        return results[0] if is_single else results

    def _process_single(self, file_path: Union[str, Path]) -> Dict[str, Any]:
        """处理单个文件"""
        file_path = Path(file_path)

        # 1. 检查文件是否存在
        if not file_path.exists():
            return {
                "success": False,
                "file_path": str(file_path),
                "file_type": None,
                "content": None,
                "error": f"文件不存在: {file_path}",
            }

        # 2. 获取对应的解析器
        parser = self.get_parser(file_path)
        if not parser:
            ext = file_path.suffix.lower()
            return {
                "success": False,
                "file_path": str(file_path),
                "file_type": ext,
                "content": None,
                "error": f"不支持的文件类型: {ext}",
            }

        # 3. 调用解析器处理
        try:
            result = parser.parse(file_path)
            result["file_type"] = file_path.suffix.lower()
            return result
        except Exception as e:
            return {
                "success": False,
                "file_path": str(file_path),
                "file_type": file_path.suffix.lower(),
                "content": None,
                "error": f"解析失败: {str(e)}",
            }

    def process_directory(
        self, directory: Union[str, Path], recursive: bool = False
    ) -> List[Dict[str, Any]]:
        """
        处理整个目录中的所有支持文件

        Args:
            directory: 目录路径
            recursive: 是否递归处理子目录

        Returns:
            所有文件的处理结果列表
        """
        directory = Path(directory)
        if not directory.is_dir():
            raise ValueError(f"不是有效的目录: {directory}")

        # 获取所有支持的扩展名
        supported_exts = set(self._EXT_PARSER_MAP.keys())

        # 收集所有待处理文件
        files_to_process = []
        pattern = "**/*" if recursive else "*"

        for file_path in directory.glob(pattern):
            if file_path.is_file() and file_path.suffix.lower() in supported_exts:
                files_to_process.append(file_path)

        return self.process(files_to_process)

    @classmethod
    def get_supported_extensions(cls) -> List[str]:
        """获取所有支持的文件扩展名"""
        extensions = []
        for parser_cls in cls.PARSERS:
            extensions.extend(parser_cls.SUPPORTED_EXTENSIONS)
        return extensions


# 便捷函数
def process_files(
    files: Union[str, Path, List[Union[str, Path]]],
) -> Union[Dict, List[Dict]]:
    """快捷方式：直接处理文件"""
    return DataTrans().process(files)
