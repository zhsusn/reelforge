"""
文件：src/reelforge/modules/database/exceptions.py
职责：定义数据库模块的异常体系，所有外部异常均包装为这些子类
"""

from __future__ import annotations

from typing import Optional


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
