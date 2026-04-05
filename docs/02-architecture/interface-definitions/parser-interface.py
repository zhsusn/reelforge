"""
Excel Parser 模块接口定义 (Type Spec)
版本：v1.0（草案）
项目：ReelForge
文件映射：`core/parser.py`

职责：Excel文件解析、列名校验、数据清洗
依赖：pandas, openpyxl

状态：Generated（未冻结）
确认方式：运行 mypy 检查，然后可冻结为 parser-interface.v1.locked.py
"""

from __future__ import annotations

import pandas as pd
from dataclasses import dataclass
from pathlib import Path
from typing import Any, List, Optional, Union

# =============================================================================
# 数据模型定义
# =============================================================================

@dataclass
class ScriptLine:
    """剧本行数据模型（对应Excel模板列）"""
    sequence: int           # 序号
    character: str          # 角色名（必填）
    dialogue: str           # 台词（必填）
    emotion: str            # 情绪（必填）
    knowledge: Optional[str] = None      # 知识点（可选）
    camera: Optional[str] = None         # 运镜建议（可选）
    bgm: Optional[str] = None            # BGM建议（可选）
    duration: Optional[float] = None     # 预估时长（秒，可选）

# =============================================================================
# 异常定义
# =============================================================================

class ParserError(Exception):
    """解析器基础异常"""
    def __init__(self, message: str, original_error: Optional[Exception] = None) -> None:
        super().__init__(message)
        self.message = message
        self.original_error = original_error

class ValidationError(ParserError):
    """Excel列名校验失败异常"""
    pass

class FormatError(ParserError):
    """Excel格式错误（文件类型、损坏等）"""
    pass

class EmptyFileError(ParserError):
    """文件为空或只有表头"""
    pass

# =============================================================================
# 主类接口
# =============================================================================

class ExcelParser:
    """
    Excel解析器主类

    职责：
        1. 读取Excel文件并转换为DataFrame
        2. 校验必填列（角色/台词/情绪）
        3. 提取角色列表
        4. 转换为ScriptLine对象列表

    约束：
        - 支持.xlsx和.xls格式
        - 必填列：character, dialogue, emotion
        - 函数长度 < 50行
        - 类型注解 100%
    """

    # 必填列定义
    REQUIRED_COLUMNS: List[str] = ["character", "dialogue", "emotion"]

    def __init__(self) -> None:
        """初始化解析器"""
        raise NotImplementedError

    def parse(self, file_path: Path) -> List[ScriptLine]:
        """
        解析Excel文件

        Args:
            file_path: Excel文件路径

        Returns:
            List[ScriptLine]: 剧本行列表

        Raises:
            FileNotFoundError: 文件不存在
            FormatError: 文件格式不支持或损坏
            ValidationError: 必填列缺失
            EmptyFileError: 文件为空或只有表头
        """
        raise NotImplementedError

    def validate_columns(self, df: pd.DataFrame) -> List[str]:
        """
        校验DataFrame列名

        Args:
            df: pandas DataFrame

        Returns:
            List[str]: 缺失的列名列表，空列表表示校验通过
        """
        raise NotImplementedError

    def extract_roles(self, df: pd.DataFrame) -> List[str]:
        """
        从DataFrame提取角色列表

        Args:
            df: pandas DataFrame，包含character列

        Returns:
            List[str]: 去重后的角色名列表
        """
        raise NotImplementedError

    def to_script_lines(self, df: pd.DataFrame) -> List[ScriptLine]:
        """
        将DataFrame转换为ScriptLine列表

        Args:
            df: pandas DataFrame

        Returns:
            List[ScriptLine]: 转换后的剧本行列表
        """
        raise NotImplementedError

    @staticmethod
    def get_template_columns() -> List[str]:
        """
        获取Excel模板列名列表

        Returns:
            List[str]: 列名列表（包括必填和可选列）
        """
        raise NotImplementedError

# =============================================================================
# 导出列表
# =============================================================================

__all__ = [
    # 数据模型
    "ScriptLine",
    # 异常
    "ParserError",
    "ValidationError",
    "FormatError",
    "EmptyFileError",
    # 主类
    "ExcelParser",
]