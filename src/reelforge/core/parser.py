"""
Excel Parser 模块实现

文件：src/reelforge/core/parser.py
接口定义：docs/05-coding/interface-definitions/parser-interface.v1.locked.py

职责：Excel文件解析、列名校验、数据清洗
依赖：pandas, openpyxl

实现状态：完全遵循接口定义v1.0
最后更新：2026-04-03
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
# 主类实现
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
        pass

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
        # 检查文件是否存在
        if not file_path.exists():
            raise FileNotFoundError(f"文件不存在：{file_path}")

        # 检查文件扩展名
        if file_path.suffix.lower() not in ['.xlsx', '.xls']:
            raise FormatError(f"不支持的文件格式：{file_path.suffix}。仅支持.xlsx和.xls格式")

        try:
            # 读取Excel文件
            df = pd.read_excel(
                file_path,
                dtype=str,  # 所有列作为字符串读取
                keep_default_na=False  # 不将空单元格转换为NaN
            )
        except Exception as e:
            raise FormatError(f"无法读取Excel文件：{e}", e) from e

        # 检查是否为空文件
        if df.empty:
            raise EmptyFileError("Excel文件为空或只有表头")

        # 校验列名
        missing_cols = self.validate_columns(df)
        if missing_cols:
            raise ValidationError(f"缺少必填列：{missing_cols}")

        # 转换为ScriptLine列表
        script_lines = self.to_script_lines(df)
        return script_lines

    def validate_columns(self, df: pd.DataFrame) -> List[str]:
        """
        校验DataFrame列名

        Args:
            df: pandas DataFrame

        Returns:
            List[str]: 缺失的列名列表，空列表表示校验通过
        """
        # 规范化列名：去除空格、转换为小写
        df_columns = [str(col).strip().lower() for col in df.columns]
        required_columns = [col.strip().lower() for col in self.REQUIRED_COLUMNS]

        missing = []
        for required in required_columns:
            if required not in df_columns:
                missing.append(required)

        return missing

    def extract_roles(self, df: pd.DataFrame) -> List[str]:
        """
        从DataFrame提取角色列表

        Args:
            df: pandas DataFrame，包含character列

        Returns:
            List[str]: 去重后的角色名列表
        """
        # 找到character列（不区分大小写）
        column_map = {str(col).strip().lower(): col for col in df.columns}
        char_col_name = column_map.get('character')

        if not char_col_name:
            # 如果找不到character列，尝试其他常见名称
            possible_names = ['角色', '人物', 'character', 'role']
            for name in possible_names:
                if name in column_map:
                    char_col_name = column_map[name]
                    break

        if not char_col_name:
            return []

        # 提取角色名，去除空值和重复
        roles = df[char_col_name].astype(str).str.strip()
        roles = roles[roles != '']
        roles = roles.unique().tolist()

        return roles

    def to_script_lines(self, df: pd.DataFrame) -> List[ScriptLine]:
        """
        将DataFrame转换为ScriptLine列表

        Args:
            df: pandas DataFrame

        Returns:
            List[ScriptLine]: 转换后的剧本行列表
        """
        script_lines = []

        # 创建列名映射（不区分大小写）
        column_map = {str(col).strip().lower(): col for col in df.columns}

        # 找到各列的实际列名
        seq_col = column_map.get('sequence') or column_map.get('序号')
        char_col = column_map.get('character') or column_map.get('角色')
        dial_col = column_map.get('dialogue') or column_map.get('台词')
        emo_col = column_map.get('emotion') or column_map.get('情绪')
        know_col = column_map.get('knowledge') or column_map.get('知识点')
        cam_col = column_map.get('camera') or column_map.get('运镜')
        bgm_col = column_map.get('bgm') or column_map.get('背景音乐')
        dur_col = column_map.get('duration') or column_map.get('时长')

        for idx, row in df.iterrows():
            try:
                # 序号处理
                sequence = idx + 1  # 默认使用行号
                if seq_col and seq_col in row:
                    seq_val = row[seq_col]
                    if pd.notna(seq_val) and str(seq_val).strip():
                        try:
                            sequence = int(float(str(seq_val).strip()))
                        except (ValueError, TypeError):
                            pass  # 保持默认行号

                # 必填字段处理
                character = str(row[char_col]).strip() if char_col and char_col in row else ''
                dialogue = str(row[dial_col]).strip() if dial_col and dial_col in row else ''
                emotion = str(row[emo_col]).strip() if emo_col and emo_col in row else ''

                # 可选字段处理
                knowledge = None
                if know_col and know_col in row and pd.notna(row[know_col]):
                    knowledge = str(row[know_col]).strip()
                    if knowledge == '':
                        knowledge = None

                camera = None
                if cam_col and cam_col in row and pd.notna(row[cam_col]):
                    camera = str(row[cam_col]).strip()
                    if camera == '':
                        camera = None

                bgm = None
                if bgm_col and bgm_col in row and pd.notna(row[bgm_col]):
                    bgm = str(row[bgm_col]).strip()
                    if bgm == '':
                        bgm = None

                duration = None
                if dur_col and dur_col in row and pd.notna(row[dur_col]):
                    try:
                        duration = float(str(row[dur_col]).strip())
                    except (ValueError, TypeError):
                        duration = None

                # 创建ScriptLine对象
                script_line = ScriptLine(
                    sequence=sequence,
                    character=character,
                    dialogue=dialogue,
                    emotion=emotion,
                    knowledge=knowledge,
                    camera=camera,
                    bgm=bgm,
                    duration=duration
                )

                script_lines.append(script_line)

            except Exception as e:
                # 跳过无法解析的行，但记录错误
                print(f"警告：第{idx+1}行解析失败：{e}")
                continue

        return script_lines

    @staticmethod
    def get_template_columns() -> List[str]:
        """
        获取Excel模板列名列表

        Returns:
            List[str]: 列名列表（包括必填和可选列）
        """
        return [
            "sequence",     # 序号
            "character",    # 角色名（必填）
            "dialogue",     # 台词（必填）
            "emotion",      # 情绪（必填）
            "knowledge",    # 知识点（可选）
            "camera",       # 运镜建议（可选）
            "bgm",          # BGM建议（可选）
            "duration",     # 预估时长（可选）
        ]


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