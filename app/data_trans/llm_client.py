"""
火山引擎方舟大模型客户端
使用 volcengine-python-sdk[ark] 调用大模型 API
参考文档: https://www.volcengine.com/docs/82379/1541595
"""

import json
import re
from typing import Any, Dict, List, Optional

from .ai_config import ArkConfig, GEO_EXTRACTION_PROMPT, get_config


class ArkClient:
    """
    火山引擎方舟大模型客户端

    使用示例:
        client = ArkClient()
        result = client.extract_geo_info("实验小学：中山路以东，解放路以北")
        print(result)  # {"school_name": "实验小学", "boundaries": [...], "includes": [...]}
    """

    def __init__(self, config: Optional[ArkConfig] = None):
        """
        初始化客户端

        Args:
            config: 配置对象，不传则从环境变量读取
        """
        self.config = config or get_config()
        self._client = None

    def _get_client(self):
        """懒加载火山引擎 Ark 客户端"""
        if self._client is None:
            try:
                from volcenginesdkarkruntime import Ark
            except ImportError:
                raise ImportError(
                    "请安装火山引擎 SDK: pip install 'volcengine-python-sdk[ark]'"
                )

            # 验证配置
            self.config.validate()

            # 初始化客户端
            client_kwargs = {"api_key": self.config.api_key}
            if self.config.base_url:
                client_kwargs["base_url"] = self.config.base_url

            self._client = Ark(**client_kwargs)

        return self._client

    def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> str:
        """
        发送对话请求

        Args:
            messages: 消息列表，格式为 [{"role": "user", "content": "..."}]
            temperature: 温度参数 (可选)
            max_tokens: 最大 token 数 (可选)

        Returns:
            模型返回的文本内容
        """
        client = self._get_client()

        response = client.chat.completions.create(
            model=self.config.endpoint_id,
            messages=messages,
            temperature=temperature or self.config.temperature,
            max_tokens=max_tokens or self.config.max_tokens,
        )

        return response.choices[0].message.content

    def chat_stream(
        self,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ):
        """
        发送流式对话请求

        Args:
            messages: 消息列表
            temperature: 温度参数 (可选)
            max_tokens: 最大 token 数 (可选)

        Yields:
            逐个返回的文本片段
        """
        client = self._get_client()

        stream = client.chat.completions.create(
            model=self.config.endpoint_id,
            messages=messages,
            temperature=temperature or self.config.temperature,
            max_tokens=max_tokens or self.config.max_tokens,
            stream=True,
        )

        for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content

    def extract_geo_info(self, text: str) -> Dict[str, Any]:
        """
        从文本中提取地理信息

        Args:
            text: 包含学校施教区描述的文本

        Returns:
            结构化的地理信息字典
        """
        prompt = GEO_EXTRACTION_PROMPT.format(input_text=text)

        messages = [{"role": "user", "content": prompt}]

        response = self.chat(messages, temperature=0.1)

        # 解析 JSON 响应
        return self._parse_json_response(response)

    def extract_geo_info_batch(self, texts: List[str]) -> List[Dict[str, Any]]:
        """
        批量提取地理信息

        Args:
            texts: 文本列表

        Returns:
            结构化地理信息字典列表
        """
        results = []
        for text in texts:
            try:
                result = self.extract_geo_info(text)
                results.append({"success": True, "data": result, "error": None})
            except Exception as e:
                results.append({"success": False, "data": None, "error": str(e)})
        return results

    def _parse_json_response(self, response: str) -> Dict[str, Any]:
        """
        解析 LLM 返回的 JSON 响应

        处理可能存在的 markdown 代码块包裹
        """
        text = response.strip()

        # 尝试提取 markdown 代码块中的 JSON
        json_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
        if json_match:
            text = json_match.group(1)

        # 尝试直接解析 JSON
        try:
            return json.loads(text)
        except json.JSONDecodeError as e:
            raise ValueError(f"无法解析 LLM 返回的 JSON: {e}\n原始响应: {response}")


# 便捷函数
def extract_geo_info(text: str) -> Dict[str, Any]:
    """快捷方式：提取地理信息"""
    return ArkClient().extract_geo_info(text)


def chat(message: str) -> str:
    """快捷方式：发送单条消息"""
    return ArkClient().chat([{"role": "user", "content": message}])
