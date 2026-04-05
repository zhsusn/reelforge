"""
DeepSeek Client 模块接口定义 (Type Spec)
版本：v1.0（已冻结）
项目：ReelForge
文件映射：`services/deepseek_client.py`

职责：DeepSeek API 客户端、流式响应、重试逻辑
依赖：httpx, tenacity

状态：🔒 LOCKED (冻结)
锁定日期：2026-04-03
锁定原因：接口定义完整，类型正确，通过Python语法检查
验证状态：✅ 语法检查通过 (python -m py_compile)

重要：此文件为冻结接口定义，不可修改。如需变更请创建RFC文档。
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Tuple
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

# =============================================================================
# 数据模型定义
# =============================================================================

@dataclass
class ShotDescription:
    """分镜描述数据模型"""
    sequence: int                   # 序号
    scene_description: str          # 画面描述（用于生图）
    dialogue: str                   # 台词
    emotion: str                    # 情绪
    camera_movement: str            # 运镜建议（推/拉/摇/移）
    shot_type: str                  # 景别（特写/中景/全景）

@dataclass
class Storyboard:
    """故事板数据模型"""
    shots: List[ShotDescription]    # 分镜列表
    total_duration: float           # 预估总时长（秒）

# =============================================================================
# 异常定义
# =============================================================================

class APIError(Exception):
    """API调用失败异常（4xx/5xx错误）"""
    def __init__(self, message: str, status_code: Optional[int] = None,
                 response_data: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.response_data = response_data

class RateLimitError(APIError):
    """触发速率限制异常（429）"""
    pass

class TimeoutError(APIError):
    """请求超时异常（默认60s）"""
    pass

class ParseError(APIError):
    """响应解析失败异常（JSON格式错误）"""
    pass

# =============================================================================
# 主类接口
# =============================================================================

class DeepSeekClient:
    """
    DeepSeek API 客户端

    职责：
        1. 调用DeepSeek API生成故事板
        2. 实现重试逻辑（tenacity装饰器）
        3. 支持流式响应
        4. API密钥验证

    约束：
        - 所有API调用方法必须有@retry装饰器
        - 默认超时：60秒
        - 重试策略：最大3次，指数退避
    """

    def __init__(self, api_key: str, base_url: str = "https://api.deepseek.com") -> None:
        """
        初始化DeepSeek客户端

        Args:
            api_key: DeepSeek API密钥
            base_url: API基础URL
        """
        raise NotImplementedError

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=8),
        retry=retry_if_exception_type((APIError, TimeoutError))
    )
    def generate_storyboard(self, script: str, roles: List[str]) -> Storyboard:
        """
        生成故事板（分镜列表）

        Args:
            script: 剧本全文
            roles: 角色列表

        Returns:
            Storyboard: 生成的故事板对象

        Raises:
            APIError: API调用失败
            RateLimitError: 触发速率限制
            TimeoutError: 请求超时
            ParseError: 响应解析失败
        """
        raise NotImplementedError

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=8),
        retry=retry_if_exception_type((APIError, TimeoutError))
    )
    def stream_generate(self, script: str) -> Iterator[str]:
        """
        流式生成（返回文本chunks迭代器）

        Args:
            script: 剧本全文

        Yields:
            str: 生成的文本chunks

        Raises:
            APIError: API调用失败
            TimeoutError: 请求超时
        """
        raise NotImplementedError

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=8),
        retry=retry_if_exception_type((APIError, TimeoutError))
    )
    def validate_key(self, api_key: str) -> Tuple[bool, str]:
        """
        验证API密钥有效性

        Args:
            api_key: 要验证的API密钥

        Returns:
            Tuple[bool, str]: (是否有效, 余额信息或错误消息)
        """
        raise NotImplementedError

    def get_usage(self) -> Dict[str, Any]:
        """
        获取API使用情况

        Returns:
            Dict[str, Any]: 使用情况信息，包含tokens_used, tokens_remaining等
        """
        raise NotImplementedError

    @property
    def api_key(self) -> str:
        """获取API密钥（隐藏部分字符）"""
        raise NotImplementedError

    @property
    def base_url(self) -> str:
        """获取API基础URL"""
        raise NotImplementedError

# =============================================================================
# 导出列表
# =============================================================================

__all__ = [
    # 数据模型
    "ShotDescription",
    "Storyboard",
    # 异常
    "APIError",
    "RateLimitError",
    "TimeoutError",
    "ParseError",
    # 主类
    "DeepSeekClient",
]