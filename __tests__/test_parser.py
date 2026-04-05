"""
文件：__tests__/test_parser.py
职责：Excel Parser 模块单元测试（覆盖率 > 80%）
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Generator

import pandas as pd
import pytest

import sys
sys.path.insert(0, "src")

from reelforge.core.parser import (
    ExcelParser,
    ScriptLine,
    ParserError,
    ValidationError,
    FormatError,
    EmptyFileError,
)


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def parser() -> ExcelParser:
    """提供 ExcelParser 实例"""
    return ExcelParser()


@pytest.fixture
def valid_excel_data() -> pd.DataFrame:
    """提供有效的Excel数据DataFrame"""
    data = {
        "sequence": [1, 2, 3],
        "character": ["小明", "小红", "旁白"],
        "dialogue": ["你好，小红！", "你好，小明！", "这是一个测试剧本。"],
        "emotion": ["开心", "兴奋", "平静"],
        "knowledge": ["知识点1", None, "知识点2"],
        "camera": ["特写", "中景", "全景"],
        "bgm": ["轻快", "欢快", None],
        "duration": [2.5, 3.0, 4.0]
    }
    return pd.DataFrame(data)


@pytest.fixture
def temp_excel_file(valid_excel_data: pd.DataFrame) -> Generator[Path, None, None]:
    """创建临时Excel文件"""
    with tempfile.TemporaryDirectory() as tmpdir:
        file_path = Path(tmpdir) / "test.xlsx"
        valid_excel_data.to_excel(file_path, index=False)
        yield file_path


# =============================================================================
# Test Data Models
# =============================================================================

class TestScriptLine:
    """测试 ScriptLine 数据模型"""

    def test_scriptline_creation(self) -> None:
        """测试创建 ScriptLine 对象"""
        script_line = ScriptLine(
            sequence=1,
            character="小明",
            dialogue="你好！",
            emotion="开心",
            knowledge="知识点",
            camera="特写",
            bgm="轻快",
            duration=2.5
        )

        assert script_line.sequence == 1
        assert script_line.character == "小明"
        assert script_line.dialogue == "你好！"
        assert script_line.emotion == "开心"
        assert script_line.knowledge == "知识点"
        assert script_line.camera == "特写"
        assert script_line.bgm == "轻快"
        assert script_line.duration == 2.5

    def test_scriptline_optional_fields(self) -> None:
        """测试 ScriptLine 可选字段"""
        script_line = ScriptLine(
            sequence=1,
            character="小明",
            dialogue="你好！",
            emotion="开心"
        )

        assert script_line.sequence == 1
        assert script_line.character == "小明"
        assert script_line.dialogue == "你好！"
        assert script_line.emotion == "开心"
        assert script_line.knowledge is None
        assert script_line.camera is None
        assert script_line.bgm is None
        assert script_line.duration is None

    def test_scriptline_string_representation(self) -> None:
        """测试 ScriptLine 字符串表示"""
        script_line = ScriptLine(
            sequence=1,
            character="小明",
            dialogue="你好！",
            emotion="开心"
        )

        repr_str = repr(script_line)
        assert "ScriptLine" in repr_str
        assert "sequence=1" in repr_str
        assert "character='小明'" in repr_str


# =============================================================================
# Test Exceptions
# =============================================================================

class TestExceptions:
    """测试异常体系"""

    def test_parser_error_with_original(self) -> None:
        """测试 ParserError 包装原始异常"""
        original = ValueError("original error")
        err = ParserError("parsing failed", original)

        assert err.message == "parsing failed"
        assert err.original_error is original
        assert str(err) == "parsing failed"

    def test_validation_error_inheritance(self) -> None:
        """测试 ValidationError 继承 ParserError"""
        err = ValidationError("validation failed")
        assert isinstance(err, ParserError)

    def test_format_error_inheritance(self) -> None:
        """测试 FormatError 继承 ParserError"""
        err = FormatError("format error")
        assert isinstance(err, ParserError)

    def test_empty_file_error_inheritance(self) -> None:
        """测试 EmptyFileError 继承 ParserError"""
        err = EmptyFileError("file is empty")
        assert isinstance(err, ParserError)


# =============================================================================
# Test ExcelParser Initialization
# =============================================================================

class TestExcelParserInitialization:
    """测试 ExcelParser 初始化"""

    def test_init_creates_instance(self, parser: ExcelParser) -> None:
        """测试创建 ExcelParser 实例"""
        assert isinstance(parser, ExcelParser)

    def test_required_columns_constant(self, parser: ExcelParser) -> None:
        """测试 REQUIRED_COLUMNS 常量"""
        assert hasattr(parser, 'REQUIRED_COLUMNS')
        assert isinstance(parser.REQUIRED_COLUMNS, list)
        assert len(parser.REQUIRED_COLUMNS) == 3
        assert "character" in parser.REQUIRED_COLUMNS
        assert "dialogue" in parser.REQUIRED_COLUMNS
        assert "emotion" in parser.REQUIRED_COLUMNS


# =============================================================================
# Test Column Validation
# =============================================================================

class TestColumnValidation:
    """测试列名校验"""

    def test_validate_columns_valid(self, parser: ExcelParser, valid_excel_data: pd.DataFrame) -> None:
        """测试有效的列名"""
        missing = parser.validate_columns(valid_excel_data)
        assert missing == []  # 应该为空列表

    def test_validate_columns_missing_one(self, parser: ExcelParser) -> None:
        """测试缺少一个必填列"""
        df = pd.DataFrame({
            "sequence": [1, 2],
            "character": ["小明", "小红"],
            "dialogue": ["你好", "你好"]  # 缺少emotion列
        })

        missing = parser.validate_columns(df)
        assert len(missing) == 1
        assert "emotion" in missing

    def test_validate_columns_missing_all(self, parser: ExcelParser) -> None:
        """测试缺少所有必填列"""
        df = pd.DataFrame({
            "sequence": [1, 2],
            "其他列": ["a", "b"]
        })

        missing = parser.validate_columns(df)
        assert len(missing) == 3
        assert "character" in missing
        assert "dialogue" in missing
        assert "emotion" in missing

    def test_validate_columns_case_insensitive(self, parser: ExcelParser) -> None:
        """测试不区分大小写的列名"""
        df = pd.DataFrame({
            "Character": ["小明", "小红"],  # 大写
            "DIALOGUE": ["你好", "你好"],    # 大写
            "Emotion": ["开心", "开心"]      # 首字母大写
        })

        missing = parser.validate_columns(df)
        assert missing == []  # 应该通过校验

    def test_validate_columns_with_spaces(self, parser: ExcelParser) -> None:
        """测试列名包含空格"""
        df = pd.DataFrame({
            " character ": ["小明", "小红"],  # 前后空格
            "dialogue ": ["你好", "你好"],    # 后面空格
            " emotion": ["开心", "开心"]      # 前面空格
        })

        missing = parser.validate_columns(df)
        assert missing == []  # 应该通过校验


# =============================================================================
# Test Role Extraction
# =============================================================================

class TestRoleExtraction:
    """测试角色提取"""

    def test_extract_roles_valid(self, parser: ExcelParser, valid_excel_data: pd.DataFrame) -> None:
        """测试提取有效角色列表"""
        roles = parser.extract_roles(valid_excel_data)

        assert len(roles) == 3
        assert "小明" in roles
        assert "小红" in roles
        assert "旁白" in roles
        # 检查去重
        assert len(roles) == len(set(roles))

    def test_extract_roles_empty(self, parser: ExcelParser) -> None:
        """测试空角色列"""
        df = pd.DataFrame({
            "character": ["", "", ""],  # 空角色名
            "dialogue": ["a", "b", "c"],
            "emotion": ["x", "y", "z"]
        })

        roles = parser.extract_roles(df)
        assert roles == []  # 应该返回空列表

    def test_extract_roles_mixed_case(self, parser: ExcelParser) -> None:
        """测试混合大小写的列名"""
        df = pd.DataFrame({
            "Character": ["小明", "小红"],  # 大写
            "dialogue": ["a", "b"],
            "emotion": ["x", "y"]
        })

        roles = parser.extract_roles(df)
        assert roles == ["小明", "小红"]

    def test_extract_roles_with_whitespace(self, parser: ExcelParser) -> None:
        """测试角色名包含空格"""
        df = pd.DataFrame({
            "character": [" 小明 ", "小红  ", "  旁白"],  # 前后空格
            "dialogue": ["a", "b", "c"],
            "emotion": ["x", "y", "z"]
        })

        roles = parser.extract_roles(df)
        # 应该去除空格
        assert roles == ["小明", "小红", "旁白"]

    def test_extract_roles_no_character_column(self, parser: ExcelParser) -> None:
        """测试没有character列"""
        df = pd.DataFrame({
            "序列": [1, 2],
            "台词": ["a", "b"],
            "情绪": ["x", "y"]
        })

        roles = parser.extract_roles(df)
        assert roles == []  # 应该返回空列表


# =============================================================================
# Test DataFrame to ScriptLines Conversion
# =============================================================================

class TestDataFrameConversion:
    """测试DataFrame到ScriptLine转换"""

    def test_to_script_lines_valid(self, parser: ExcelParser, valid_excel_data: pd.DataFrame) -> None:
        """测试有效DataFrame转换"""
        script_lines = parser.to_script_lines(valid_excel_data)

        assert len(script_lines) == 3
        assert all(isinstance(sl, ScriptLine) for sl in script_lines)

        # 检查第一个script line
        sl1 = script_lines[0]
        assert sl1.sequence == 1
        assert sl1.character == "小明"
        assert sl1.dialogue == "你好，小红！"
        assert sl1.emotion == "开心"
        assert sl1.knowledge == "知识点1"
        assert sl1.camera == "特写"
        assert sl1.bgm == "轻快"
        assert sl1.duration == 2.5

        # 检查第二个script line（可选字段为None）
        sl2 = script_lines[1]
        assert sl2.knowledge is None  # DataFrame中为None

        # 检查第三个script line
        sl3 = script_lines[2]
        assert sl3.bgm is None  # DataFrame中为None

    def test_to_script_lines_alternative_column_names(self, parser: ExcelParser) -> None:
        """测试替代列名（中文）"""
        df = pd.DataFrame({
            "序号": [1, 2],
            "角色": ["小明", "小红"],
            "台词": ["你好", "你好"],
            "情绪": ["开心", "开心"],
            "知识点": ["k1", "k2"],
            "运镜": ["特写", "中景"],
            "背景音乐": ["b1", "b2"],
            "时长": [1.0, 2.0]
        })

        script_lines = parser.to_script_lines(df)
        assert len(script_lines) == 2

        sl = script_lines[0]
        assert sl.sequence == 1
        assert sl.character == "小明"
        assert sl.dialogue == "你好"
        assert sl.emotion == "开心"
        assert sl.knowledge == "k1"
        assert sl.camera == "特写"
        assert sl.bgm == "b1"
        assert sl.duration == 1.0

    def test_to_script_lines_partial_columns(self, parser: ExcelParser) -> None:
        """测试部分列存在"""
        df = pd.DataFrame({
            "character": ["小明"],
            "dialogue": ["你好"],
            "emotion": ["开心"]
            # 其他列都缺失
        })

        script_lines = parser.to_script_lines(df)
        assert len(script_lines) == 1

        sl = script_lines[0]
        assert sl.sequence == 1  # 默认行号+1
        assert sl.character == "小明"
        assert sl.dialogue == "你好"
        assert sl.emotion == "开心"
        assert sl.knowledge is None
        assert sl.camera is None
        assert sl.bgm is None
        assert sl.duration is None

    def test_to_script_lines_invalid_sequence(self, parser: ExcelParser) -> None:
        """测试无效的序号处理"""
        df = pd.DataFrame({
            "sequence": ["不是数字", 2],  # 第一个不是数字
            "character": ["小明", "小红"],
            "dialogue": ["a", "b"],
            "emotion": ["x", "y"]
        })

        script_lines = parser.to_script_lines(df)
        assert len(script_lines) == 2

        # 第一个应该使用默认行号（1）
        assert script_lines[0].sequence == 1
        # 第二个应该使用提供的数字
        assert script_lines[1].sequence == 2

    def test_to_script_lines_invalid_duration(self, parser: ExcelParser) -> None:
        """测试无效的时长处理"""
        df = pd.DataFrame({
            "character": ["小明", "小红"],
            "dialogue": ["a", "b"],
            "emotion": ["x", "y"],
            "duration": ["不是数字", 2.5]  # 第一个不是数字
        })

        script_lines = parser.to_script_lines(df)
        assert len(script_lines) == 2

        # 第一个duration应该为None
        assert script_lines[0].duration is None
        # 第二个duration应该为2.5
        assert script_lines[1].duration == 2.5

    def test_to_script_lines_empty_strings_to_none(self, parser: ExcelParser) -> None:
        """测试空字符串转换为None"""
        df = pd.DataFrame({
            "character": ["小明"],
            "dialogue": ["你好"],
            "emotion": ["开心"],
            "knowledge": [""],  # 空字符串
            "camera": [" "],    # 空格
            "bgm": [None]       # None
        })

        script_lines = parser.to_script_lines(df)
        sl = script_lines[0]

        # 空字符串和空格应该转换为None
        assert sl.knowledge is None
        assert sl.camera is None
        assert sl.bgm is None


# =============================================================================
# Test Template Columns
# =============================================================================

class TestTemplateColumns:
    """测试模板列功能"""

    def test_get_template_columns_static_method(self) -> None:
        """测试静态方法 get_template_columns"""
        columns = ExcelParser.get_template_columns()

        assert isinstance(columns, list)
        assert len(columns) == 8

        expected_columns = [
            "sequence",
            "character",
            "dialogue",
            "emotion",
            "knowledge",
            "camera",
            "bgm",
            "duration"
        ]

        for col in expected_columns:
            assert col in columns


# =============================================================================
# Test Full Parse Workflow
# =============================================================================

class TestFullParseWorkflow:
    """测试完整解析流程"""

    def test_parse_valid_excel(self, parser: ExcelParser, temp_excel_file: Path) -> None:
        """测试解析有效的Excel文件"""
        script_lines = parser.parse(temp_excel_file)

        assert len(script_lines) == 3
        assert all(isinstance(sl, ScriptLine) for sl in script_lines)

        # 验证解析结果
        assert script_lines[0].character == "小明"
        assert script_lines[1].character == "小红"
        assert script_lines[2].character == "旁白"

    def test_parse_file_not_found(self, parser: ExcelParser) -> None:
        """测试文件不存在"""
        with pytest.raises(FileNotFoundError):
            parser.parse(Path("/nonexistent/file.xlsx"))

    def test_parse_invalid_format(self, parser: ExcelParser, tmp_path: Path) -> None:
        """测试无效文件格式"""
        invalid_file = tmp_path / "test.txt"
        invalid_file.write_text("not an excel file")

        with pytest.raises(FormatError):
            parser.parse(invalid_file)

    def test_parse_empty_excel(self, parser: ExcelParser, tmp_path: Path) -> None:
        """测试空Excel文件"""
        empty_file = tmp_path / "empty.xlsx"
        df = pd.DataFrame()
        df.to_excel(empty_file, index=False)

        with pytest.raises(EmptyFileError):
            parser.parse(empty_file)

    def test_parse_missing_required_columns(self, parser: ExcelParser, tmp_path: Path) -> None:
        """测试缺少必填列的Excel"""
        missing_col_file = tmp_path / "missing.xlsx"
        df = pd.DataFrame({
            "sequence": [1, 2],
            "character": ["小明", "小红"]
            # 缺少dialogue和emotion
        })
        df.to_excel(missing_col_file, index=False)

        with pytest.raises(ValidationError) as exc_info:
            parser.parse(missing_col_file)

        assert "缺少必填列" in str(exc_info.value)

    def test_parse_corrupted_excel(self, parser: ExcelParser, tmp_path: Path) -> None:
        """测试损坏的Excel文件"""
        corrupted_file = tmp_path / "corrupted.xlsx"
        corrupted_file.write_bytes(b"not a valid excel file")

        with pytest.raises(FormatError):
            parser.parse(corrupted_file)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])