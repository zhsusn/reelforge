"""
Tongyi Client 模块接口定义 (Type Spec)
版本：v1.0（草案）
项目：ReelForge
文件映射：`services/tongyi_client.py`

职责：通义万相首帧锁定 API 客户端
约束：必须包含降级策略标记

状态：Generated（未冻结）
确认方式：运行 mypy 检查，然后可冻结为 tongyi_client-interface.v1.locked.py
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

# =============================================================================
# 异常定义
# =============================================================================

class APIError(Exception):
    """API调用失败异常"""
    def __init__(self, message: str, status_code: Optional[int] = None,
                 response_data: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.response_data = response_data

class CharacterMismatchError(APIError):
    """生成图片与首帧角色不一致异常（相似度<90%）"""
    pass

class FaceDetectionError(APIError):
    """无法检测人脸异常（首帧图片质量问题）"""
    pass

class QuotaExceededError(APIError):
    """当日积分耗尽异常"""
    pass

# =============================================================================
# 主类接口
# =============================================================================

class TongyiClient:
    """
    通义万相 API 客户端（首帧锁定）

    职责：
        1. 首帧锁定图像生成
        2. 角色一致性验证（相似度计算）
        3. 降级策略实现
        4. 配额管理

    约束：
        - 首帧锁定代码必须包含 `# TODO: 降级策略` 标记
        - 相似度阈值：90%（低于此值触发CharacterMismatchError）
    """

    def __init__(self, api_key: str, base_url: str = "https://dashscope.aliyuncs.com") -> None:
        """
        初始化通义万相客户端

        Args:
            api_key: 通义万相 API密钥
            base_url: API基础URL
        """
        raise NotImplementedError

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=8),
        retry=retry_if_exception_type((APIError, CharacterMismatchError))
    )
    def generate_with_first_frame(self, prompt: str, first_frame_path: Path) -> Path:
        """
        使用首帧锁定生成图片

        Args:
            prompt: 提示词（画面描述）
            first_frame_path: 首帧图片路径

        Returns:
            Path: 生成的图片路径

        Raises:
            APIError: API调用失败
            CharacterMismatchError: 生成图片与首帧角色不一致（相似度<90%）
            FaceDetectionError: 无法检测人脸（首帧图片质量问题）
            QuotaExceededError: 当日积分耗尽

        Note:
            必须包含降级策略标记：`# TODO: 降级策略`
        """
        raise NotImplementedError

    def validate_character_consistency(self, images: List[Path]) -> float:
        """
        验证角色一致性（计算相似度分数）

        Args:
            images: 图片路径列表

        Returns:
            float: 相似度分数（0-100），越高表示一致性越好

        Raises:
            FaceDetectionError: 无法检测人脸（图片质量问题）
        """
        raise NotImplementedError

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=8),
        retry=retry_if_exception_type((APIError,))
    )
    def get_quota_remaining(self) -> int:
        """
        获取剩余积分

        Returns:
            int: 剩余积分

        Raises:
            APIError: API调用失败
        """
        raise NotImplementedError

    # TODO: 降级策略 - 生成降级方法
    def generate_with_style_fallback(self, prompt: str, style_description: str) -> Path:
        """
        风格描述降级生成（当首帧锁定失败时使用）

        Args:
            prompt: 提示词
            style_description: 风格描述（如：动漫风格、写实风格）

        Returns:
            Path: 生成的图片路径
        """
        raise NotImplementedError

    def get_model_info(self) -> Dict[str, Any]:
        """
        获取模型信息

        Returns:
            Dict[str, Any]: 模型信息
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

    @property
    def similarity_threshold(self) -> float:
        """获取相似度阈值"""
        raise NotImplementedError

# =============================================================================
# 导出列表
# =============================================================================

__all__ = [
    # 异常
    "APIError",
    "CharacterMismatchError",
    "FaceDetectionError",
    "QuotaExceededError",
    # 主类
    "TongyiClient",
]