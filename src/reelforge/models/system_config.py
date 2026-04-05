"""
系统配置数据模型和CRUD操作
版本：v1.0
文件映射：docs/02-architecture/database-schema.sql (system_config表)

职责：系统配置数据的创建、读取、更新、删除操作，类型安全转换，配置缓存
依赖：src/reelforge/models/database/ (Database, DatabaseError等)
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from datetime import datetime
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
        self._db = database
        self._logger = logging.getLogger(__name__)

        # 配置缓存
        self._cache: Dict[str, SystemConfig] = {}
        self._cache_enabled: bool = True

        # 确保数据库已连接
        try:
            self._db.connect()
        except Exception as e:
            raise SystemConfigError(f"Database connection failed: {e}") from e

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
        self._logger.info(f"Creating config: key={config_data.key}, type={config_data.value_type}")

        # 验证键名
        if not self.validate_key(config_data.key):
            raise ConfigValidationError(f"Invalid config key: {config_data.key}")

        # 验证值类型
        if not self.validate_value_for_type(config_data.value, config_data.value_type):
            raise ConfigValidationError(
                f"Value '{config_data.value}' does not match type '{config_data.value_type}'"
            )

        # 检查键是否已存在
        if self.exists(config_data.key):
            raise ConfigAlreadyExistsError(f"Config key '{config_data.key}' already exists")

        # 构建SQL
        sql = """
        INSERT INTO system_config (
            config_key, config_value, config_type, description,
            created_at, updated_at
        ) VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """

        params = (
            config_data.key,
            config_data.value,
            config_data.value_type.value,
            config_data.description,
        )

        try:
            # 执行插入
            affected = self._db.execute(sql, params)
            if affected != 1:
                raise SystemConfigError(f"Failed to create config: affected rows={affected}")

            # 获取新创建的配置
            new_id = self._get_last_insert_id()
            config = self.get_by_id(new_id)

            # 更新缓存
            if self._cache_enabled:
                self._cache[config_data.key] = config

            return config

        except DatabaseError as e:
            raise SystemConfigError(f"Failed to create config: {e}") from e

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
        self._logger.debug(f"Getting config by key: {key}")

        # 检查缓存
        if self._cache_enabled and key in self._cache:
            self._logger.debug(f"Cache hit for key: {key}")
            return self._cache[key]

        sql = """
        SELECT id, config_key, config_value, config_type, description,
               created_at, updated_at
        FROM system_config
        WHERE config_key = ?
        """

        try:
            result = self._db.query(sql, (key,))
            rows = list(result)

            if not rows:
                raise ConfigNotFoundError(f"Config with key '{key}' not found")

            if len(rows) > 1:
                self._logger.warning(f"Multiple configs found with key {key}")

            config = SystemConfig.from_row(dict(rows[0]))

            # 更新缓存
            if self._cache_enabled:
                self._cache[key] = config

            return config

        except DatabaseError as e:
            raise SystemConfigError(f"Failed to get config by key: {e}") from e

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
        self._logger.debug(f"Getting config by ID: {config_id}")

        sql = """
        SELECT id, config_key, config_value, config_type, description,
               created_at, updated_at
        FROM system_config
        WHERE id = ?
        """

        try:
            result = self._db.query(sql, (config_id,))
            rows = list(result)

            if not rows:
                raise ConfigNotFoundError(f"Config with ID {config_id} not found")

            if len(rows) > 1:
                self._logger.warning(f"Multiple configs found with ID {config_id}")

            return SystemConfig.from_row(dict(rows[0]))

        except DatabaseError as e:
            raise SystemConfigError(f"Failed to get config by ID: {e}") from e

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
        self._logger.info(f"Updating config: key={key}")

        # 获取当前配置
        try:
            current_config = self.get_by_key(key)
        except ConfigNotFoundError:
            raise

        # 构建更新SQL
        updates = []
        params: List[Any] = []

        if update_data.value is not None:
            # 验证新值类型
            value_type = update_data.value_type if update_data.value_type else current_config.value_type
            if not self.validate_value_for_type(update_data.value, value_type):
                raise ConfigValidationError(
                    f"Value '{update_data.value}' does not match type '{value_type}'"
                )
            updates.append("config_value = ?")
            params.append(update_data.value)

        if update_data.value_type is not None:
            # 如果也更新了值，需要重新验证
            if update_data.value is not None and not self.validate_value_for_type(update_data.value, update_data.value_type):
                raise ConfigValidationError(
                    f"Value '{update_data.value}' does not match type '{update_data.value_type}'"
                )
            updates.append("config_type = ?")
            params.append(update_data.value_type.value)

        if update_data.description is not None:
            updates.append("description = ?")
            params.append(update_data.description)

        # 如果没有更新内容，直接返回原配置
        if not updates:
            return current_config

        # 添加更新时间
        updates.append("updated_at = CURRENT_TIMESTAMP")

        # 构建完整SQL
        sql = f"""
        UPDATE system_config
        SET {', '.join(updates)}
        WHERE config_key = ?
        """

        params.append(key)

        try:
            affected = self._db.execute(sql, tuple(params))
            if affected != 1:
                raise SystemConfigError(f"Failed to update config: affected rows={affected}")

            # 清除缓存
            if self._cache_enabled and key in self._cache:
                del self._cache[key]

            # 返回更新后的配置
            return self.get_by_key(key)

        except DatabaseError as e:
            raise SystemConfigError(f"Failed to update config: {e}") from e

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
        self._logger.info(f"Deleting config: key={key}")

        # 检查配置是否存在
        try:
            self.get_by_key(key)
        except ConfigNotFoundError:
            raise

        sql = "DELETE FROM system_config WHERE config_key = ?"

        try:
            affected = self._db.execute(sql, (key,))
            success = affected == 1

            if success:
                self._logger.info(f"Deleted config: {key}")
                # 清除缓存
                if self._cache_enabled and key in self._cache:
                    del self._cache[key]
            else:
                self._logger.warning(f"Config {key} not found for deletion")

            return success

        except DatabaseError as e:
            raise SystemConfigError(f"Failed to delete config: {e}") from e

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
        self._logger.debug(f"Getting typed config: key={key}")

        config = self.get_by_key(key)
        typed_value = config.get_typed_value()

        return TypedConfig(
            key=config.key,
            typed_value=typed_value,
            description=config.description,
            value_type=config.value_type,
            updated_at=config.updated_at,
        )

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
        try:
            # 如果配置已存在，更新它
            existing_config = self.get_by_key(key)
            update_data = SystemConfigUpdate(
                value=value,
                value_type=ConfigType.STRING,
                description=description
            )
            return self.update(key, update_data)
        except ConfigNotFoundError:
            # 配置不存在，创建新的
            config_data = SystemConfigCreate(
                key=key,
                value=value,
                value_type=ConfigType.STRING,
                description=description
            )
            return self.create(config_data)

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
        try:
            existing_config = self.get_by_key(key)
            update_data = SystemConfigUpdate(
                value=str(value),
                value_type=ConfigType.INTEGER,
                description=description
            )
            return self.update(key, update_data)
        except ConfigNotFoundError:
            config_data = SystemConfigCreate(
                key=key,
                value=str(value),
                value_type=ConfigType.INTEGER,
                description=description
            )
            return self.create(config_data)

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
        try:
            existing_config = self.get_by_key(key)
            update_data = SystemConfigUpdate(
                value=str(value),
                value_type=ConfigType.FLOAT,
                description=description
            )
            return self.update(key, update_data)
        except ConfigNotFoundError:
            config_data = SystemConfigCreate(
                key=key,
                value=str(value),
                value_type=ConfigType.FLOAT,
                description=description
            )
            return self.create(config_data)

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
        str_value = "true" if value else "false"
        try:
            existing_config = self.get_by_key(key)
            update_data = SystemConfigUpdate(
                value=str_value,
                value_type=ConfigType.BOOLEAN,
                description=description
            )
            return self.update(key, update_data)
        except ConfigNotFoundError:
            config_data = SystemConfigCreate(
                key=key,
                value=str_value,
                value_type=ConfigType.BOOLEAN,
                description=description
            )
            return self.create(config_data)

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
        str_value = json.dumps(value, ensure_ascii=False)
        try:
            existing_config = self.get_by_key(key)
            update_data = SystemConfigUpdate(
                value=str_value,
                value_type=ConfigType.JSON,
                description=description
            )
            return self.update(key, update_data)
        except ConfigNotFoundError:
            config_data = SystemConfigCreate(
                key=key,
                value=str_value,
                value_type=ConfigType.JSON,
                description=description
            )
            return self.create(config_data)

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
        self._logger.debug(f"Listing configs: prefix={prefix}, limit={limit}, offset={offset}")

        # 构建WHERE条件
        conditions = []
        params: List[Any] = []

        if prefix is not None:
            conditions.append("config_key LIKE ?")
            params.append(f"{prefix}%")

        where_clause = " AND ".join(conditions) if conditions else "1=1"
        order_clause = "ORDER BY config_key ASC" if order_by_key else "ORDER BY updated_at DESC"

        sql = f"""
        SELECT id, config_key, config_value, config_type, description,
               created_at, updated_at
        FROM system_config
        WHERE {where_clause}
        {order_clause}
        LIMIT ? OFFSET ?
        """

        params.extend([limit, offset])

        try:
            result = self._db.query(sql, tuple(params))
            return [SystemConfig.from_row(dict(row)) for row in result]

        except DatabaseError as e:
            raise SystemConfigError(f"Failed to list configs: {e}") from e

    def list_typed_all(self, prefix: Optional[str] = None) -> List[TypedConfig]:
        """
        列出所有类型化的配置

        Args:
            prefix: 按键前缀过滤（可选）

        Returns:
            List[TypedConfig]: 类型化的配置列表
        """
        self._logger.debug(f"Listing typed configs: prefix={prefix}")

        configs = self.list_all(prefix=prefix, limit=1000)  # 使用较大限制获取所有
        typed_configs: List[TypedConfig] = []

        for config in configs:
            try:
                typed_value = config.get_typed_value()
                typed_configs.append(TypedConfig(
                    key=config.key,
                    typed_value=typed_value,
                    description=config.description,
                    value_type=config.value_type,
                    updated_at=config.updated_at,
                ))
            except ConfigValueError as e:
                self._logger.warning(f"Skipping config '{config.key}' due to value error: {e}")
                continue

        return typed_configs

    def search_by_key(self, query: str, limit: int = 50) -> List[SystemConfig]:
        """
        按键名搜索配置

        Args:
            query: 搜索关键词
            limit: 返回数量限制

        Returns:
            List[SystemConfig]: 匹配的配置列表
        """
        self._logger.debug(f"Searching configs by key: query='{query}'")

        sql = """
        SELECT id, config_key, config_value, config_type, description,
               created_at, updated_at
        FROM system_config
        WHERE config_key LIKE ?
        ORDER BY config_key
        LIMIT ?
        """

        try:
            result = self._db.query(sql, (f"%{query}%", limit))
            return [SystemConfig.from_row(dict(row)) for row in result]

        except DatabaseError as e:
            raise SystemConfigError(f"Failed to search configs by key: {e}") from e

    def search_by_description(self, query: str, limit: int = 50) -> List[SystemConfig]:
        """
        按描述搜索配置

        Args:
            query: 搜索关键词
            limit: 返回数量限制

        Returns:
            List[SystemConfig]: 匹配的配置列表
        """
        self._logger.debug(f"Searching configs by description: query='{query}'")

        sql = """
        SELECT id, config_key, config_value, config_type, description,
               created_at, updated_at
        FROM system_config
        WHERE description LIKE ?
        ORDER BY config_key
        LIMIT ?
        """

        try:
            result = self._db.query(sql, (f"%{query}%", limit))
            return [SystemConfig.from_row(dict(row)) for row in result]

        except DatabaseError as e:
            raise SystemConfigError(f"Failed to search configs by description: {e}") from e

    def count(self, prefix: Optional[str] = None) -> int:
        """
        统计配置数量

        Args:
            prefix: 按键前缀过滤（可选）

        Returns:
            int: 配置数量
        """
        self._logger.debug(f"Counting configs: prefix={prefix}")

        # 构建WHERE条件
        conditions = []
        params: List[Any] = []

        if prefix is not None:
            conditions.append("config_key LIKE ?")
            params.append(f"{prefix}%")

        where_clause = " AND ".join(conditions) if conditions else "1=1"
        sql = f"SELECT COUNT(*) as count FROM system_config WHERE {where_clause}"

        try:
            result = self._db.query(sql, tuple(params))
            row = list(result)[0]
            return int(row["count"])

        except DatabaseError as e:
            raise SystemConfigError(f"Failed to count configs: {e}") from e

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
        self._logger.info(f"Batch creating {len(configs_data)} configs")

        created_configs: List[SystemConfig] = []
        failed_configs: List[str] = []

        # 使用事务确保原子性
        with self._db.transaction() as tx:
            for config_data in configs_data:
                try:
                    # 验证键名
                    if not self.validate_key(config_data.key):
                        raise ConfigValidationError(f"Invalid config key: {config_data.key}")

                    # 验证值类型
                    if not self.validate_value_for_type(config_data.value, config_data.value_type):
                        raise ConfigValidationError(
                            f"Value '{config_data.value}' does not match type '{config_data.value_type}'"
                        )

                    # 检查键是否已存在
                    check_sql = "SELECT COUNT(*) as count FROM system_config WHERE config_key = ?"
                    cursor = tx.execute(check_sql, (config_data.key,))
                    row = cursor.fetchone()
                    if row and int(row["count"]) > 0:
                        raise ConfigAlreadyExistsError(f"Config key '{config_data.key}' already exists")

                    # 插入配置
                    sql = """
                    INSERT INTO system_config (
                        config_key, config_value, config_type, description,
                        created_at, updated_at
                    ) VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                    """

                    params = (
                        config_data.key,
                        config_data.value,
                        config_data.value_type.value,
                        config_data.description,
                    )

                    cursor = tx.execute(sql, params)
                    if cursor.rowcount != 1:
                        raise SystemConfigError(f"Failed to create config: {config_data.key}")

                    # 获取新创建的ID
                    cursor = tx.execute("SELECT last_insert_rowid() as id", ())
                    row = cursor.fetchone()
                    if not row:
                        raise SystemConfigError(f"Failed to get last insert ID for: {config_data.key}")

                    new_id = int(row["id"])

                    # 查询新创建的配置
                    select_sql = """
                    SELECT id, config_key, config_value, config_type, description,
                           created_at, updated_at
                    FROM system_config
                    WHERE id = ?
                    """
                    cursor = tx.execute(select_sql, (new_id,))
                    row = cursor.fetchone()
                    if not row:
                        raise SystemConfigError(f"Failed to retrieve created config: {config_data.key}")

                    config = SystemConfig.from_row(dict(row))
                    created_configs.append(config)

                    # 更新缓存
                    if self._cache_enabled:
                        self._cache[config_data.key] = config

                except (SystemConfigError, ConfigValidationError, ConfigAlreadyExistsError) as e:
                    self._logger.error(f"Failed to create config '{config_data.key}': {e}")
                    failed_configs.append(config_data.key)
                    # 可以选择继续或终止批量创建
                    continue

        self._logger.info(f"Batch create completed: {len(created_configs)} created, {len(failed_configs)} failed")
        return created_configs

    def batch_update(self, updates: Dict[str, SystemConfigUpdate]) -> Dict[str, SystemConfig]:
        """
        批量更新配置

        Args:
            updates: 更新字典（键 -> 更新数据）

        Returns:
            Dict[str, SystemConfig]: 更新后的配置字典
        """
        self._logger.info(f"Batch updating {len(updates)} configs")

        updated_configs: Dict[str, SystemConfig] = {}
        failed_configs: List[str] = []

        for key, update_data in updates.items():
            try:
                config = self.update(key, update_data)
                updated_configs[key] = config
            except (ConfigNotFoundError, ConfigValidationError, SystemConfigError) as e:
                self._logger.error(f"Failed to update config '{key}': {e}")
                failed_configs.append(key)
                continue

        if failed_configs:
            self._logger.warning(f"Batch update failed for keys: {failed_configs}")

        return updated_configs

    def batch_delete(self, keys: List[str]) -> Dict[str, bool]:
        """
        批量删除配置

        Args:
            keys: 配置键列表

        Returns:
            Dict[str, bool]: 删除结果字典（键 -> 是否成功）
        """
        self._logger.info(f"Batch deleting {len(keys)} configs")

        results: Dict[str, bool] = {}

        for key in keys:
            try:
                success = self.delete(key)
                results[key] = success
            except (ConfigNotFoundError, SystemConfigError) as e:
                self._logger.error(f"Failed to delete config '{key}': {e}")
                results[key] = False

        return results

    def import_from_dict(self, config_dict: Dict[str, Any]) -> Dict[str, SystemConfig]:
        """
        从字典导入配置（自动推断类型）

        Args:
            config_dict: 配置字典

        Returns:
            Dict[str, SystemConfig]: 导入的配置字典
        """
        self._logger.info(f"Importing {len(config_dict)} configs from dictionary")

        imported_configs: Dict[str, SystemConfig] = {}

        for key, value in config_dict.items():
            try:
                # 推断类型
                value_type = self.infer_type_from_value(value)

                # 创建配置数据
                config_data = SystemConfigCreate(
                    key=key,
                    value=self._serialize_value(value),
                    value_type=value_type,
                    description=f"Imported from dictionary",
                )

                # 创建或更新配置
                try:
                    existing_config = self.get_by_key(key)
                    # 配置已存在，更新它
                    update_data = SystemConfigUpdate(
                        value=self._serialize_value(value),
                        value_type=value_type,
                        description=f"Imported from dictionary (updated)",
                    )
                    config = self.update(key, update_data)
                except ConfigNotFoundError:
                    # 配置不存在，创建新的
                    config = self.create(config_data)

                imported_configs[key] = config

            except (ConfigValidationError, SystemConfigError) as e:
                self._logger.error(f"Failed to import config '{key}': {e}")
                continue

        return imported_configs

    def export_to_dict(self, prefix: Optional[str] = None) -> Dict[str, Any]:
        """
        导出配置为字典（类型化值）

        Args:
            prefix: 按键前缀过滤（可选）

        Returns:
            Dict[str, Any]: 配置字典（键 -> 类型化值）
        """
        self._logger.debug(f"Exporting configs to dictionary: prefix={prefix}")

        typed_configs = self.list_typed_all(prefix=prefix)
        config_dict: Dict[str, Any] = {}

        for config in typed_configs:
            config_dict[config.key] = config.typed_value

        return config_dict

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
        try:
            typed_config = self.get_typed_config(key)
            if isinstance(typed_config.typed_value, str):
                return typed_config.typed_value
            else:
                # 强制转换为字符串
                return str(typed_config.typed_value)
        except (ConfigNotFoundError, ConfigValueError, SystemConfigError):
            return default

    def get_int(self, key: str, default: int = 0) -> int:
        """
        获取整数配置值

        Args:
            key: 配置键
            default: 默认值（配置不存在时返回）

        Returns:
            int: 整数值
        """
        try:
            typed_config = self.get_typed_config(key)
            if isinstance(typed_config.typed_value, int):
                return typed_config.typed_value
            else:
                # 尝试转换
                return int(typed_config.typed_value)
        except (ConfigNotFoundError, ConfigValueError, SystemConfigError, ValueError, TypeError):
            return default

    def get_float(self, key: str, default: float = 0.0) -> float:
        """
        获取浮点数配置值

        Args:
            key: 配置键
            default: 默认值（配置不存在时返回）

        Returns:
            float: 浮点数值
        """
        try:
            typed_config = self.get_typed_config(key)
            if isinstance(typed_config.typed_value, float):
                return typed_config.typed_value
            else:
                # 尝试转换
                return float(typed_config.typed_value)
        except (ConfigNotFoundError, ConfigValueError, SystemConfigError, ValueError, TypeError):
            return default

    def get_bool(self, key: str, default: bool = False) -> bool:
        """
        获取布尔配置值

        Args:
            key: 配置键
            default: 默认值（配置不存在时返回）

        Returns:
            bool: 布尔值
        """
        try:
            typed_config = self.get_typed_config(key)
            if isinstance(typed_config.typed_value, bool):
                return typed_config.typed_value
            else:
                # 布尔值已经在get_typed_config中转换过，但这里处理意外情况
                value = str(typed_config.typed_value).lower()
                return value in ("true", "1", "yes", "on", "enabled")
        except (ConfigNotFoundError, ConfigValueError, SystemConfigError):
            return default

    def get_json(self, key: str, default: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        获取JSON配置值

        Args:
            key: 配置键
            default: 默认值（配置不存在时返回）

        Returns:
            Dict[str, Any]: JSON字典
        """
        try:
            typed_config = self.get_typed_config(key)
            if isinstance(typed_config.typed_value, dict):
                return typed_config.typed_value
            else:
                # 如果不是字典，尝试转换或返回默认值
                if default is None:
                    return {}
                return default
        except (ConfigNotFoundError, ConfigValueError, SystemConfigError):
            if default is None:
                return {}
            return default

    def get_list(self, key: str, default: Optional[List[Any]] = None) -> List[Any]:
        """
        获取列表配置值（JSON数组）

        Args:
            key: 配置键
            default: 默认值（配置不存在时返回）

        Returns:
            List[Any]: 列表值
        """
        try:
            typed_config = self.get_typed_config(key)
            if isinstance(typed_config.typed_value, list):
                return typed_config.typed_value
            else:
                # 如果不是列表，尝试转换或返回默认值
                if default is None:
                    return []
                return default
        except (ConfigNotFoundError, ConfigValueError, SystemConfigError):
            if default is None:
                return []
            return default

    def exists(self, key: str) -> bool:
        """
        检查配置是否存在

        Args:
            key: 配置键

        Returns:
            bool: 配置是否存在
        """
        self._logger.debug(f"Checking if config exists: key={key}")

        # 先检查缓存
        if self._cache_enabled and key in self._cache:
            return True

        sql = "SELECT COUNT(*) as count FROM system_config WHERE config_key = ?"

        try:
            result = self._db.query(sql, (key,))
            row = list(result)[0]
            exists = int(row["count"]) > 0

            # 如果存在且缓存启用，但不在缓存中，加载到缓存
            if exists and self._cache_enabled and key not in self._cache:
                try:
                    self._cache[key] = self.get_by_key(key)
                except SystemConfigError:
                    # 如果加载失败，忽略缓存更新
                    pass

            return exists

        except DatabaseError as e:
            raise SystemConfigError(f"Failed to check if config exists: {e}") from e

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
        if not isinstance(key, str):
            return False

        if not key.strip():
            return False

        if len(key) > 128:
            return False

        if key.startswith(".") or key.endswith("."):
            return False

        # 正则表达式：字母、数字、下划线、点、连字符
        pattern = r"^[a-zA-Z0-9_.\-]+$"
        if not re.match(pattern, key):
            return False

        return True

    def validate_value_for_type(self, value: str, value_type: ConfigType) -> bool:
        """
        验证值是否符合指定类型

        Args:
            value: 字符串值
            value_type: 配置类型

        Returns:
            bool: 是否符合类型
        """
        if not isinstance(value, str):
            return False

        try:
            if value_type == ConfigType.STRING:
                # 字符串总是有效
                return True

            elif value_type == ConfigType.INTEGER:
                # 检查是否为整数
                int(value)
                return True

            elif value_type == ConfigType.FLOAT:
                # 检查是否为浮点数
                float(value)
                return True

            elif value_type == ConfigType.BOOLEAN:
                # 检查是否为有效的布尔值
                val_lower = value.lower()
                return val_lower in ("true", "false", "0", "1", "yes", "no", "on", "off", "enabled", "disabled")

            elif value_type == ConfigType.JSON:
                # 检查是否为有效的JSON
                if not value.strip():
                    return True  # 空字符串视为空JSON对象
                json.loads(value)
                return True

            else:
                return False

        except (ValueError, json.JSONDecodeError):
            return False

    def infer_type_from_value(self, value: Any) -> ConfigType:
        """
        从值推断配置类型

        Args:
            value: 任意类型值

        Returns:
            ConfigType: 推断的配置类型
        """
        if isinstance(value, bool):
            return ConfigType.BOOLEAN
        elif isinstance(value, int):
            return ConfigType.INTEGER
        elif isinstance(value, float):
            return ConfigType.FLOAT
        elif isinstance(value, str):
            # 字符串可能是数字或布尔值
            if value.lower() in ("true", "false", "yes", "no", "on", "off", "enabled", "disabled"):
                return ConfigType.BOOLEAN
            try:
                int(value)
                return ConfigType.INTEGER
            except ValueError:
                try:
                    float(value)
                    return ConfigType.FLOAT
                except ValueError:
                    # 检查是否为JSON
                    if value.strip() and (value.strip().startswith("{") or value.strip().startswith("[")):
                        try:
                            json.loads(value)
                            return ConfigType.JSON
                        except json.JSONDecodeError:
                            pass
                    return ConfigType.STRING
        elif isinstance(value, (dict, list)):
            return ConfigType.JSON
        else:
            # 默认转换为字符串
            return ConfigType.STRING

    # =========================================================================
    # 缓存管理（可选）
    # =========================================================================

    def clear_cache(self) -> None:
        """清除配置缓存"""
        self._logger.info("Clearing config cache")
        self._cache.clear()

    def reload_cache(self) -> None:
        """重新加载配置缓存"""
        self._logger.info("Reloading config cache")
        self._cache.clear()

        if not self._cache_enabled:
            return

        try:
            configs = self.list_all(limit=1000)  # 加载所有配置到缓存
            for config in configs:
                self._cache[config.key] = config
            self._logger.info(f"Loaded {len(configs)} configs into cache")
        except SystemConfigError as e:
            self._logger.error(f"Failed to reload cache: {e}")

    def is_cache_enabled(self) -> bool:
        """检查缓存是否启用"""
        return self._cache_enabled

    def set_cache_enabled(self, enabled: bool) -> None:
        """设置缓存启用状态"""
        self._logger.info(f"Setting cache enabled to: {enabled}")
        self._cache_enabled = enabled

        if not enabled:
            self._cache.clear()

    # =========================================================================
    # 统计和报表
    # =========================================================================

    def get_statistics(self) -> Dict[str, Any]:
        """
        获取配置统计信息

        Returns:
            Dict[str, Any]: 统计信息
        """
        self._logger.debug("Getting config statistics")

        try:
            # 获取类型分布
            type_distribution = self.get_type_distribution()

            # 获取总数
            total_count = self.count()

            # 获取最新更新时间
            sql = """
            SELECT MAX(updated_at) as latest_update,
                   MIN(created_at) as earliest_create,
                   COUNT(DISTINCT config_key) as unique_keys
            FROM system_config
            """
            result = self._db.query(sql, ())
            row = dict(list(result)[0])

            return {
                "total_count": total_count,
                "type_distribution": type_distribution,
                "latest_update": row["latest_update"],
                "earliest_create": row["earliest_create"],
                "unique_keys": int(row["unique_keys"]),
                "cache_enabled": self._cache_enabled,
                "cache_size": len(self._cache),
            }

        except DatabaseError as e:
            raise SystemConfigError(f"Failed to get statistics: {e}") from e

    def get_type_distribution(self) -> Dict[str, int]:
        """
        获取类型分布统计

        Returns:
            Dict[str, int]: 类型->数量映射
        """
        self._logger.debug("Getting config type distribution")

        sql = """
        SELECT config_type, COUNT(*) as count
        FROM system_config
        GROUP BY config_type
        ORDER BY config_type
        """

        try:
            result = self._db.query(sql, ())
            distribution: Dict[str, int] = {}

            for row in result:
                config_type = str(row["config_type"])
                count = int(row["count"])
                distribution[config_type] = count

            return distribution

        except DatabaseError as e:
            raise SystemConfigError(f"Failed to get type distribution: {e}") from e

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
            raise SystemConfigError(f"Failed to get last insert ID: {e}") from e

    def _serialize_value(self, value: Any) -> str:
        """序列化值为字符串"""
        if isinstance(value, str):
            return value
        elif isinstance(value, (int, float)):
            return str(value)
        elif isinstance(value, bool):
            return "true" if value else "false"
        elif isinstance(value, (dict, list)):
            return json.dumps(value, ensure_ascii=False)
        else:
            # 默认转换为字符串
            return str(value)

    def _deserialize_value(self, value_str: str, value_type: ConfigType) -> Any:
        """反序列化字符串为指定类型值"""
        try:
            if value_type == ConfigType.STRING:
                return value_str
            elif value_type == ConfigType.INTEGER:
                return int(value_str)
            elif value_type == ConfigType.FLOAT:
                return float(value_str)
            elif value_type == ConfigType.BOOLEAN:
                return value_str.lower() in ("true", "1", "yes", "on", "enabled")
            elif value_type == ConfigType.JSON:
                return json.loads(value_str) if value_str else {}
            else:
                return value_str
        except (ValueError, json.JSONDecodeError) as e:
            raise ConfigValueError(
                f"Failed to deserialize value '{value_str}' with type '{value_type}': {e}"
            ) from e


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