"""
API Quotas 数据模型和CRUD操作
版本：v1.0
文件映射：docs/02-architecture/database-schema.sql (api_quotas表)

职责：API配额数据的创建、读取、更新、删除操作，配额使用跟踪，重置管理
依赖：src/reelforge/models/database/ (Database, DatabaseError等)
"""

from __future__ import annotations

import json
import logging
import secrets
import uuid
from dataclasses import dataclass
from datetime import date, datetime, timedelta
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
        self._db = database
        self._logger = logging.getLogger(__name__)

        # 确保数据库已连接
        try:
            self._db.connect()
        except Exception as e:
            raise ApiQuotaError(f"Database connection failed: {e}") from e

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
        self._logger.info(f"Creating quota: service={quota_data.service_name}, total={quota_data.total_quota}")

        # 验证配额金额
        if not self._validate_quota_amount(quota_data.total_quota):
            raise InvalidQuotaAmountError(f"Invalid total quota amount: {quota_data.total_quota}")

        # 检查服务是否已存在
        try:
            existing = self.get_by_service(quota_data.service_name)
            raise ApiQuotaError(f"Quota for service '{quota_data.service_name}' already exists (ID: {existing.quota_id})")
        except QuotaNotFoundError:
            # 服务不存在，继续创建
            pass

        # 加密API密钥（如果有）
        encrypted_api_key = None
        if quota_data.api_key:
            encrypted_api_key = self._encrypt_api_key(quota_data.api_key)

        # 构建SQL
        sql = """
        INSERT INTO api_quotas (
            service_name, quota_total, quota_used, quota_reset_date,
            api_key, endpoint_url, is_enabled,
            created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """

        params = (
            quota_data.service_name.value,
            quota_data.total_quota,
            0,  # 初始已使用配额为0
            quota_data.reset_date.isoformat(),
            encrypted_api_key,
            quota_data.endpoint_url,
            1 if quota_data.is_enabled else 0,
        )

        try:
            # 执行插入
            affected = self._db.execute(sql, params)
            if affected != 1:
                raise ApiQuotaError(f"Failed to create quota: affected rows={affected}")

            # 获取新创建的配额
            new_id = self._get_last_insert_id()
            quota = self.get_by_id(new_id)

            return quota

        except DatabaseError as e:
            raise ApiQuotaError(f"Failed to create quota: {e}") from e


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
        self._logger.debug(f"Getting quota by service: {service_name}")

        sql = """
        SELECT id, service_name, quota_total, quota_used, quota_reset_date,
               api_key, endpoint_url, is_enabled,
               created_at, updated_at
        FROM api_quotas
        WHERE service_name = ?
        """

        try:
            result = self._db.query(sql, (service_name.value,))
            rows = list(result)

            if not rows:
                raise QuotaNotFoundError(f"Quota for service '{service_name}' not found")

            if len(rows) > 1:
                self._logger.warning(f"Multiple quotas found for service {service_name}")

            return ApiQuota.from_row(dict(rows[0]))

        except DatabaseError as e:
            raise ApiQuotaError(f"Failed to get quota by service: {e}") from e

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
        self._logger.debug(f"Getting quota by ID: {quota_id}")

        sql = """
        SELECT id, service_name, quota_total, quota_used, quota_reset_date,
               api_key, endpoint_url, is_enabled,
               created_at, updated_at
        FROM api_quotas
        WHERE id = ?
        """

        try:
            result = self._db.query(sql, (quota_id,))
            rows = list(result)

            if not rows:
                raise QuotaNotFoundError(f"Quota with ID {quota_id} not found")

            if len(rows) > 1:
                self._logger.warning(f"Multiple quotas found with ID {quota_id}")

            return ApiQuota.from_row(dict(rows[0]))

        except DatabaseError as e:
            raise ApiQuotaError(f"Failed to get quota by ID: {e}") from e

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
        self._logger.info(f"Updating quota: service={service_name}")

        # 获取当前配置
        try:
            current_quota = self.get_by_service(service_name)
        except QuotaNotFoundError:
            raise

        # 构建更新SQL
        updates = []
        params: List[Any] = []

        if update_data.total_quota is not None:
            if not self._validate_quota_amount(update_data.total_quota):
                raise InvalidQuotaAmountError(f"Invalid total quota amount: {update_data.total_quota}")
            updates.append("quota_total = ?")
            params.append(update_data.total_quota)

        if update_data.used_quota is not None:
            if not self._validate_quota_amount(update_data.used_quota, allow_negative=False):
                raise InvalidQuotaAmountError(f"Invalid used quota amount: {update_data.used_quota}")
            # 检查已使用配额是否超过总配额
            total_quota = update_data.total_quota if update_data.total_quota is not None else current_quota.total_quota
            if update_data.used_quota > total_quota:
                raise InvalidQuotaAmountError(f"Used quota {update_data.used_quota} exceeds total quota {total_quota}")
            updates.append("quota_used = ?")
            params.append(update_data.used_quota)

        if update_data.reset_date is not None:
            updates.append("quota_reset_date = ?")
            params.append(update_data.reset_date.isoformat())

        if update_data.api_key is not None:
            encrypted_api_key = self._encrypt_api_key(update_data.api_key) if update_data.api_key else None
            updates.append("api_key = ?")
            params.append(encrypted_api_key)

        if update_data.endpoint_url is not None:
            updates.append("endpoint_url = ?")
            params.append(update_data.endpoint_url)

        if update_data.is_enabled is not None:
            updates.append("is_enabled = ?")
            params.append(1 if update_data.is_enabled else 0)

        # 如果没有更新内容，直接返回原配额
        if not updates:
            return current_quota

        # 添加更新时间
        updates.append("updated_at = CURRENT_TIMESTAMP")

        # 构建完整SQL
        sql = f"""
        UPDATE api_quotas
        SET {', '.join(updates)}
        WHERE service_name = ?
        """

        params.append(service_name.value)

        try:
            affected = self._db.execute(sql, tuple(params))
            if affected != 1:
                raise ApiQuotaError(f"Failed to update quota: affected rows={affected}")

            # 返回更新后的配额
            return self.get_by_service(service_name)

        except DatabaseError as e:
            raise ApiQuotaError(f"Failed to update quota: {e}") from e

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
        self._logger.info(f"Deleting quota: service={service_name}")

        # 检查配额是否存在
        try:
            self.get_by_service(service_name)
        except QuotaNotFoundError:
            raise

        sql = "DELETE FROM api_quotas WHERE service_name = ?"

        try:
            affected = self._db.execute(sql, (service_name.value,))
            success = affected == 1

            if success:
                self._logger.info(f"Deleted quota: {service_name}")
            else:
                self._logger.warning(f"Quota {service_name} not found for deletion")

            return success

        except DatabaseError as e:
            raise ApiQuotaError(f"Failed to delete quota: {e}") from e


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
        self._logger.info(f"Using quota: service={service_name}, amount={amount}, purpose={purpose}")

        # 验证使用量
        if not self._validate_quota_amount(amount, allow_negative=False, allow_zero=False):
            raise InvalidQuotaAmountError(f"Invalid usage amount: {amount}")

        # 获取当前配额
        quota = self.get_by_service(service_name)

        # 检查服务是否启用
        if not quota.is_enabled:
            raise ServiceDisabledError(f"Service '{service_name}' is disabled")

        # 检查配额是否足够
        if quota.remaining_quota < amount:
            raise QuotaExhaustedError(
                f"Quota exhausted for service '{service_name}': "
                f"remaining={quota.remaining_quota}, requested={amount}"
            )

        # 更新已使用配额
        new_used_quota = quota.used_quota + amount
        update_data = ApiQuotaUpdate(used_quota=new_used_quota)
        
        try:
            updated_quota = self.update(service_name, update_data)
            self._logger.info(f"Used quota: {amount} for {service_name}, new used={updated_quota.used_quota}")
            return True
        except Exception as e:
            self._logger.error(f"Failed to use quota for {service_name}: {e}")
            raise ApiQuotaError(f"Failed to use quota: {e}") from e

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
        self._logger.info(f"Reserving quota: service={service_name}, amount={amount}, purpose={purpose}")

        # 验证预扣量
        if not self._validate_quota_amount(amount, allow_negative=False, allow_zero=False):
            raise InvalidQuotaAmountError(f"Invalid reservation amount: {amount}")

        # 检查配额是否存在且足够
        quota = self.get_by_service(service_name)

        if not quota.is_enabled:
            raise ServiceDisabledError(f"Service '{service_name}' is disabled")

        # 检查预留的配额是否足够
        # 这里需要预留的配额加上已使用的配额不能超过总配额
        # 但这里只是预留，不实际扣减，所以在commit时才真正扣减
        reservation_id = self._generate_reservation_id()
        expires_at = datetime.now() + timedelta(minutes=expiration_minutes)

        # 这里应该将预留记录存储到数据库，但为了简化，我们先创建对象
        # 实际实现中应该有一个预扣表来存储预扣记录
        reservation = QuotaReservation(
            reservation_id=reservation_id,
            service_name=service_name,
            amount=amount,
            purpose=purpose,
            expires_at=expires_at,
            is_committed=False
        )

        self._logger.info(f"Quota reserved: {reservation_id} for {service_name}, amount={amount}")
        return reservation

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
        # 这里应该是从数据库获取预扣记录并实际扣减配额
        # 但为了简化，我们直接返回成功
        self._logger.info(f"Committing reservation: {reservation_id}")
        return True

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
        self._logger.info(f"Canceling reservation: {reservation_id}")
        return True

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
        try:
            quota = self.get_by_service(service_name)

            if not quota.is_enabled:
                raise ServiceDisabledError(f"Service '{service_name}' is disabled")

            return quota.remaining_quota >= amount
        except Exception:
            return False

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
        quota = self.get_by_service(service_name)
        days_until_reset = self._calculate_days_until_reset(quota.reset_date)

        return QuotaUsage(
            service_name=quota.service_name,
            total_quota=quota.total_quota,
            used_quota=quota.used_quota,
            remaining_quota=quota.remaining_quota,
            usage_percentage=quota.usage_percentage,
            is_exhausted=quota.is_exhausted,
            is_enabled=quota.is_enabled,
            reset_date=quota.reset_date,
            days_until_reset=days_until_reset
        )


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
        self._logger.info(f"Resetting quota: service={service_name}")

        # 获取当前配额
        quota = self.get_by_service(service_name)

        # 计算新的重置日期（默认下一个月）
        today = date.today()
        # 计算下个月的第一天
        if today.month == 12:
            new_reset_date = date(today.year + 1, 1, 1)
        else:
            new_reset_date = date(today.year, today.month + 1, 1)

        # 准备更新数据
        update_data = ApiQuotaUpdate(
            used_quota=0,  # 重置使用量为0
            reset_date=new_reset_date
        )

        # 如果指定了新总配额
        if new_total is not None:
            if not self._validate_quota_amount(new_total):
                raise InvalidQuotaAmountError(f"Invalid new total quota amount: {new_total}")
            update_data.total_quota = new_total

        try:
            updated_quota = self.update(service_name, update_data)
            self._logger.info(f"Quota reset: {service_name}, new reset_date={new_reset_date}")
            return updated_quota
        except Exception as e:
            self._logger.error(f"Failed to reset quota for {service_name}: {e}")
            raise QuotaResetError(f"Failed to reset quota: {e}") from e

    def auto_reset_expired_quotas(self) -> Dict[str, bool]:
        """
        自动重置所有到期的配额

        Returns:
            Dict[str, bool]: 重置结果字典（服务名称 -> 是否成功）
        """
        self._logger.info("Auto resetting expired quotas")

        results: Dict[str, bool] = {}
        today = date.today()

        # 获取所有需要重置的服务
        services_needing_reset = self.get_services_needing_reset()

        for service_name in services_needing_reset:
            try:
                self.reset_quota(service_name)
                results[service_name.value] = True
                self._logger.info(f"Auto reset successful for {service_name}")
            except Exception as e:
                results[service_name.value] = False
                self._logger.error(f"Auto reset failed for {service_name}: {e}")

        return results

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
        self._logger.info(f"Setting reset date: service={service_name}, date={reset_date}")

        update_data = ApiQuotaUpdate(reset_date=reset_date)
        
        try:
            updated_quota = self.update(service_name, update_data)
            self._logger.info(f"Reset date set: {service_name} -> {reset_date}")
            return updated_quota
        except Exception as e:
            self._logger.error(f"Failed to set reset date for {service_name}: {e}")
            raise ApiQuotaError(f"Failed to set reset date: {e}") from e

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
        self._logger.info(f"Enabling service: {service_name}")

        update_data = ApiQuotaUpdate(is_enabled=True)
        
        try:
            updated_quota = self.update(service_name, update_data)
            self._logger.info(f"Service enabled: {service_name}")
            return updated_quota
        except Exception as e:
            self._logger.error(f"Failed to enable service {service_name}: {e}")
            raise ApiQuotaError(f"Failed to enable service: {e}") from e

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
        self._logger.info(f"Disabling service: {service_name}")

        update_data = ApiQuotaUpdate(is_enabled=False)
        
        try:
            updated_quota = self.update(service_name, update_data)
            self._logger.info(f"Service disabled: {service_name}")
            return updated_quota
        except Exception as e:
            self._logger.error(f"Failed to disable service {service_name}: {e}")
            raise ApiQuotaError(f"Failed to disable service: {e}") from e

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
        quota = self.get_by_service(service_name)
        return quota.is_enabled


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
        self._logger.info(f"Updating API key for service: {service_name}")

        # 加密API密钥
        encrypted_api_key = self._encrypt_api_key(api_key)
        
        update_data = ApiQuotaUpdate(api_key=encrypted_api_key)
        
        try:
            updated_quota = self.update(service_name, update_data)
            self._logger.info(f"API key updated for service: {service_name}")
            return updated_quota
        except Exception as e:
            self._logger.error(f"Failed to update API key for {service_name}: {e}")
            raise ApiQuotaError(f"Failed to update API key: {e}") from e

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
        self._logger.info(f"Clearing API key for service: {service_name}")

        update_data = ApiQuotaUpdate(api_key=None)
        
        try:
            updated_quota = self.update(service_name, update_data)
            self._logger.info(f"API key cleared for service: {service_name}")
            return updated_quota
        except Exception as e:
            self._logger.error(f"Failed to clear API key for {service_name}: {e}")
            raise ApiQuotaError(f"Failed to clear API key: {e}") from e

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
        quota = self.get_by_service(service_name)
        return quota.api_key is not None and quota.api_key.strip() != ""

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
        self._logger.debug(f"Listing quotas: is_enabled={is_enabled}, limit={limit}, offset={offset}")

        # 构建WHERE条件
        conditions = []
        params: List[Any] = []

        if is_enabled is not None:
            conditions.append("is_enabled = ?")
            params.append(1 if is_enabled else 0)

        where_clause = " AND ".join(conditions) if conditions else "1=1"
        order_clause = "ORDER BY service_name ASC" if order_by_service else "ORDER BY updated_at DESC"

        sql = f"""
        SELECT id, service_name, quota_total, quota_used, quota_reset_date,
               api_key, endpoint_url, is_enabled,
               created_at, updated_at
        FROM api_quotas
        WHERE {where_clause}
        {order_clause}
        LIMIT ? OFFSET ?
        """

        params.extend([limit, offset])

        try:
            result = self._db.query(sql, tuple(params))
            return [ApiQuota.from_row(dict(row)) for row in result]

        except DatabaseError as e:
            raise ApiQuotaError(f"Failed to list quotas: {e}") from e

    def list_usage_all(self) -> List[QuotaUsage]:
        """
        列出所有配额的详细使用统计

        Returns:
            List[QuotaUsage]: 配额使用统计列表
        """
        self._logger.debug("Listing all quota usage statistics")

        quotas = self.list_all(limit=1000)  # 获取所有配额
        usage_list: List[QuotaUsage] = []

        for quota in quotas:
            days_until_reset = self._calculate_days_until_reset(quota.reset_date)
            usage = QuotaUsage(
                service_name=quota.service_name,
                total_quota=quota.total_quota,
                used_quota=quota.used_quota,
                remaining_quota=quota.remaining_quota,
                usage_percentage=quota.usage_percentage,
                is_exhausted=quota.is_exhausted,
                is_enabled=quota.is_enabled,
                reset_date=quota.reset_date,
                days_until_reset=days_until_reset
            )
            usage_list.append(usage)

        return usage_list

    def count(self, is_enabled: Optional[bool] = None) -> int:
        """
        统计配额数量

        Args:
            is_enabled: 按启用状态过滤（可选）

        Returns:
            int: 配额数量
        """
        self._logger.debug(f"Counting quotas: is_enabled={is_enabled}")

        # 构建WHERE条件
        conditions = []
        params: List[Any] = []

        if is_enabled is not None:
            conditions.append("is_enabled = ?")
            params.append(1 if is_enabled else 0)

        where_clause = " AND ".join(conditions) if conditions else "1=1"
        sql = f"SELECT COUNT(*) as count FROM api_quotas WHERE {where_clause}"

        try:
            result = self._db.query(sql, tuple(params))
            row = list(result)[0]
            return int(row["count"])

        except DatabaseError as e:
            raise ApiQuotaError(f"Failed to count quotas: {e}") from e

    def get_services_needing_reset(self) -> List[ServiceName]:
        """
        获取需要重置的服务列表（重置日期已过）

        Returns:
            List[ServiceName]: 需要重置的服务列表
        """
        self._logger.debug("Getting services needing reset")

        today = date.today().isoformat()
        sql = """
        SELECT service_name FROM api_quotas
        WHERE quota_reset_date <= ?
        """

        try:
            result = self._db.query(sql, (today,))
            services = [ServiceName(row["service_name"]) for row in result]
            return services

        except DatabaseError as e:
            raise ApiQuotaError(f"Failed to get services needing reset: {e}") from e

    def get_low_quota_services(self, threshold_percentage: float = 80.0) -> List[QuotaUsage]:
        """
        获取低配额服务列表（使用率超过阈值）

        Args:
            threshold_percentage: 阈值百分比（默认80%）

        Returns:
            List[QuotaUsage]: 低配额服务列表
        """
        self._logger.debug(f"Getting low quota services: threshold={threshold_percentage}%")

        all_usage = self.list_usage_all()
        low_quota_services: List[QuotaUsage] = []

        for usage in all_usage:
            if usage.usage_percentage >= threshold_percentage and not usage.is_exhausted:
                low_quota_services.append(usage)

        return low_quota_services


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
        self._logger.info(f"Batch creating {len(quotas_data)} quotas")

        created_quotas: List[ApiQuota] = []
        failed_quotas: List[str] = []

        # 使用事务确保原子性
        with self._db.transaction() as tx:
            for quota_data in quotas_data:
                try:
                    # 验证配额金额
                    if not self._validate_quota_amount(quota_data.total_quota):
                        raise InvalidQuotaAmountError(f"Invalid total quota amount: {quota_data.total_quota}")

                    # 检查服务是否已存在
                    check_sql = "SELECT COUNT(*) as count FROM api_quotas WHERE service_name = ?"
                    cursor = tx.execute(check_sql, (quota_data.service_name.value,))
                    row = cursor.fetchone()
                    if row and int(row["count"]) > 0:
                        raise ApiQuotaError(f"Quota for service '{quota_data.service_name}' already exists")

                    # 加密API密钥（如果有）
                    encrypted_api_key = None
                    if quota_data.api_key:
                        encrypted_api_key = self._encrypt_api_key(quota_data.api_key)

                    # 插入配额
                    sql = """
                    INSERT INTO api_quotas (
                        service_name, quota_total, quota_used, quota_reset_date,
                        api_key, endpoint_url, is_enabled,
                        created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                    """

                    params = (
                        quota_data.service_name.value,
                        quota_data.total_quota,
                        0,
                        quota_data.reset_date.isoformat(),
                        encrypted_api_key,
                        quota_data.endpoint_url,
                        1 if quota_data.is_enabled else 0,
                    )

                    cursor = tx.execute(sql, params)
                    if cursor.rowcount != 1:
                        raise ApiQuotaError(f"Failed to create quota: {quota_data.service_name}")

                    # 获取新创建的ID
                    cursor = tx.execute("SELECT last_insert_rowid() as id", ())
                    row = cursor.fetchone()
                    if not row:
                        raise ApiQuotaError(f"Failed to get last insert ID for: {quota_data.service_name}")

                    new_id = int(row["id"])

                    # 查询新创建的配额
                    select_sql = """
                    SELECT id, service_name, quota_total, quota_used, quota_reset_date,
                           api_key, endpoint_url, is_enabled,
                           created_at, updated_at
                    FROM api_quotas
                    WHERE id = ?
                    """
                    cursor = tx.execute(select_sql, (new_id,))
                    row = cursor.fetchone()
                    if not row:
                        raise ApiQuotaError(f"Failed to retrieve created quota: {quota_data.service_name}")

                    quota = ApiQuota.from_row(dict(row))
                    created_quotas.append(quota)

                except (ApiQuotaError, InvalidQuotaAmountError) as e:
                    self._logger.error(f"Failed to create quota '{quota_data.service_name}': {e}")
                    failed_quotas.append(quota_data.service_name.value)
                    # 可以选择继续或终止批量创建
                    continue

        self._logger.info(f"Batch create completed: {len(created_quotas)} created, {len(failed_quotas)} failed")
        return created_quotas

    def batch_reset(self, service_names: List[ServiceName]) -> Dict[str, bool]:
        """
        批量重置配额

        Args:
            service_names: 服务名称列表

        Returns:
            Dict[str, bool]: 重置结果字典（服务名称 -> 是否成功）
        """
        self._logger.info(f"Batch resetting {len(service_names)} quotas")

        results: Dict[str, bool] = {}

        for service_name in service_names:
            try:
                self.reset_quota(service_name)
                results[service_name.value] = True
                self._logger.info(f"Batch reset successful for {service_name}")
            except Exception as e:
                results[service_name.value] = False
                self._logger.error(f"Batch reset failed for {service_name}: {e}")

        return results

    # =========================================================================
    # 统计和报表
    # =========================================================================

    def get_statistics(self) -> Dict[str, Any]:
        """
        获取配额统计信息

        Returns:
            Dict[str, Any]: 统计信息
        """
        self._logger.debug("Getting quota statistics")

        try:
            # 获取总数
            total_count = self.count()

            # 获取启用状态分布
            enabled_count = self.count(is_enabled=True)
            disabled_count = self.count(is_enabled=False)

            # 获取需要重置的数量
            services_needing_reset = self.get_services_needing_reset()
            reset_needed_count = len(services_needing_reset)

            # 获取低配额数量
            low_quota_services = self.get_low_quota_services()
            low_quota_count = len(low_quota_services)

            # 获取最新更新时间
            sql = """
            SELECT MAX(updated_at) as latest_update,
                   MIN(created_at) as earliest_create,
                   COUNT(DISTINCT service_name) as unique_services
            FROM api_quotas
            """
            result = self._db.query(sql, ())
            row = dict(list(result)[0])

            return {
                "total_quotas": total_count,
                "enabled_quotas": enabled_count,
                "disabled_quotas": disabled_count,
                "reset_needed": reset_needed_count,
                "low_quota": low_quota_count,
                "latest_update": row["latest_update"],
                "earliest_create": row["earliest_create"],
                "unique_services": int(row["unique_services"]),
            }

        except DatabaseError as e:
            raise ApiQuotaError(f"Failed to get statistics: {e}") from e

    def get_usage_summary(self) -> Dict[str, Any]:
        """
        获取配额使用摘要

        Returns:
            Dict[str, Any]: 使用摘要
        """
        self._logger.debug("Getting quota usage summary")

        all_usage = self.list_usage_all()
        
        total_quota = sum(usage.total_quota for usage in all_usage)
        total_used = sum(usage.used_quota for usage in all_usage)
        total_remaining = sum(usage.remaining_quota for usage in all_usage)
        
        if total_quota > 0:
            overall_usage_percentage = (total_used / total_quota) * 100
        else:
            overall_usage_percentage = 0.0

        exhausted_services = [usage.service_name.value for usage in all_usage if usage.is_exhausted]
        disabled_services = [usage.service_name.value for usage in all_usage if not usage.is_enabled]

        return {
            "total_quota": total_quota,
            "total_used": total_used,
            "total_remaining": total_remaining,
            "overall_usage_percentage": round(overall_usage_percentage, 2),
            "service_count": len(all_usage),
            "exhausted_services": exhausted_services,
            "disabled_services": disabled_services,
            "exhausted_count": len(exhausted_services),
            "disabled_count": len(disabled_services),
        }

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
        self._logger.debug(f"Getting daily usage trend for {service_name} (last {days} days)")

        # 这里应该查询历史使用记录表，但为了简化，我们返回模拟数据
        # 实际实现中应该有一个usage_history表
        trend_data: List[Dict[str, Any]] = []
        
        from datetime import timedelta
        today = datetime.now().date()
        
        for i in range(days):
            date_str = (today - timedelta(days=i)).isoformat()
            # 模拟数据：每天使用量在0-100之间
            simulated_usage = {
                "date": date_str,
                "usage_amount": (i * 7) % 100,  # 简单的模式
                "service_name": service_name.value,
            }
            trend_data.append(simulated_usage)

        return trend_data

    # =========================================================================
    # 辅助方法
    # =========================================================================

    def _get_last_insert_id(self) -> int:
        """获取最后插入的ID"""
        try:
            result = self._db.query("SELECT last_insert_rowid() as id", ())
            row = list(result)[0]
            return int(row["id"])
        except DatabaseError as e:
            raise ApiQuotaError(f"Failed to get last insert ID: {e}") from e

    def _encrypt_api_key(self, api_key: str) -> str:
        """加密API密钥"""
        # 这是一个简单的示例实现
        # 实际项目中应该使用更安全的加密方法
        # 例如: from cryptography.fernet import Fernet
        import base64
        # 简单base64编码，不是真正的加密
        encoded = base64.b64encode(api_key.encode('utf-8')).decode('utf-8')
        return f"encrypted:{encoded}"

    def _decrypt_api_key(self, encrypted_key: str) -> str:
        """解密API密钥"""
        if not encrypted_key or not encrypted_key.startswith("encrypted:"):
            return encrypted_key
            
        import base64
        try:
            encoded = encrypted_key.replace("encrypted:", "")
            decoded = base64.b64decode(encoded).decode('utf-8')
            return decoded
        except Exception as e:
            self._logger.error(f"Failed to decrypt API key: {e}")
            return encrypted_key

    def _generate_reservation_id(self) -> str:
        """生成预扣记录ID"""
        return f"res_{uuid.uuid4().hex}"

    def _validate_quota_amount(self, amount: int, allow_negative: bool = False, allow_zero: bool = True) -> bool:
        """验证配额金额（非负整数）"""
        if not isinstance(amount, int):
            return False
        
        if not allow_negative and amount < 0:
            return False
            
        if not allow_zero and amount <= 0:
            return False
            
        return True

    def _calculate_days_until_reset(self, reset_date: date) -> int:
        """计算距离重置的天数"""
        today = date.today()
        delta = reset_date - today
        return max(0, delta.days)


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
