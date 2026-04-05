"""
Database 模块接口定义（Type Spec）
版本：v1.0（冻结待确认）
项目：ReelForge M02 Pilot
文件映射：
  - exceptions.py: 异常体系
  - connection.py: Database主类 + 类型定义
  - pool.py: ConnectionPool类
  - transaction.py: Transaction类
确认方式：回复"确认接口定义，进入P2.4"或"修改[具体建议]"
"""

from __future__ import annotations

import sqlite3
import threading
from pathlib import Path
from types import TracebackType
from typing import Any, Iterator, Optional, Union, final

# =============================================================================
# File: exceptions.py
# 说明：异常定义，无依赖，被其他所有模块导入
# =============================================================================

class DatabaseError(Exception):
    """基础数据库异常
    
    Args:
        message: 错误信息
        original_error: 原始异常（包装用）
    """
    
    def __init__(
        self, 
        message: str, 
        original_error: Optional[Exception] = None
    ) -> None:
        super().__init__(message)
        self.message = message
        self.original_error = original_error

class ConnectionError(DatabaseError):
    """连接失败异常（数据库文件损坏、锁定等）"""
    pass

class TransactionError(DatabaseError):
    """事务执行异常"""
    pass

class PoolExhaustedError(DatabaseError):
    """连接池耗尽异常"""
    pass

# =============================================================================
# File: connection.py
# 说明：主数据库类，被 pool.py 和 transaction.py 依赖（类型引用）
# 注意：实现时需避免与 pool/transaction 的循环导入（使用延迟导入或依赖注入）
# =============================================================================

ConnectionConfig = dict[str, Union[str, int, bool]]
"""连接配置类型：{"timeout": 30, "wal_mode": True, "max_connections": 5}"""

QueryResult = Iterator[sqlite3.Row]
"""查询结果类型：行迭代器"""

@final
class Database:
    """SQLite数据库管理主类
    
    职责：
        1. 连接生命周期管理（打开/关闭）
        2. 连接池封装（引用 pool.ConnectionPool）
        3. 基础查询接口（execute/query）
        4. 事务管理（引用 transaction.Transaction）
    
    约束：
        - 函数长度 < 50行（已实现方法需拆分）
        - 圈复杂度 < 10
        - 类型注解 100%
        - 禁止 async/await（THREADING 策略）
    """
    
    def __init__(
        self, 
        db_path: Path, 
        config: Optional[ConnectionConfig] = None
    ) -> None:
        """初始化数据库管理器
        
        Args:
            db_path: 数据库文件路径（不存在自动创建）
            config: 连接配置（可选，默认 WAL 模式开启）
        """
        raise NotImplementedError
    
    def connect(self) -> None:
        """建立连接（初始化连接池）
        
        Raises:
            ConnectionError: 连接失败（路径不可写、文件损坏等）
        """
        raise NotImplementedError
    
    def disconnect(self) -> None:
        """断开所有连接（释放资源）
        
        注意：关闭连接池中的所有连接
        """
        raise NotImplementedError
    
    def is_alive(self) -> bool:
        """检查数据库连接是否有效
        
        Returns:
            bool: 能正常执行 PRAGMA 查询返回 True
        """
        raise NotImplementedError
    
    def execute(self, sql: str, parameters: Optional[tuple[Any, ...]] = None) -> int:
        """执行 SQL（INSERT/UPDATE/DELETE）
        
        Args:
            sql: SQL 语句（使用 ? 占位符防注入）
            parameters: SQL 参数元组
            
        Returns:
            int: 影响的行数（rowcount）
            
        Raises:
            DatabaseError: 执行失败
        """
        raise NotImplementedError
    
    def query(self, sql: str, parameters: Optional[tuple[Any, ...]] = None) -> QueryResult:
        """执行查询（SELECT）返回迭代器
        
        Args:
            sql: SELECT 语句
            parameters: 查询参数
            
        Returns:
            QueryResult: 行迭代器（sqlite3.Row）
        """
        raise NotImplementedError
    
    def query_one(
        self, 
        sql: str, 
        parameters: Optional[tuple[Any, ...]] = None
    ) -> Optional[sqlite3.Row]:
        """执行查询返回单行（或无结果）
        
        Args:
            sql: SELECT 语句
            parameters: 查询参数
            
        Returns:
            Optional[sqlite3.Row]: 单行结果，无结果返回 None
        """
        raise NotImplementedError
    
    def transaction(
        self, 
        isolation_level: Optional[str] = "DEFERRED"
    ) -> Transaction:
        """创建事务上下文
        
        Args:
            isolation_level: 隔离级别（DEFERRED/IMMEDIATE/EXCLUSIVE）
            
        Returns:
            Transaction: 事务上下文管理器
        """
        raise NotImplementedError
    
    @property
    def pool(self) -> ConnectionPool:
        """获取连接池实例（只读）"""
        raise NotImplementedError
    
    @property
    def db_path(self) -> Path:
        """获取数据库路径（只读）"""
        raise NotImplementedError

# =============================================================================
# File: pool.py
# 说明：连接池实现，依赖 connection.py（导入 ConnectionConfig, DatabaseError）
# =============================================================================

@final
class ConnectionPool:
    """SQLite 连接池（线程安全单例）
    
    约束：
        - 最大连接数默认 5，可配置
        - 获取连接超时默认 30 秒
        - 线程安全（threading.Lock 保护）
    """
    
    _instance: Optional[ConnectionPool] = None
    _lock: threading.Lock = threading.Lock()
    
    def __new__(
        cls, 
        db_path: Path, 
        max_connections: int = 5,
        **config: Any
    ) -> ConnectionPool:
        """单例构造器
        
        Args:
            db_path: 数据库文件路径
            max_connections: 最大连接数（1-10）
            **config: 额外配置（超时、WAL 模式等）
        """
        raise NotImplementedError
    
    def acquire(
        self, 
        timeout: Optional[float] = 30.0
    ) -> sqlite3.Connection:
        """获取连接（阻塞直到可用或超时）
        
        Args:
            timeout: 等待秒数，None 表示无限等待
            
        Returns:
            sqlite3.Connection: 数据库连接
            
        Raises:
            PoolExhaustedError: 超时未获取到连接
        """
        raise NotImplementedError
    
    def release(self, conn: sqlite3.Connection) -> None:
        """释放连接回池
        
        Args:
            conn: 要释放的连接
        """
        raise NotImplementedError
    
    def is_full(self) -> bool:
        """检查连接池是否已满"""
        raise NotImplementedError
    
    def close_all(self) -> None:
        """关闭所有连接（用于程序退出）"""
        raise NotImplementedError

# =============================================================================
# File: transaction.py
# 说明：事务上下文管理器，依赖 connection.py（导入 DatabaseError）
# =============================================================================

@final
class Transaction:
    """事务上下文管理器
    
    使用方式：
        with db.transaction() as tx:
            tx.execute("INSERT...")
            # 自动提交（无异常）或回滚（有异常）
    """
    
    def __init__(
        self, 
        conn: sqlite3.Connection,
        isolation_level: Optional[str] = "DEFERRED"
    ) -> None:
        """
        Args:
            conn: 数据库连接（从池获取）
            isolation_level: 隔离级别（DEFERRED/IMMEDIATE/EXCLUSIVE）
        """
        raise NotImplementedError
    
    def __enter__(self) -> Transaction:
        """进入上下文，BEGIN 事务"""
        raise NotImplementedError
    
    def __exit__(
        self,
        exc_type: Optional[type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[TracebackType]
    ) -> bool:
        """退出上下文，自动提交或回滚
        
        Returns:
            bool: 是否抑制异常（False 表示不抑制，向上抛出）
        """
        raise NotImplementedError
    
    def commit(self) -> None:
        """提交事务"""
        raise NotImplementedError
    
    def rollback(self) -> None:
        """回滚事务"""
        raise NotImplementedError
    
    def execute(
        self, 
        sql: str, 
        parameters: Optional[tuple[Any, ...]] = None
    ) -> sqlite3.Cursor:
        """在事务内执行 SQL"""
        raise NotImplementedError

# =============================================================================
# 导出列表（对应 __init__.py）
# =============================================================================

__all__ = [
    # exceptions.py
    "DatabaseError",
    "ConnectionError",
    "TransactionError",
    "PoolExhaustedError",
    # connection.py
    "Database",
    "ConnectionConfig",
    "QueryResult",
    # pool.py
    "ConnectionPool",
    # transaction.py
    "Transaction",
]