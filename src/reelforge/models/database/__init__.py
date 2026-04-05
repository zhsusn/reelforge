"""
文件：src/reelforge/modules/database/__init__.py
职责：导出 Database 模块所有公共接口
"""

from __future__ import annotations

from .connection import (
    ConnectionConfig,
    Database,
    QueryResult,
)
from .exceptions import (
    ConnectionError,
    DatabaseError,
    PoolExhaustedError,
    TransactionError,
)
from .pool import ConnectionPool
from .transaction import Transaction

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
