"""
基础解析器抽象类
所有文件类型的解析器都必须继承此类并实现 parse 方法
"""
from abc import ABC, abstractmethod
from typing import Union, List, Dict, Any
from pathlib import Path


class BaseParser(ABC):
    """文件解析器基类"""
    
    # 子类必须定义支持的文件扩展名
    SUPPORTED_EXTENSIONS: List[str] = []
    
    @abstractmethod
    def parse(self, file_path: Union[str, Path]) -> Dict[str, Any]:
        """
        解析单个文件，提取文本内容
        
        Args:
            file_path: 文件路径
            
        Returns:
            包含提取内容的字典，格式如：
            {
                "success": bool,
                "file_path": str,
                "content": str,  # 提取的文本内容
                "error": str | None
            }
        """
        pass
    
    def parse_batch(self, file_paths: List[Union[str, Path]]) -> List[Dict[str, Any]]:
        """
        批量解析文件
        
        Args:
            file_paths: 文件路径列表
            
        Returns:
            解析结果列表
        """
        results = []
        for fp in file_paths:
            try:
                result = self.parse(fp)
                results.append(result)
            except Exception as e:
                results.append({
                    "success": False,
                    "file_path": str(fp),
                    "content": None,
                    "error": str(e)
                })
        return results
    
    @classmethod
    def can_handle(cls, file_path: Union[str, Path]) -> bool:
        """判断该解析器是否能处理此文件类型"""
        ext = Path(file_path).suffix.lower()
        return ext in cls.SUPPORTED_EXTENSIONS
