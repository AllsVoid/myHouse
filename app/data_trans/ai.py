"""
火山引擎方舟大模型 AI 助手
使用 volcenginesdkarkruntime 的 responses API 进行对话
参考文档: https://www.volcengine.com/docs/82379/1399008
"""

import os
from typing import Any, Dict, Generator, List, Optional, Union

from volcenginesdkarkruntime import Ark


class AiConfig:
    """AI 助手配置类"""

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: str = "https://ark.cn-beijing.volces.com/api/v3",
        model: str = "ep-20250716095151-bw4sm",
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

    使用生成器模式进行多轮对话

    使用示例:
        ai = Ai()

        # 创建对话生成器
        conv = ai.conversation("Hi，帮我讲个笑话。")

        # 获取第一轮响应
        response = next(conv)
        print(response)

        # 通过 send() 继续对话
        response = conv.send("这个笑话的笑点在哪？")
        print(response)

        # 结束对话
        conv.close()
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

        使用示例:
            ai = Ai()
            conv = ai.conversation("你好，帮我讲个笑话")

            # 获取第一轮响应
            response = next(conv)
            print(response)

            # 发送后续消息并获取响应
            response = conv.send("这个笑话的笑点在哪？")
            print(response)

            # 结束对话
            conv.close()
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
def chat(message: str) -> Generator[Any, str, None]:
    """快捷方式：创建对话生成器"""
    return Ai().conversation(message)


if __name__ == "__main__":
    ai = Ai()

    # 创建对话生成器
    conv = ai.conversation("Hi，帮我讲个笑话。")

    # 获取第一轮响应
    response = next(conv)
    print("第一轮响应:", response)

    # 通过 send() 继续对话
    response = conv.send("这个笑话的笑点在哪？")
    print("第二轮响应:", response)

    response = conv.send("再讲一个更好笑的")
    print("第三轮响应:", response)

    # 结束对话
    conv.close()
