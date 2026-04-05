"""
API Quotas 模块接口定义 (Type Spec)
版本：v1.0（草案）
项目：ReelForge
文件映射：`models/api_quotas.py`

职责：API配额数据的创建、读取、更新、删除操作，配额使用跟踪，重置管理
依赖：src/reelforge/models/database/ (Database, DatabaseError等)

状态：📝 DRAFT (草案)
创建日期：2026-04-03
锁定状态：待审核确认

重要：此文件为接口定义草案，需通过mypy严格检查后锁定。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, Union

from reelforge.models.database import Database, DatabaseError, QueryResult


# =============================================================================
# 数据模型定义
# =============================================================================

class ServiceName(str, Enum):
    """服务名称枚举"""
    DEEPSEEK = "deepseek"
    TONGYI = "tongyi"
    EDGE_TTS = "edge_tts"


@dataclass
class ApiQuota:
    """API配额数据模型

    对应数据库表：api_quotas
    字段映射：
        id -> quota_id
        service_name -> service_name (ServiceName)
        quota_total -> total_quota
        quota_used -> used_quota
        quota_reset_date -> reset_date (date)
        api_key -> api_key (可选，加密存储)
        endpoint_url -> endpoint_url (可选)
        is_enabled -> is_enabled (bool)
        created_at -> created_at (datetime)
        updated_at -> updated_at (datetime)
    """

    quota_id: int
    service_name: ServiceName
    total_quota: int
    used_quota: int
    reset_date: date
    api_key: Optional[str]  # 加密存储
    endpoint_url: Optional[str]
    is_enabled: bool
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_row(cls, row: Dict[str, Any]) -> ApiQuota:
        """从数据库行创建ApiQuota对象"""
        return cls(
            quota_id=row["id"],
            service_name=ServiceName(row["service_name"]),
            total_quota=row["quota_total"],
            used_quota=row["quota_used"],
            reset_date=date.fromisoformat(row["quota_reset_date"]),
            api_key=row["api_key"],
            endpoint_url=row["endpoint_url"],
            is_enabled=bool(row["is_enabled"]),
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )

    @property
    def remaining_quota(self) -> int:
        """获取剩余配额"""
        return max(0, self.total_quota - self.used_quota)

    @property
    def usage_percentage(self) -> float:
        """获取使用百分比"""
        if self.total_quota == 0:
            return 0.0
        return (self.used_quota / self.total_quota) * 100

    @property
    def is_exhausted(self) -> bool:
        """检查配额是否已耗尽"""
        return self.remaining_quota <= 0

    @property
    def is_reset_needed(self) -> bool:
        """检查是否需要重置（重置日期已过）"""
        return date.today() >= self.reset_date


@dataclass
class ApiQuotaCreate:
    """创建API配额时的数据模型（输入）"""
    service_name: ServiceName
    total_quota: int
    reset_date: date
    api_key: Optional[str] = None
    endpoint_url: Optional[str] = None
    is_enabled: bool = True


@dataclass
class ApiQuotaUpdate:
    """更新API配额时的数据模型（输入）"""
    total_quota: Optional[int] = None
    used_quota: Optional[int] = None
    reset_date: Optional[date] = None
    api_key: Optional[str] = None
    endpoint_url: Optional[str] = None
    is_enabled: Optional[bool] = None


@dataclass
class QuotaUsage:
    """配额使用统计"""
    service_name: ServiceName
    total_quota: int
    used_quota: int
    remaining_quota: int
    usage_percentage: float
    is_exhausted: bool
    is_enabled: bool
    reset_date: date
    days_until_reset: int  # 距离重置的天数


@dataclass
class QuotaReservation:
    """配额预扣记录"""
    reservation_id: str
    service_name: ServiceName
    amount: int
    purpose: str
    expires_at: datetime
    is_committed: bool = False


# =============================================================================
# 异常定义
# =============================================================================

class ApiQuotaError(DatabaseError):
    """API配额操作基础异常"""
    pass


class QuotaNotFoundError(ApiQuotaError):
    """配额未找到异常"""
    pass


class QuotaExhaustedError(ApiQuotaError):
    """配额已耗尽异常"""
    pass


class InvalidQuotaAmountError(ApiQuotaError):
    """配额金额无效异常（负数或超出范围）"""
    pass


class ServiceDisabledError(ApiQuotaError):
    """服务已禁用异常"""
    pass


class QuotaResetError(ApiQuotaError):
    """配额重置异常"""
    pass


class ReservationNotFoundError(ApiQuotaError):
    """预扣记录未找到异常"""
    pass


# =============================================================================
# 主类接口实现
# =============================================================================

class ApiQuotaManager:
    """API配额管理器（CRUD操作）

    职责：
        1. API配额创建、读取、更新、删除
        2. 配额使用跟踪和扣减
        3. 配额预扣和提交机制
        4. 定期配额重置
        5. 服务启用/禁用管理
        6. API密钥加密存储
    """

    def __init__(self, database: Database) -> None:
        """
        初始化API配额管理器

        Args:
            database: 数据库实例
        """
        raise NotImplementedError

    # =========================================================================
    # 基本CRUD操作
    # =========================================================================

    def create(self, quota_data: ApiQuotaCreate) -> ApiQuota:
        """
        创建新API配额

        Args:
            quota_data: 配额创建数据

        Returns:
            ApiQuota: 创建的配额对象

        Raises:
            ApiQuotaError: 创建失败
            InvalidQuotaAmountError: 配额金额无效
        """
        raise NotImplementedError

    def get_by_service(self, service_name: ServiceName) -> ApiQuota:
        """
        根据服务名称获取API配额

        Args:
            service_name: 服务名称

        Returns:
            ApiQuota: 配额对象

        Raises:
            QuotaNotFoundError: 配额不存在
            ApiQuotaError: 查询失败
        """
        raise NotImplementedError

    def get_by_id(self, quota_id: int) -> ApiQuota:
        """
        根据ID获取API配额

        Args:
            quota_id: 配额ID

        Returns:
            ApiQuota: 配额对象

        Raises:
            QuotaNotFoundError: 配额不存在
            ApiQuotaError: 查询失败
        """
        raise NotImplementedError

    def update(self, service_name: ServiceName, update_data: ApiQuotaUpdate) -> ApiQuota:
        """
        更新API配额信息

        Args:
            service_name: 服务名称
            update_data: 更新数据

        Returns:
            ApiQuota: 更新后的配额对象

        Raises:
            QuotaNotFoundError: 配额不存在
            InvalidQuotaAmountError: 配额金额无效
            ApiQuotaError: 更新失败
        """
        raise NotImplementedError

    def delete(self, service_name: ServiceName) -> bool:
        """
        删除API配额

        Args:
            service_name: 服务名称

        Returns:
            bool: 删除是否成功

        Raises:
            QuotaNotFoundError: 配额不存在
            ApiQuotaError: 删除失败
        """
        raise NotImplementedError

    # =========================================================================
    # 配额使用管理
    # =========================================================================

    def use_quota(
        self,
        service_name: ServiceName,
        amount: int,
        purpose: str = "api_call",
        require_commit: bool = False,
    ) -> bool:
        """
        使用配额（直接扣减）

        Args:
            service_name: 服务名称
            amount: 使用量
            purpose: 使用目的（用于日志）
            require_commit: 是否需要提交确认

        Returns:
            bool: 使用是否成功

        Raises:
            QuotaNotFoundError: 配额不存在
            QuotaExhaustedError: 配额不足
            ServiceDisabledError: 服务已禁用
            InvalidQuotaAmountError: 使用量无效
            ApiQuotaError: 使用失败
        """
        raise NotImplementedError

    def reserve_quota(
        self,
        service_name: ServiceName,
        amount: int,
        purpose: str,
        expiration_minutes: int = 30,
    ) -> QuotaReservation:
        """
        预扣配额（临时保留，避免并发使用超限）

        Args:
            service_name: 服务名称
            amount: 预扣量
            purpose: 预扣目的
            expiration_minutes: 预扣过期时间（分钟）

        Returns:
            QuotaReservation: 预扣记录

        Raises:
            QuotaNotFoundError: 配额不存在
            QuotaExhaustedError: 配额不足
            ServiceDisabledError: 服务已禁用
            InvalidQuotaAmountError: 预扣量无效
            ApiQuotaError: 预扣失败
        """
        raise NotImplementedError

    def commit_reservation(self, reservation_id: str) -> bool:
        """
        提交预扣配额（实际扣减）

        Args:
            reservation_id: 预扣记录ID

        Returns:
            bool: 提交是否成功

        Raises:
            ReservationNotFoundError: 预扣记录不存在
            ReservationExpiredError: 预扣已过期
            ApiQuotaError: 提交失败
        """
        raise NotImplementedError

    def cancel_reservation(self, reservation_id: str) -> bool:
        """
        取消预扣配额（释放预扣）

        Args:
            reservation_id: 预扣记录ID

        Returns:
            bool: 取消是否成功

        Raises:
            ReservationNotFoundError: 预扣记录不存在
            ReservationExpiredError: 预扣已过期
            ApiQuotaError: 取消失败
        """
        raise NotImplementedError

    def can_use_quota(self, service_name: ServiceName, amount: int) -> bool:
        """
        检查是否可以使用的配额

        Args:
            service_name: 服务名称
            amount: 使用量

        Returns:
            bool: 是否可以使用

        Raises:
            QuotaNotFoundError: 配额不存在
            ServiceDisabledError: 服务已禁用
        """
        raise NotImplementedError

    def get_quota_usage(self, service_name: ServiceName) -> QuotaUsage:
        """
        获取配额使用统计

        Args:
            service_name: 服务名称

        Returns:
            QuotaUsage: 配额使用统计

        Raises:
            QuotaNotFoundError: 配额不存在
        """
        raise NotImplementedError

    # =========================================================================
    # 配额重置管理
    # =========================================================================

    def reset_quota(self, service_name: ServiceName, new_total: Optional[int] = None) -> ApiQuota:
        """
        重置配额（重置日期已到时调用）

        Args:
            service_name: 服务名称
            new_total: 新总配额（可选，不指定则保持不变）

        Returns:
            ApiQuota: 重置后的配额对象

        Raises:
            QuotaNotFoundError: 配额不存在
            QuotaResetError: 重置失败
            ApiQuotaError: 操作失败
        """
        raise NotImplementedError

    def auto_reset_expired_quotas(self) -> Dict[str, bool]:
        """
        自动重置所有到期的配额

        Returns:
            Dict[str, bool]: 重置结果字典（服务名称 -> 是否成功）
        """
        raise NotImplementedError

    def set_reset_date(self, service_name: ServiceName, reset_date: date) -> ApiQuota:
        """
        设置配额重置日期

        Args:
            service_name: 服务名称
            reset_date: 重置日期

        Returns:
            ApiQuota: 更新后的配额对象

        Raises:
            QuotaNotFoundError: 配额不存在
            ApiQuotaError: 设置失败
        """
        raise NotImplementedError

    # =========================================================================
    # 服务状态管理
    # =========================================================================

    def enable_service(self, service_name: ServiceName) -> ApiQuota:
        """
        启用服务

        Args:
            service_name: 服务名称

        Returns:
            ApiQuota: 更新后的配额对象

        Raises:
            QuotaNotFoundError: 配额不存在
            ApiQuotaError: 启用失败
        """
        raise NotImplementedError

    def disable_service(self, service_name: ServiceName) -> ApiQuota:
        """
        禁用服务

        Args:
            service_name: 服务名称

        Returns:
            ApiQuota: 更新后的配额对象

        Raises:
            QuotaNotFoundError: 配额不存在
            ApiQuotaError: 禁用失败
        """
        raise NotImplementedError

    def is_service_enabled(self, service_name: ServiceName) -> bool:
        """
        检查服务是否启用

        Args:
            service_name: 服务名称

        Returns:
            bool: 服务是否启用

        Raises:
            QuotaNotFoundError: 配额不存在
        """
        raise NotImplementedError

    # =========================================================================
    # API密钥管理
    # =========================================================================

    def update_api_key(self, service_name: ServiceName, api_key: str) -> ApiQuota:
        """
        更新API密钥（加密存储）

        Args:
            service_name: 服务名称
            api_key: API密钥

        Returns:
            ApiQuota: 更新后的配额对象

        Raises:
            QuotaNotFoundError: 配额不存在
            ApiQuotaError: 更新失败
        """
        raise NotImplementedError

    def clear_api_key(self, service_name: ServiceName) -> ApiQuota:
        """
        清除API密钥

        Args:
            service_name: 服务名称

        Returns:
            ApiQuota: 更新后的配额对象

        Raises:
            QuotaNotFoundError: 配额不存在
            ApiQuotaError: 清除失败
        """
        raise NotImplementedError

    def has_api_key(self, service_name: ServiceName) -> bool:
        """
        检查是否有API密钥

        Args:
            service_name: 服务名称

        Returns:
            bool: 是否有API密钥

        Raises:
            QuotaNotFoundError: 配额不存在
        """
        raise NotImplementedError

    # =========================================================================
    # 查询和列表操作
    # =========================================================================

    def list_all(
        self,
        is_enabled: Optional[bool] = None,
        limit: int = 100,
        offset: int = 0,
        order_by_service: bool = True,
    ) -> List[ApiQuota]:
        """
        列出所有API配额

        Args:
            is_enabled: 按启用状态过滤（可选）
            limit: 返回数量限制
            offset: 偏移量
            order_by_service: 是否按服务名称排序

        Returns:
            List[ApiQuota]: 配额列表
        """
        raise NotImplementedError

    def list_usage_all(self) -> List[QuotaUsage]:
        """
        列出所有配额的详细使用统计

        Returns:
            List[QuotaUsage]: 配额使用统计列表
        """
        raise NotImplementedError

    def count(self, is_enabled: Optional[bool] = None) -> int:
        """
        统计配额数量

        Args:
            is_enabled: 按启用状态过滤（可选）

        Returns:
            int: 配额数量
        """
        raise NotImplementedError

    def get_services_needing_reset(self) -> List[ServiceName]:
        """
        获取需要重置的服务列表（重置日期已过）

        Returns:
            List[ServiceName]: 需要重置的服务列表
        """
        raise NotImplementedError

    def get_low_quota_services(self, threshold_percentage: float = 80.0) -> List[QuotaUsage]:
        """
        获取低配额服务列表（使用率超过阈值）

        Args:
            threshold_percentage: 阈值百分比（默认80%）

        Returns:
            List[QuotaUsage]: 低配额服务列表
        """
        raise NotImplementedError

    # =========================================================================
    # 批量操作
    # =========================================================================

    def batch_create(self, quotas_data: List[ApiQuotaCreate]) -> List[ApiQuota]:
        """
        批量创建配额

        Args:
            quotas_data: 配额创建数据列表

        Returns:
            List[ApiQuota]: 创建的配额列表

        Raises:
            ApiQuotaError: 批量创建失败
        """
        raise NotImplementedError

    def batch_reset(self, service_names: List[ServiceName]) -> Dict[str, bool]:
        """
        批量重置配额

        Args:
            service_names: 服务名称列表

        Returns:
            Dict[str, bool]: 重置结果字典（服务名称 -> 是否成功）
        """
        raise NotImplementedError

    # =========================================================================
    # 统计和报表
    # =========================================================================

    def get_statistics(self) -> Dict[str, Any]:
        """
        获取配额统计信息

        Returns:
            Dict[str, Any]: 统计信息
        """
        raise NotImplementedError

    def get_usage_summary(self) -> Dict[str, Any]:
        """
        获取配额使用摘要

        Returns:
            Dict[str, Any]: 使用摘要
        """
        raise NotImplementedError

    def get_daily_usage_trend(
        self,
        service_name: ServiceName,
        days: int = 30,
    ) -> List[Dict[str, Any]]:
        """
        获取每日使用趋势

        Args:
            service_name: 服务名称
            days: 天数（默认30天）

        Returns:
            List[Dict[str, Any]]: 每日使用趋势数据
        """
        raise NotImplementedError

    # =========================================================================
    # 辅助方法
    # =========================================================================

    def _get_last_insert_id(self) -> int:
        """获取最后插入的ID"""
        raise NotImplementedError

    def _encrypt_api_key(self, api_key: str) -> str:
        """加密API密钥"""
        raise NotImplementedError

    def _decrypt_api_key(self, encrypted_key: str) -> str:
        """解密API密钥"""
        raise NotImplementedError

    def _generate_reservation_id(self) -> str:
        """生成预扣记录ID"""
        raise NotImplementedError

    def _validate_quota_amount(self, amount: int) -> bool:
        """验证配额金额（非负整数）"""
        raise NotImplementedError

    def _calculate_days_until_reset(self, reset_date: date) -> int:
        """计算距离重置的天数"""
        raise NotImplementedError


# =============================================================================
# 导出列表
# =============================================================================

__all__ = [
    # 数据模型
    "ApiQuota",
    "ApiQuotaCreate",
    "ApiQuotaUpdate",
    "QuotaUsage",
    "QuotaReservation",
    # 枚举
    "ServiceName",
    # 异常
    "ApiQuotaError",
    "QuotaNotFoundError",
    "QuotaExhaustedError",
    "InvalidQuotaAmountError",
    "ServiceDisabledError",
    "QuotaResetError",
    "ReservationNotFoundError",
    # 主类
    "ApiQuotaManager",
]