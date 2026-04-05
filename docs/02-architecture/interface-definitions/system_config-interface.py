"""
System Config 模块接口定义 (Type Spec)
版本：v1.0（草案）
项目：ReelForge
文件映射：`models/system_config.py`

职责：系统配置数据的创建、读取、更新、删除操作，类型安全转换，配置缓存
依赖：src/reelforge/models/database/ (Database, DatabaseError等)

状态：📝 DRAFT (草案)
创建日期：2026-04-03
锁定状态：待审核确认

重要：此文件为接口定义草案，需通过mypy严格检查后锁定。
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import date, datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, Union

from reelforge.models.database import Database, DatabaseError, QueryResult


# =============================================================================
# 数据模型定义
# =============================================================================

class ConfigType(str, Enum):
    """配置值类型枚举"""
    STRING = "string"
    INTEGER = "int"
    FLOAT = "float"
    BOOLEAN = "bool"
    JSON = "json"


@dataclass
class SystemConfig:
    """系统配置数据模型

    对应数据库表：system_config
    字段映射：
        id -> config_id
        config_key -> key
        config_value -> value (原始字符串)
        config_type -> value_type (ConfigType)
        description -> description (可选)
        created_at -> created_at (datetime)
        updated_at -> updated_at (datetime)
    """

    config_id: int
    key: str
    value: str  # 原始字符串值
    value_type: ConfigType
    description: Optional[str]
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_row(cls, row: Dict[str, Any]) -> SystemConfig:
        """从数据库行创建SystemConfig对象"""
        return cls(
            config_id=row["id"],
            key=row["config_key"],
            value=row["config_value"] or "",
            value_type=ConfigType(row["config_type"]),
            description=row["description"],
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )

    def get_typed_value(self) -> Union[str, int, float, bool, Dict[str, Any], List[Any]]:
        """根据value_type获取类型转换后的值"""
        try:
            if self.value_type == ConfigType.STRING:
                return self.value
            elif self.value_type == ConfigType.INTEGER:
                return int(self.value)
            elif self.value_type == ConfigType.FLOAT:
                return float(self.value)
            elif self.value_type == ConfigType.BOOLEAN:
                return self.value.lower() in ("true", "1", "yes", "on", "enabled")
            elif self.value_type == ConfigType.JSON:
                return json.loads(self.value) if self.value else {}
            else:
                return self.value
        except (ValueError, json.JSONDecodeError) as e:
            raise ConfigValueError(
                f"Failed to parse config '{self.key}' with type '{self.value_type}': {e}"
            ) from e


@dataclass
class SystemConfigCreate:
    """创建系统配置时的数据模型（输入）"""
    key: str
    value: str
    value_type: ConfigType
    description: Optional[str] = None


@dataclass
class SystemConfigUpdate:
    """更新系统配置时的数据模型（输入）"""
    value: Optional[str] = None
    value_type: Optional[ConfigType] = None
    description: Optional[str] = None


@dataclass
class TypedConfig:
    """类型化的配置项"""
    key: str
    typed_value: Union[str, int, float, bool, Dict[str, Any], List[Any]]
    description: Optional[str]
    value_type: ConfigType
    updated_at: datetime


# =============================================================================
# 异常定义
# =============================================================================

class SystemConfigError(DatabaseError):
    """系统配置操作基础异常"""
    pass


class ConfigNotFoundError(SystemConfigError):
    """配置未找到异常"""
    pass


class ConfigAlreadyExistsError(SystemConfigError):
    """配置已存在异常（键重复）"""
    pass


class ConfigValidationError(SystemConfigError):
    """配置验证异常（键名无效、值类型不匹配等）"""
    pass


class ConfigValueError(SystemConfigError):
    """配置值转换异常（类型转换失败）"""
    pass


# =============================================================================
# 主类接口实现
# =============================================================================

class SystemConfigManager:
    """系统配置管理器（CRUD操作）

    职责：
        1. 系统配置创建、读取、更新、删除
        2. 配置值类型安全转换
        3. 配置验证（键名格式、值类型）
        4. 配置缓存（可选）
        5. 批量配置操作
    """

    def __init__(self, database: Database) -> None:
        """
        初始化系统配置管理器

        Args:
            database: 数据库实例
        """
        raise NotImplementedError

    # =========================================================================
    # 基本CRUD操作
    # =========================================================================

    def create(self, config_data: SystemConfigCreate) -> SystemConfig:
        """
        创建新系统配置

        Args:
            config_data: 配置创建数据

        Returns:
            SystemConfig: 创建的配置对象

        Raises:
            SystemConfigError: 创建失败
            ConfigAlreadyExistsError: 配置键已存在
            ConfigValidationError: 配置验证失败
        """
        raise NotImplementedError

    def get_by_key(self, key: str) -> SystemConfig:
        """
        根据键获取系统配置

        Args:
            key: 配置键

        Returns:
            SystemConfig: 配置对象

        Raises:
            ConfigNotFoundError: 配置不存在
            SystemConfigError: 查询失败
        """
        raise NotImplementedError

    def get_by_id(self, config_id: int) -> SystemConfig:
        """
        根据ID获取系统配置

        Args:
            config_id: 配置ID

        Returns:
            SystemConfig: 配置对象

        Raises:
            ConfigNotFoundError: 配置不存在
            SystemConfigError: 查询失败
        """
        raise NotImplementedError

    def update(self, key: str, update_data: SystemConfigUpdate) -> SystemConfig:
        """
        更新系统配置

        Args:
            key: 配置键
            update_data: 更新数据

        Returns:
            SystemConfig: 更新后的配置对象

        Raises:
            ConfigNotFoundError: 配置不存在
            ConfigValidationError: 配置验证失败
            SystemConfigError: 更新失败
        """
        raise NotImplementedError

    def delete(self, key: str) -> bool:
        """
        删除系统配置

        Args:
            key: 配置键

        Returns:
            bool: 删除是否成功

        Raises:
            ConfigNotFoundError: 配置不存在
            SystemConfigError: 删除失败
        """
        raise NotImplementedError

    # =========================================================================
    # 类型化配置操作
    # =========================================================================

    def get_typed_config(self, key: str) -> TypedConfig:
        """
        获取类型化的配置项

        Args:
            key: 配置键

        Returns:
            TypedConfig: 类型化的配置项

        Raises:
            ConfigNotFoundError: 配置不存在
            ConfigValueError: 值转换失败
            SystemConfigError: 查询失败
        """
        raise NotImplementedError

    def set_string_config(self, key: str, value: str, description: Optional[str] = None) -> SystemConfig:
        """
        设置字符串类型配置

        Args:
            key: 配置键
            value: 字符串值
            description: 描述（可选）

        Returns:
            SystemConfig: 配置对象
        """
        raise NotImplementedError

    def set_int_config(self, key: str, value: int, description: Optional[str] = None) -> SystemConfig:
        """
        设置整数类型配置

        Args:
            key: 配置键
            value: 整数值
            description: 描述（可选）

        Returns:
            SystemConfig: 配置对象
        """
        raise NotImplementedError

    def set_float_config(self, key: str, value: float, description: Optional[str] = None) -> SystemConfig:
        """
        设置浮点数类型配置

        Args:
            key: 配置键
            value: 浮点数值
            description: 描述（可选）

        Returns:
            SystemConfig: 配置对象
        """
        raise NotImplementedError

    def set_bool_config(self, key: str, value: bool, description: Optional[str] = None) -> SystemConfig:
        """
        设置布尔类型配置

        Args:
            key: 配置键
            value: 布尔值
            description: 描述（可选）

        Returns:
            SystemConfig: 配置对象
        """
        raise NotImplementedError

    def set_json_config(
        self,
        key: str,
        value: Union[Dict[str, Any], List[Any]],
        description: Optional[str] = None,
    ) -> SystemConfig:
        """
        设置JSON类型配置

        Args:
            key: 配置键
            value: JSON值（字典或列表）
            description: 描述（可选）

        Returns:
            SystemConfig: 配置对象
        """
        raise NotImplementedError

    # =========================================================================
    # 查询和列表操作
    # =========================================================================

    def list_all(
        self,
        prefix: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
        order_by_key: bool = True,
    ) -> List[SystemConfig]:
        """
        列出所有系统配置

        Args:
            prefix: 按键前缀过滤（可选）
            limit: 返回数量限制
            offset: 偏移量
            order_by_key: 是否按键排序

        Returns:
            List[SystemConfig]: 配置列表
        """
        raise NotImplementedError

    def list_typed_all(self, prefix: Optional[str] = None) -> List[TypedConfig]:
        """
        列出所有类型化的配置

        Args:
            prefix: 按键前缀过滤（可选）

        Returns:
            List[TypedConfig]: 类型化的配置列表
        """
        raise NotImplementedError

    def search_by_key(self, query: str, limit: int = 50) -> List[SystemConfig]:
        """
        按键名搜索配置

        Args:
            query: 搜索关键词
            limit: 返回数量限制

        Returns:
            List[SystemConfig]: 匹配的配置列表
        """
        raise NotImplementedError

    def search_by_description(self, query: str, limit: int = 50) -> List[SystemConfig]:
        """
        按描述搜索配置

        Args:
            query: 搜索关键词
            limit: 返回数量限制

        Returns:
            List[SystemConfig]: 匹配的配置列表
        """
        raise NotImplementedError

    def count(self, prefix: Optional[str] = None) -> int:
        """
        统计配置数量

        Args:
            prefix: 按键前缀过滤（可选）

        Returns:
            int: 配置数量
        """
        raise NotImplementedError

    # =========================================================================
    # 批量操作
    # =========================================================================

    def batch_create(self, configs_data: List[SystemConfigCreate]) -> List[SystemConfig]:
        """
        批量创建配置

        Args:
            configs_data: 配置创建数据列表

        Returns:
            List[SystemConfig]: 创建的配置列表

        Raises:
            SystemConfigError: 批量创建失败
        """
        raise NotImplementedError

    def batch_update(self, updates: Dict[str, SystemConfigUpdate]) -> Dict[str, SystemConfig]:
        """
        批量更新配置

        Args:
            updates: 更新字典（键 -> 更新数据）

        Returns:
            Dict[str, SystemConfig]: 更新后的配置字典
        """
        raise NotImplementedError

    def batch_delete(self, keys: List[str]) -> Dict[str, bool]:
        """
        批量删除配置

        Args:
            keys: 配置键列表

        Returns:
            Dict[str, bool]: 删除结果字典（键 -> 是否成功）
        """
        raise NotImplementedError

    def import_from_dict(self, config_dict: Dict[str, Any]) -> Dict[str, SystemConfig]:
        """
        从字典导入配置（自动推断类型）

        Args:
            config_dict: 配置字典

        Returns:
            Dict[str, SystemConfig]: 导入的配置字典
        """
        raise NotImplementedError

    def export_to_dict(self, prefix: Optional[str] = None) -> Dict[str, Any]:
        """
        导出配置为字典（类型化值）

        Args:
            prefix: 按键前缀过滤（可选）

        Returns:
            Dict[str, Any]: 配置字典（键 -> 类型化值）
        """
        raise NotImplementedError

    # =========================================================================
    # 实用方法
    # =========================================================================

    def get_string(self, key: str, default: str = "") -> str:
        """
        获取字符串配置值

        Args:
            key: 配置键
            default: 默认值（配置不存在时返回）

        Returns:
            str: 字符串值
        """
        raise NotImplementedError

    def get_int(self, key: str, default: int = 0) -> int:
        """
        获取整数配置值

        Args:
            key: 配置键
            default: 默认值（配置不存在时返回）

        Returns:
            int: 整数值
        """
        raise NotImplementedError

    def get_float(self, key: str, default: float = 0.0) -> float:
        """
        获取浮点数配置值

        Args:
            key: 配置键
            default: 默认值（配置不存在时返回）

        Returns:
            float: 浮点数值
        """
        raise NotImplementedError

    def get_bool(self, key: str, default: bool = False) -> bool:
        """
        获取布尔配置值

        Args:
            key: 配置键
            default: 默认值（配置不存在时返回）

        Returns:
            bool: 布尔值
        """
        raise NotImplementedError

    def get_json(self, key: str, default: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        获取JSON配置值

        Args:
            key: 配置键
            default: 默认值（配置不存在时返回）

        Returns:
            Dict[str, Any]: JSON字典
        """
        raise NotImplementedError

    def get_list(self, key: str, default: Optional[List[Any]] = None) -> List[Any]:
        """
        获取列表配置值（JSON数组）

        Args:
            key: 配置键
            default: 默认值（配置不存在时返回）

        Returns:
            List[Any]: 列表值
        """
        raise NotImplementedError

    def exists(self, key: str) -> bool:
        """
        检查配置是否存在

        Args:
            key: 配置键

        Returns:
            bool: 配置是否存在
        """
        raise NotImplementedError

    # =========================================================================
    # 验证方法
    # =========================================================================

    def validate_key(self, key: str) -> bool:
        """
        验证配置键是否有效

        Args:
            key: 配置键

        Returns:
            bool: 是否有效

        规则：
        - 非空字符串
        - 仅包含字母、数字、下划线、点、连字符
        - 最大长度128字符
        - 不能以点开头或结尾
        """
        raise NotImplementedError

    def validate_value_for_type(self, value: str, value_type: ConfigType) -> bool:
        """
        验证值是否符合指定类型

        Args:
            value: 字符串值
            value_type: 配置类型

        Returns:
            bool: 是否符合类型
        """
        raise NotImplementedError

    def infer_type_from_value(self, value: Any) -> ConfigType:
        """
        从值推断配置类型

        Args:
            value: 任意类型值

        Returns:
            ConfigType: 推断的配置类型
        """
        raise NotImplementedError

    # =========================================================================
    # 缓存管理（可选）
    # =========================================================================

    def clear_cache(self) -> None:
        """清除配置缓存"""
        raise NotImplementedError

    def reload_cache(self) -> None:
        """重新加载配置缓存"""
        raise NotImplementedError

    def is_cache_enabled(self) -> bool:
        """检查缓存是否启用"""
        raise NotImplementedError

    def set_cache_enabled(self, enabled: bool) -> None:
        """设置缓存启用状态"""
        raise NotImplementedError

    # =========================================================================
    # 统计和报表
    # =========================================================================

    def get_statistics(self) -> Dict[str, Any]:
        """
        获取配置统计信息

        Returns:
            Dict[str, Any]: 统计信息
        """
        raise NotImplementedError

    def get_type_distribution(self) -> Dict[str, int]:
        """
        获取类型分布统计

        Returns:
            Dict[str, int]: 类型->数量映射
        """
        raise NotImplementedError

    # =========================================================================
    # 辅助方法
    # =========================================================================

    def _get_last_insert_id(self) -> int:
        """获取最后插入的ID"""
        raise NotImplementedError

    def _serialize_value(self, value: Any) -> str:
        """序列化值为字符串"""
        raise NotImplementedError

    def _deserialize_value(self, value_str: str, value_type: ConfigType) -> Any:
        """反序列化字符串为指定类型值"""
        raise NotImplementedError


# =============================================================================
# 导出列表
# =============================================================================

__all__ = [
    # 数据模型
    "SystemConfig",
    "SystemConfigCreate",
    "SystemConfigUpdate",
    "TypedConfig",
    # 枚举
    "ConfigType",
    # 异常
    "SystemConfigError",
    "ConfigNotFoundError",
    "ConfigAlreadyExistsError",
    "ConfigValidationError",
    "ConfigValueError",
    # 主类
    "SystemConfigManager",
]