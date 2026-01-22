"""
火山引擎方舟大模型 AI 助手
使用 volcenginesdkarkruntime 的 Chat Completions API 进行对话
参考文档: https://www.volcengine.com/docs/82379/1494384
"""

import json
import os
import re
from pathlib import Path
from typing import Any, Dict, Generator, List, Optional

from dotenv import load_dotenv
from volcenginesdkarkruntime import Ark

# 加载项目根目录的 .env
load_dotenv(dotenv_path=Path(__file__).resolve().parents[2] / ".env")

# Token 阈值配置 (字符数估算，1个中文字符约等于1.5-2个token)
MAX_CHARS_DIRECT = 8000  # 调小阈值，避免输出过长导致截断
MAX_CHARS_PER_SEGMENT = 6000  # 分段大小也相应调整

# 模型最大输出 tokens
MAX_COMPLETION_TOKENS = 16384  # doubao 模型支持的最大输出 tokens

# 结构化输出的 JSON Schema
GEO_JSON_SCHEMA = {
    "type": "json_schema",
    "json_schema": {
        "name": "school_districts",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                "schools": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "school_name": {"type": "string"},
                            "boundaries": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "name": {"type": "string"},
                                        "type": {
                                            "type": "string",
                                            "enum": [
                                                "road",
                                                "river",
                                                "railway",
                                                "other",
                                            ],
                                        },
                                        "relation": {
                                            "type": ["string", "null"],
                                            "enum": [
                                                "east_of",
                                                "west_of",
                                                "south_of",
                                                "north_of",
                                                None,
                                            ],
                                        },
                                    },
                                    "required": ["name", "type", "relation"],
                                    "additionalProperties": False,
                                },
                            },
                            "includes": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "name": {"type": "string"},
                                        "type": {
                                            "type": "string",
                                            "enum": [
                                                "village",
                                                "community",
                                                "estate",
                                                "other",
                                            ],
                                        },
                                    },
                                    "required": ["name", "type"],
                                    "additionalProperties": False,
                                },
                            },
                        },
                        "required": ["school_name", "boundaries", "includes"],
                        "additionalProperties": False,
                    },
                }
            },
            "required": ["schools"],
            "additionalProperties": False,
        },
    },
}

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

# Output Format (JSON Object)
请严格遵守以下 JSON 结构。所有学校信息放在 schools 数组中。不要返回任何多余的解释文字：

{
  "schools": [
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
}

# Input Text
{input_text}
"""


class LLMParseError(Exception):
    """LLM 响应解析错误，包含原始响应内容"""

    def __init__(self, message: str, raw_response: str):
        super().__init__(message)
        self.raw_response = raw_response


class StreamJsonParser:
    """简单的流式 JSON 解析器，用于提取数组中的对象"""

    def __init__(self):
        self.decoder = json.JSONDecoder()
        self.buffer = ""
        self.in_array = False
        self.array_finished = False

    def feed(self, chunk: str) -> List[Dict[str, Any]]:
        self.buffer += chunk
        objects = []

        if self.array_finished:
            return []

        if not self.in_array:
            # 寻找数组开始 "schools": [ 或者直接 [
            # 考虑到可能有 markdown 代码块 ```json
            array_start = self.buffer.find("[")
            if array_start != -1:
                self.in_array = True
                self.buffer = self.buffer[array_start + 1 :]
            else:
                # 保持 buffer 大小合理，丢弃无用前缀（如果有）
                # 但要小心不要丢弃了 "schools": [ 的部分
                if len(self.buffer) > 2000 and "[" not in self.buffer:
                    self.buffer = self.buffer[-500:]
                return []

        # 尝试解析对象
        while True:
            # 跳过空白和逗号
            idx = 0
            while idx < len(self.buffer) and self.buffer[idx] in " \t\n\r,":
                idx += 1

            if idx >= len(self.buffer):
                # 只有空白，保留 buffer
                self.buffer = self.buffer[idx:]
                break

            if self.buffer[idx] == "]":
                # 数组结束
                self.buffer = self.buffer[idx + 1 :]
                self.array_finished = True
                break

            if self.buffer[idx] == "{":
                try:
                    obj, end_idx = self.decoder.raw_decode(self.buffer, idx)
                    if isinstance(obj, dict) and "school_name" in obj:
                        objects.append(obj)
                    self.buffer = self.buffer[end_idx:]
                    # 继续循环尝试解析下一个
                except json.JSONDecodeError:
                    # 解析失败，说明数据不完整，等待更多数据
                    self.buffer = self.buffer[idx:]
                    break
            else:
                # 非预期字符，可能是乱序或错误，跳过当前字符
                idx += 1
                self.buffer = self.buffer[idx:]

        return objects


class AiConfig:
    """AI 助手配置类"""

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: str = "https://ark.cn-beijing.volces.com/api/v3",
        model: str = "ep-20260109153350-7pdqw",
        thinking_enabled: bool = False,
        timeout: int = 600,
    ):
        """
        初始化配置

        Args:
            api_key: API Key，不传则从环境变量 ARK_API_KEY 获取
            base_url: API 基础 URL
            model: 模型名称或推理接入点 ID
            thinking_enabled: 是否启用思考模式
            timeout: 请求超时时间（秒）
        """
        self.api_key = api_key or os.getenv("ARK_API_KEY", "")
        self.base_url = os.getenv("ARK_BASE_URL", base_url)
        self.model = os.getenv("ARK_MODEL", model)
        self.thinking_enabled = thinking_enabled
        self.timeout = int(os.getenv("ARK_TIMEOUT", timeout))

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
                timeout=self.config.timeout,
            )
        return self._client

    def _send_chat_request(
        self,
        messages: List[Dict[str, Any]],
        use_json_schema: bool = True,
        verbose: bool = False,
        stream: bool = False,
    ) -> str:
        """
        发送对话请求（内部方法）- 使用 Chat Completions API

        Args:
            messages: 消息列表，格式为 [{"role": "user", "content": "..."}]
            use_json_schema: 是否使用 JSON Schema 结构化输出
            verbose: 是否输出调试信息
            stream: 是否使用流式输出

        Returns:
            模型响应的文本内容
        """
        if verbose:
            content_len = sum(len(str(m.get("content", ""))) for m in messages)
            print(f"       [DEBUG] 发送请求，消息长度: {content_len} 字符...")

        request_kwargs: Dict[str, Any] = {
            "model": self.config.model,
            "messages": messages,
            "max_tokens": MAX_COMPLETION_TOKENS,
        }

        # 使用 JSON Schema 确保结构化输出
        if use_json_schema:
            request_kwargs["response_format"] = GEO_JSON_SCHEMA
        if stream:
            request_kwargs["stream"] = True

        response = self.client.chat.completions.create(**request_kwargs)

        if stream:
            collected_content = []
            if verbose:
                print("       [DEBUG] 正在接收流式响应...")

            for chunk in response:
                if not chunk.choices:
                    continue
                delta = chunk.choices[0].delta
                if hasattr(delta, "content") and delta.content:
                    content = delta.content
                    collected_content.append(content)
                    if verbose:
                        print(content, end="", flush=True)

            full_content = "".join(collected_content)
            if verbose:
                print("\n       [DEBUG] 流式响应接收完成")
                # print(f"       [DEBUG] 完整内容: {full_content[:100]}...")
            return full_content

        if verbose:
            print(f"       [DEBUG] 收到响应")

        return response.choices[0].message.content

    def chat_once(self, message: str) -> str:
        """
        单次对话，返回纯文本响应

        Args:
            message: 用户消息

        Returns:
            模型响应的文本内容
        """
        messages = [
            {"role": "user", "content": message},
            {"role": "assistant", "content": ""},
        ]
        return self._send_chat_request(messages)

    # ==================== 地理信息提取 ====================

    def extract_geo_info_stream(
        self, text: str, verbose: bool = False
    ) -> Generator[Dict[str, Any], None, None]:
        """
        从文本中流式提取地理信息

        Args:
            text: 施教区描述文本
            verbose: 是否输出调试信息

        Yields:
            解析出的学校对象
        """
        # 强制使用直接发送模式进行流式处理（分段模式比较复杂，暂不支持流式）
        # 如果文本超长，这里可能会有问题，但对于边生成边写，直接发送是最好的
        prompt = GEO_EXTRACTION_PROMPT.replace("{input_text}", text)
        messages = [
            {"role": "user", "content": prompt},
            {"role": "assistant", "content": ""},
        ]

        # 开启 stream
        # 注意：这里我们绕过 _send_chat_request 的一些逻辑，直接调用 client
        if verbose:
            print(f"       [DEBUG] 开始流式提取...")

        request_kwargs: Dict[str, Any] = {
            "model": self.config.model,
            "messages": messages,
            "max_tokens": MAX_COMPLETION_TOKENS,
            "response_format": GEO_JSON_SCHEMA,
            "stream": True,
        }

        response = self.client.chat.completions.create(**request_kwargs)
        parser = StreamJsonParser()

        for chunk in response:
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta
            if hasattr(delta, "content") and delta.content:
                content = delta.content
                if verbose:
                    print(content, end="", flush=True)

                # 解析并 yield
                objects = parser.feed(content)
                for obj in objects:
                    yield obj

        if verbose:
            print("\n")

    def extract_geo_info(self, text: str, verbose: bool = True) -> List[Dict[str, Any]]:
        """
        从文本中提取地理信息

        使用 Chat Completions API + JSON Schema 结构化输出
        256k 长上下文模型，max_tokens=16384

        处理策略:
        - 短文本 (<=200000字符): 直接发送
        - 长文本: 分段处理

        Args:
            text: 施教区描述文本
            verbose: 是否输出处理状态

        Returns:
            结构化的地理信息列表
        """
        text_len = len(text)

        if text_len <= MAX_CHARS_DIRECT:
            if verbose:
                print(f"       [AI] 直接发送模式 ({text_len} 字符)...")
            return self._extract_geo_direct(text, verbose=verbose)
        else:
            if verbose:
                print(f"       [AI] 文本较长 ({text_len} 字符)，使用分段处理...")
            return self._extract_geo_segmented(text, verbose=verbose)

    def _extract_geo_direct(
        self, text: str, verbose: bool = False
    ) -> List[Dict[str, Any]]:
        """直接发送文本提取地理信息 - 使用 Chat Completions API + JSON Schema"""
        prompt = GEO_EXTRACTION_PROMPT.replace("{input_text}", text)
        messages = [
            {"role": "user", "content": prompt},
            {"role": "assistant", "content": ""},
        ]
        # 只有在 verbose 模式下开启 stream
        response = self._send_chat_request(
            messages, use_json_schema=True, verbose=verbose
        )
        return self._parse_json_response(response)

    def _extract_geo_segmented(
        self, text: str, verbose: bool = False
    ) -> List[Dict[str, Any]]:
        """分段处理长文本"""
        segments = self._split_by_school(text)
        all_results = []

        if verbose:
            print(f"       [AI] 分成 {len(segments)} 个段落处理...")

        for i, segment in enumerate(segments, 1):
            try:
                if verbose:
                    print(f"       [AI] 处理段落 {i}/{len(segments)}...")
                results = self._extract_geo_direct(segment, verbose=False)
                all_results.extend(results)
            except Exception as e:
                print(f"       [WARN] 段落 {i} 处理失败: {e}")
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

        处理可能存在的 markdown 代码块包裹和 JSON Schema 格式
        """
        text = response.strip()

        # 尝试提取 markdown 代码块中的 JSON
        json_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
        if json_match:
            text = json_match.group(1)

        # 尝试解析 JSON
        try:
            result = json.loads(text)

            # 处理 JSON Schema 格式: {"schools": [...]}
            if isinstance(result, dict) and "schools" in result:
                return result["schools"]

            # 确保返回的是列表
            if isinstance(result, dict):
                return [result]
            return result
        except json.JSONDecodeError as e:
            # 尝试从截断的 JSON 中提取已完成的学校对象
            print(f"       [WARN] JSON 解析失败 ({e})，尝试提取已生成的片段...")
            try:
                extracted = self._extract_valid_objects(text)
                if extracted:
                    print(f"       [INFO] 成功恢复 {len(extracted)} 个学校数据")
                    return extracted
            except Exception as extract_error:
                print(f"       [WARN] 提取片段失败: {extract_error}")

            raise LLMParseError(f"无法解析 LLM 返回的 JSON: {e}", response)

    def stream_extract_geo_info(
        self, text: str, verbose: bool = False
    ) -> Generator[Dict[str, Any], None, None]:
        """
        流式提取地理信息（生成器模式）

        实时解析 LLM 的流式输出，每生成一个完整的学校对象就 yield 一次。
        适合处理超长文本或避免超时丢失数据。
        """
        prompt = GEO_EXTRACTION_PROMPT.replace("{input_text}", text)
        messages = [
            {"role": "user", "content": prompt},
            {"role": "assistant", "content": ""},
        ]

        # 强制开启 API 流式
        request_kwargs = {
            "model": self.config.model,
            "messages": messages,
            "max_tokens": MAX_COMPLETION_TOKENS,
            "stream": True,
        }
        if True:  # 始终使用 JSON Schema
            request_kwargs["response_format"] = GEO_JSON_SCHEMA

        if verbose:
            print(f"       [DEBUG] 发送流式请求...")

        response_stream = self.client.chat.completions.create(**request_kwargs)

        buffer = ""
        decoder = json.JSONDecoder()

        for chunk in response_stream:
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta.content
            if not delta:
                continue

            buffer += delta
            if verbose:
                # 简单打印进度点，避免刷屏
                print(".", end="", flush=True)

            # 尝试从 buffer 中解析完整的 JSON 对象
            while True:
                start_idx = buffer.find("{")
                if start_idx == -1:
                    # 没有对象开始符，保留 buffer 继续接收
                    break

                try:
                    obj, end_idx = decoder.raw_decode(buffer, start_idx)

                    # 校验是否是我们需要的学校对象
                    if isinstance(obj, dict) and "school_name" in obj:
                        yield obj
                        # 解析成功，移除已解析部分
                        buffer = buffer[end_idx:]
                    else:
                        # 跳过非目标对象（如 root 对象片段）
                        buffer = buffer[start_idx + 1 :]

                except json.JSONDecodeError:
                    # 解析失败，等待更多数据
                    break

        if verbose:
            print()  # 换行

    def _extract_valid_objects(self, text: str) -> List[Dict[str, Any]]:
        """尝试从不完整的 JSON 中提取有效的学校对象"""
        objects = []
        decoder = json.JSONDecoder()

        # 寻找数组开始
        # 可能是 {"schools": [ ... 或直接 [ ...
        start_idx = text.find("[")
        if start_idx == -1:
            return []

        idx = start_idx + 1

        while idx < len(text):
            # 跳过空白和逗号
            while idx < len(text) and text[idx] in " \t\n\r,":
                idx += 1

            if idx >= len(text):
                break

            if text[idx] == "{":
                try:
                    obj, end_idx = decoder.raw_decode(text, idx)
                    if isinstance(obj, dict) and "school_name" in obj:
                        objects.append(obj)
                    idx = end_idx
                except json.JSONDecodeError:
                    # 解析当前对象失败，说明可能被截断，停止
                    break
            elif text[idx] == "]":
                # 数组结束
                break
            else:
                # 其他字符，可能是截断导致的乱序，停止
                break

        return objects
