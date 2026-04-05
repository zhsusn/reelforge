"""
文件：src/reelforge/modules/database/transaction.py
职责：事务上下文管理器实现
"""

from __future__ import annotations

import sqlite3
from types import TracebackType
from typing import TYPE_CHECKING, Any, Literal, Optional, final

from reelforge.models.database.exceptions import DatabaseError, TransactionError

if TYPE_CHECKING:
    from reelforge.models.database.pool import ConnectionPool


@final
class Transaction:
    """事务上下文管理器
    
    使用方式：
        with db.transaction() as tx:
            tx.execute("INSERT...")
            # 自动提交（无异常）或回滚（有异常）
    """
    
    _VALID_ISOLATION_LEVELS: set[Optional[str]] = {
        "DEFERRED", "IMMEDIATE", "EXCLUSIVE", None
    }
    
    def __init__(
        self, 
        conn: sqlite3.Connection,
        pool: ConnectionPool,
        isolation_level: Optional[str] = "DEFERRED"
    ) -> None:
        """
        Args:
            conn: 数据库连接（从池获取）
            pool: 连接池引用（用于释放连接）
            isolation_level: 隔离级别（DEFERRED/IMMEDIATE/EXCLUSIVE）
            
        Raises:
            TransactionError: 无效的隔离级别
        """
        if isolation_level not in self._VALID_ISOLATION_LEVELS:
            raise TransactionError(
                f"Invalid isolation_level: {isolation_level}. "
                f"Must be one of: {self._VALID_ISOLATION_LEVELS}"
            )
        
        self._conn: sqlite3.Connection = conn
        self._pool: ConnectionPool = pool
        self._isolation_level: Optional[str] = isolation_level
        self._in_transaction: bool = False
        self._completed: bool = False
    
    def __enter__(self) -> Transaction:
        """进入上下文，BEGIN 事务
        
        Returns:
            Transaction: 事务实例
        """
        if self._completed:
            raise TransactionError("Transaction already completed")
        
        try:
            if self._isolation_level:
                self._conn.execute(f"BEGIN {self._isolation_level}")
            else:
                self._conn.execute("BEGIN")
            self._in_transaction = True
        except sqlite3.Error as e:
            raise TransactionError(f"Failed to begin transaction: {e}", e)
        
        return self
    
    def __exit__(
        self,
        exc_type: Optional[type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[TracebackType]
    ) -> Literal[False]:
        """退出上下文，自动提交或回滚
        
        Args:
            exc_type: 异常类型
            exc_val: 异常值
            exc_tb: 异常追踪
            
        Returns:
            bool: 是否抑制异常（False 表示不抑制，向上抛出）
        """
        if not self._in_transaction:
            self._pool.release(self._conn)
            return False
        
        try:
            if exc_type is None:
                self.commit()
            else:
                self.rollback()
        finally:
            self._pool.release(self._conn)
        
        return False
    
    def commit(self) -> None:
        """提交事务
        
        Raises:
            TransactionError: 提交失败
        """
        if not self._in_transaction:
            raise TransactionError("No active transaction to commit")
        
        try:
            self._conn.execute("COMMIT")
            self._in_transaction = False
            self._completed = True
        except sqlite3.Error as e:
            self._completed = True
            raise TransactionError(f"Failed to commit transaction: {e}", e)
    
    def rollback(self) -> None:
        """回滚事务
        
        Raises:
            TransactionError: 回滚失败
        """
        if not self._in_transaction:
            return
        
        try:
            self._conn.execute("ROLLBACK")
            self._in_transaction = False
            self._completed = True
        except sqlite3.Error as e:
            self._completed = True
            raise TransactionError(f"Failed to rollback transaction: {e}", e)
    
    def execute(
        self, 
        sql: str, 
        parameters: Optional[tuple[Any, ...]] = None
    ) -> sqlite3.Cursor:
        """在事务内执行 SQL
        
        Args:
            sql: SQL 语句
            parameters: SQL 参数
            
        Returns:
            sqlite3.Cursor: 游标对象
            
        Raises:
            TransactionError: 执行失败或事务未激活
        """
        if not self._in_transaction:
            raise TransactionError("No active transaction")
        
        try:
            return self._conn.execute(sql, parameters or ())
        except sqlite3.Error as e:
            raise DatabaseError(f"Execute failed: {e}", e)
