"""
AI/LLM 配置文件
使用火山引擎 volcengine-python-sdk[ark] 调用大模型
参考文档: https://www.volcengine.com/docs/82379/1541595
"""

import os
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ArkConfig:
    """火山引擎方舟大模型配置类"""

    # API Key (从火山引擎控制台获取)
    api_key: str = ""

    # 推理接入点 ID (Endpoint ID)
    # 在火山引擎控制台创建推理接入点后获取
    endpoint_id: str = ""

    # 请求参数
    temperature: float = 0.1  # 低温度 = 更稳定的输出
    max_tokens: int = 2000
    timeout: int = 60

    # 可选：指定 Base URL (一般不需要修改)
    base_url: str = ""

    @classmethod
    def from_env(cls) -> "ArkConfig":
        """从环境变量加载配置"""
        return cls(
            api_key=os.getenv("ARK_API_KEY", ""),
            endpoint_id=os.getenv("ARK_ENDPOINT_ID", ""),
            temperature=float(os.getenv("ARK_TEMPERATURE", "0.1")),
            max_tokens=int(os.getenv("ARK_MAX_TOKENS", "2000")),
            timeout=int(os.getenv("ARK_TIMEOUT", "60")),
            base_url=os.getenv("ARK_BASE_URL", ""),
        )

    def validate(self) -> bool:
        """验证配置是否完整"""
        if not self.api_key:
            raise ValueError("ARK_API_KEY 未设置，请在环境变量中配置")
        if not self.endpoint_id:
            raise ValueError("ARK_ENDPOINT_ID 未设置，请在环境变量中配置")
        return True


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

# Output Format (JSON)
请严格遵守以下 JSON 结构，不要返回任何多余的解释文字：

{
  "school_name": "string",
  "boundaries": [
    {
      "name": "string",
      "type": "road" | "river" | "railway" | "other",
      "relation": "east_of" | "west_of" | "south_of" | "north_of" | null
    }
  ],
  "includes": [
    {
      "name": "string",
      "type": "village" | "community" | "estate" | "other"
    }
  ]
}

# Input Text
{input_text}
"""


# 默认配置实例
_default_config: Optional[ArkConfig] = None


def get_config() -> ArkConfig:
    """获取全局配置"""
    global _default_config
    if _default_config is None:
        _default_config = ArkConfig.from_env()
    return _default_config


def set_config(config: ArkConfig):
    """设置全局配置"""
    global _default_config
    _default_config = config
