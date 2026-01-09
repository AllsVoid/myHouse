"""
火山引擎方舟大模型 AI 助手
使用 volcenginesdkarkruntime 的 responses API 进行对话
参考文档: https://www.volcengine.com/docs/82379/1399008
Files API: https://www.volcengine.com/docs/82379/1870405
"""

import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any, Dict, Generator, List, Optional, Union

from volcenginesdkarkruntime import Ark

# Token 阈值配置 (字符数估算，1个中文字符约等于1.5-2个token)
MAX_CHARS_DIRECT = 15000  # 直接发送的最大字符数
MAX_CHARS_PER_SEGMENT = 12000  # 分段处理时每段的最大字符数

# 提取地理信息的 Prompt 模板
GEO_EXTRACTION_PROMPT = """# Role
你是一个专业的 GIS 地理数据提取助手。你的任务是从非结构化的中文学校施教区描述文本中，提取出关键的地理要素，并将其转换为结构化 JSON 数据。

# Extraction Rules
1. **school_name**: 提取文本中描述的主体学校名称。
2. **boundaries (边界线)**: 
   - 提取所有用于界定范围的线状要素（如：道路、河流、铁轨）。
   - 分析施教区相对于该边界的方位关系：
     - "XX路以东" -> relation: "east_of" (区域在边界东侧)
     - "XX路以西" -> relation: "west_of"
     - "XX路以南" -> relation: "south_of"
     - "XX路以北" -> relation: "north_of"
     - "东至XX路" -> relation: "west_of" (区域在XX路以西)
     - 若未指明方向，relation 为 null
3. **includes (包含区域)**: 
   - 提取文本中明确列举的块状区域（如：村庄、小区、社区）。

# Output Format (JSON Array)
请严格遵守以下 JSON 结构。如果文本中包含多个学校，返回一个数组。不要返回任何多余的解释文字：

[
  {
    "school_name": "string",
    "boundaries": [
      {
        "name": "string",
        "type": "road | river | railway | other",
        "relation": "east_of | west_of | south_of | north_of | null"
      }
    ],
    "includes": [
      {
        "name": "string",
        "type": "village | community | estate | other"
      }
    ]
  }
]
"""

# 文件上传后的提取 Prompt
GEO_EXTRACTION_WITH_FILE_PROMPT = """请阅读上传的文件内容，这是一份学校施教区划分文档。

# 任务
从文档中提取每个学校的施教区地理信息，转换为结构化 JSON 数据。

# Extraction Rules
1. **school_name**: 学校名称
2. **boundaries (边界线)**: 
   - 道路/河流等线状边界
   - relation 表示施教区相对于边界的方位：
     - "XX路以东" -> "east_of"
     - "XX路以西" -> "west_of"  
     - "XX路以南" -> "south_of"
     - "XX路以北" -> "north_of"
3. **includes**: 明确包含的小区/村庄

# Output Format (JSON Array)
返回 JSON 数组，每个学校一个对象。不要返回任何解释文字，只返回 JSON：

[
  {
    "school_name": "string",
    "boundaries": [{"name": "string", "type": "road|river|railway|other", "relation": "east_of|west_of|south_of|north_of|null"}],
    "includes": [{"name": "string", "type": "village|community|estate|other"}]
  }
]
"""


class AiConfig:
    """AI 助手配置类"""

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: str = "https://ark.cn-beijing.volces.com/api/v3",
        model: str = "ep-20260109153350-7pdqw",
        thinking_enabled: bool = False,
    ):
        """
        初始化配置

        Args:
            api_key: API Key，不传则从环境变量 ARK_API_KEY 获取
            base_url: API 基础 URL
            model: 模型名称或推理接入点 ID
            thinking_enabled: 是否启用思考模式
        """
        self.api_key = api_key or os.getenv("ARK_API_KEY", "")
        self.base_url = base_url
        self.model = model
        self.thinking_enabled = thinking_enabled

    def validate(self) -> bool:
        """验证配置是否完整"""
        if not self.api_key:
            raise ValueError(
                "ARK_API_KEY 未设置，请在环境变量中配置或传入 api_key 参数"
            )
        return True


class Ai:
    """
    火山引擎方舟大模型 AI 助手

    支持:
    - 普通对话
    - 多轮对话 (生成器模式)
    - 文件上传后对话 (Files API)
    - 地理信息提取
    """

    def __init__(self, config: Optional[AiConfig] = None):
        """
        初始化 AI 助手

        Args:
            config: 配置对象，不传则使用默认配置（从环境变量读取）
        """
        self.config = config or AiConfig()
        self._client: Optional[Ark] = None

    @property
    def client(self) -> Ark:
        """懒加载 Ark 客户端"""
        if self._client is None:
            self.config.validate()
            self._client = Ark(
                base_url=self.config.base_url,
                api_key=self.config.api_key,
            )
        return self._client

    def _build_extra_body(
        self, thinking_enabled: Optional[bool] = None
    ) -> Dict[str, Any]:
        """构建 extra_body 参数"""
        enabled = (
            thinking_enabled
            if thinking_enabled is not None
            else self.config.thinking_enabled
        )
        return {"thinking": {"type": "enabled" if enabled else "disabled"}}

    def _send_request(
        self,
        message: Union[str, List[Dict[str, str]]],
        previous_response_id: Optional[str] = None,
        model: Optional[str] = None,
        thinking_enabled: Optional[bool] = None,
    ) -> Any:
        """
        发送对话请求（内部方法）

        Args:
            message: 用户消息
            previous_response_id: 上一轮对话的响应 ID
            model: 模型名称
            thinking_enabled: 是否启用思考模式

        Returns:
            API 响应对象
        """
        request_kwargs: Dict[str, Any] = {
            "model": model or self.config.model,
            "input": message,
            "extra_body": self._build_extra_body(thinking_enabled),
        }

        if previous_response_id:
            request_kwargs["previous_response_id"] = previous_response_id

        return self.client.responses.create(**request_kwargs)

    def chat_once(self, message: str) -> str:
        """
        单次对话，返回纯文本响应

        Args:
            message: 用户消息

        Returns:
            模型响应的文本内容
        """
        response = self._send_request(message)
        return self._extract_response_text(response)

    def _extract_response_text(self, response: Any) -> str:
        """从响应对象中提取文本内容"""
        if hasattr(response, "output") and hasattr(response.output, "message"):
            return response.output.message.content
        elif hasattr(response, "output"):
            # 尝试其他格式
            output = response.output
            if isinstance(output, dict) and "message" in output:
                return output["message"].get("content", "")
            elif hasattr(output, "content"):
                return output.content
        return str(response)

    # ==================== Files API ====================

    def upload_file(
        self, file_path: Union[str, Path], purpose: str = "file-extract"
    ) -> str:
        """
        上传文件到火山引擎

        Args:
            file_path: 文件路径
            purpose: 文件用途，默认 "file-extract"

        Returns:
            文件 ID
        """
        file_path = Path(file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"文件不存在: {file_path}")

        with open(file_path, "rb") as f:
            response = self.client.files.create(file=f, purpose=purpose)

        return response.id

    def upload_text_as_file(self, text: str, filename: str = "content.txt") -> str:
        """
        将文本内容作为文件上传

        Args:
            text: 文本内容
            filename: 文件名

        Returns:
            文件 ID
        """
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".txt", delete=False, encoding="utf-8"
        ) as f:
            f.write(text)
            temp_path = f.name

        try:
            file_id = self.upload_file(temp_path)
        finally:
            os.unlink(temp_path)

        return file_id

    def chat_with_file(self, file_id: str, prompt: str) -> str:
        """
        基于已上传文件进行对话

        Args:
            file_id: 已上传的文件 ID
            prompt: 提示词

        Returns:
            模型响应的文本内容
        """
        # 构建包含文件引用的消息
        message = [
            {
                "type": "file",
                "file_id": file_id,
            },
            {
                "type": "text",
                "text": prompt,
            },
        ]

        response = self._send_request(message)
        return self._extract_response_text(response)

    def delete_file(self, file_id: str) -> bool:
        """
        删除已上传的文件

        Args:
            file_id: 文件 ID

        Returns:
            是否删除成功
        """
        try:
            self.client.files.delete(file_id)
            return True
        except Exception:
            return False

    # ==================== 地理信息提取 ====================

    def extract_geo_info(self, text: str) -> List[Dict[str, Any]]:
        """
        从文本中提取地理信息

        自动选择处理策略:
        - 短文本: 直接发送
        - 长文本: 先尝试 Files API，失败则分段处理

        Args:
            text: 施教区描述文本

        Returns:
            结构化的地理信息列表
        """
        text_len = len(text)

        # 短文本: 直接发送
        if text_len <= MAX_CHARS_DIRECT:
            return self._extract_geo_direct(text)

        # 长文本: 优先使用 Files API
        try:
            return self._extract_geo_with_file(text)
        except Exception as e:
            # Files API 失败，降级到分段处理
            print(f"       [WARN] Files API 失败 ({e})，降级到分段处理")
            return self._extract_geo_segmented(text)

    def _extract_geo_direct(self, text: str) -> List[Dict[str, Any]]:
        """直接发送文本提取地理信息"""
        prompt = GEO_EXTRACTION_PROMPT.replace("{input_text}", text)
        response = self.chat_once(prompt)
        return self._parse_json_response(response)

    def _extract_geo_with_file(self, text: str) -> List[Dict[str, Any]]:
        """通过 Files API 上传后提取地理信息"""
        # 上传文本为文件
        file_id = self.upload_text_as_file(text)

        try:
            # 基于文件对话
            response = self.chat_with_file(file_id, GEO_EXTRACTION_WITH_FILE_PROMPT)
            return self._parse_json_response(response)
        finally:
            # 清理上传的文件
            self.delete_file(file_id)

    def _extract_geo_segmented(self, text: str) -> List[Dict[str, Any]]:
        """分段处理长文本"""
        segments = self._split_by_school(text)
        all_results = []

        for segment in segments:
            try:
                results = self._extract_geo_direct(segment)
                all_results.extend(results)
            except Exception as e:
                print(f"       [WARN] 分段处理失败: {e}")
                continue

        return all_results

    def _split_by_school(self, text: str) -> List[str]:
        """
        按学校分割文本

        查找 "XX学校的施教区" 或 "XX小学：" 等模式进行分割
        """
        # 常见的学校名称分隔模式
        patterns = [
            r"(?=[\u4e00-\u9fa5]+(?:小学|中学|学校|九年制学校)(?:的施教|施教区|：|:))",
            r"(?=\d+[、.]\s*[\u4e00-\u9fa5]+(?:小学|中学|学校))",
        ]

        segments = [text]
        for pattern in patterns:
            new_segments = []
            for seg in segments:
                parts = re.split(pattern, seg)
                parts = [p.strip() for p in parts if p.strip()]
                new_segments.extend(parts)
            segments = new_segments

        # 如果分割后某段仍然太长，进一步按字符数切割
        final_segments = []
        for seg in segments:
            if len(seg) <= MAX_CHARS_PER_SEGMENT:
                final_segments.append(seg)
            else:
                # 按段落切割
                for i in range(0, len(seg), MAX_CHARS_PER_SEGMENT):
                    chunk = seg[i : i + MAX_CHARS_PER_SEGMENT]
                    final_segments.append(chunk)

        return final_segments

    def _parse_json_response(self, response: str) -> List[Dict[str, Any]]:
        """
        解析 LLM 返回的 JSON 响应

        处理可能存在的 markdown 代码块包裹
        """
        text = response.strip()

        # 尝试提取 markdown 代码块中的 JSON
        json_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
        if json_match:
            text = json_match.group(1)

        # 尝试解析 JSON
        try:
            result = json.loads(text)
            # 确保返回的是列表
            if isinstance(result, dict):
                return [result]
            return result
        except json.JSONDecodeError as e:
            raise ValueError(
                f"无法解析 LLM 返回的 JSON: {e}\n原始响应: {response[:500]}"
            )

    # ==================== 多轮对话 ====================

    def conversation(
        self,
        first_message: Optional[str] = None,
        model: Optional[str] = None,
        thinking_enabled: Optional[bool] = None,
    ) -> Generator[Any, str, None]:
        """
        创建多轮对话生成器

        使用生成器模式进行多轮对话，通过 send() 方法发送后续消息

        Args:
            first_message: 第一轮对话消息（可选，也可以通过 send() 发送）
            model: 模型名称
            thinking_enabled: 是否启用思考模式

        Yields:
            每轮对话的响应对象
        """
        previous_response_id: Optional[str] = None

        # 处理第一条消息
        if first_message:
            message = first_message
        else:
            # 等待通过 send() 发送第一条消息
            message = yield  # type: ignore

        while True:
            # 发送请求
            response = self._send_request(
                message,
                previous_response_id=previous_response_id,
                model=model,
                thinking_enabled=thinking_enabled,
            )
            previous_response_id = response.id

            # yield 响应并等待下一条消息
            message = yield response
            if message is None:
                break


# 便捷函数
def chat(message: str) -> str:
    """快捷方式：单次对话"""
    return Ai().chat_once(message)


def extract_geo_info(text: str) -> List[Dict[str, Any]]:
    """快捷方式：提取地理信息"""
    return Ai().extract_geo_info(text)


if __name__ == "__main__":
    ai = Ai()

    # 测试单次对话
    response = ai.chat_once("你好，介绍一下自己")
    print("单次对话:", response[:100])
