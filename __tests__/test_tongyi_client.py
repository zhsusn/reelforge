"""
文件：__tests__/test_tongyi_client.py
职责：TongyiClient 模块单元测试（覆盖率 > 80%）
"""

from __future__ import annotations

import json
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, List
from unittest.mock import MagicMock, Mock, patch

import httpx
import pytest

import sys

sys.path.insert(0, "src")

from reelforge.services.tongyi_client import (
    APIError,
    CharacterMismatchError,
    FaceDetectionError,
    ImageGenerationResult,
    QuotaExceededError,
    TongyiClient,
)

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_api_key() -> str:
    """模拟API密钥"""
    return "test_tongyi_api_key_1234567890abcdef"


@pytest.fixture
def mock_base_url() -> str:
    """模拟基础URL"""
    return "https://api.test.dashscope.aliyuncs.com"


@pytest.fixture
def mock_first_frame_image() -> Path:
    """模拟首帧图片路径"""
    # 创建临时图片文件
    temp_dir = Path(tempfile.mkdtemp())
    image_path = temp_dir / "first_frame.png"
    # 写入一些模拟数据
    image_path.write_bytes(b"fake_image_data")
    return image_path


@pytest.fixture
def mock_text_to_image_response() -> Dict[str, Any]:
    """模拟文本到图像API响应"""
    return {
        "output": {
            "task_id": "task_123456",
            "task_status": "SUCCEEDED",
            "image_url": "https://dashscope.aliyuncs.com/images/generated.png",
        },
        "usage": {"image_count": 1, "request_id": "req_789012"},
    }


@pytest.fixture
def mock_quota_response() -> Dict[str, Any]:
    """模拟配额API响应"""
    return {
        "remaining": 1500,
        "total": 2000,
        "period": "daily",
        "reset_at": "2026-04-04T00:00:00Z",
    }


@pytest.fixture
def tongyi_client(
    mock_api_key: str, mock_base_url: str
) -> TongyiClient:
    """提供TongyiClient实例"""
    client = TongyiClient(api_key=mock_api_key, base_url=mock_base_url)
    # 等待后台初始化完成
    time.sleep(0.1)
    return client


# =============================================================================
# 单元测试：初始化与属性
# =============================================================================


def test_tongyi_client_initialization(
    mock_api_key: str, mock_base_url: str
) -> None:
    """测试TongyiClient初始化"""
    client = TongyiClient(api_key=mock_api_key, base_url=mock_base_url)

    # 检查属性
    assert client.api_key == f"{mock_api_key[:4]}...{mock_api_key[-4:]}"
    assert client.base_url == mock_base_url
    assert client.similarity_threshold == 90.0

    # 检查模型信息
    model_info = client.get_model_info()
    assert model_info["model"] == "wanx-v1"
    assert model_info["provider"] == "Alibaba Cloud"
    assert "text2image" in model_info["capabilities"]


def test_api_key_property_masked(mock_api_key: str) -> None:
    """测试API密钥属性（掩码显示）"""
    client = TongyiClient(api_key=mock_api_key)

    # 检查掩码格式
    masked_key = client.api_key
    assert masked_key.startswith(mock_api_key[:4])
    assert masked_key.endswith(mock_api_key[-4:])
    assert "..." in masked_key

    # 测试过短密钥
    short_key = "abc"
    client2 = TongyiClient(api_key=short_key)
    assert client2.api_key == "***"


# =============================================================================
# 单元测试：首帧锁定生成
# =============================================================================


@patch("httpx.Client")
def test_generate_with_first_frame_success(
    mock_client_class: MagicMock,
    tongyi_client: TongyiClient,
    mock_first_frame_image: Path,
    mock_text_to_image_response: Dict[str, Any],
) -> None:
    """测试成功使用首帧锁定生成图片"""
    # 模拟HTTP响应
    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 200
    mock_response.json.return_value = mock_text_to_image_response

    # 模拟下载图片响应
    mock_image_response = MagicMock(spec=httpx.Response)
    mock_image_response.status_code = 200
    mock_image_response.content = b"fake_generated_image_data"

    mock_client = MagicMock()
    mock_client.__enter__.return_value = mock_client
    mock_client.__exit__.return_value = None
    mock_client.post.return_value = mock_response
    mock_client.get.return_value = mock_image_response
    mock_client_class.return_value = mock_client

    # 调用方法
    prompt = "一个年轻人在公园里散步，阳光明媚，表情愉快"
    generated_path = tongyi_client.generate_with_first_frame(prompt, mock_first_frame_image)

    # 验证结果
    assert isinstance(generated_path, Path)
    assert generated_path.exists()

    # 验证API调用
    mock_client.post.assert_called_once()
    call_args = mock_client.post.call_args
    assert call_args[0][0] == "/api/v1/services/aigc/text2image/image-synthesis"
    json_data = call_args[1]["json"]
    assert json_data["model"] == "wanx-v1"
    assert "prompt" in json_data["input"]


@patch("httpx.Client")
def test_generate_with_first_frame_quota_exceeded(
    mock_client_class: MagicMock,
    tongyi_client: TongyiClient,
    mock_first_frame_image: Path,
) -> None:
    """测试积分耗尽异常"""
    # 模拟429响应
    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 429
    mock_response.text = "Quota exceeded"
    mock_response.json.return_value = {
        "error": {"message": "Daily quota exceeded", "type": "quota_error"}
    }
    mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
        "Quota exceeded", request=MagicMock(), response=mock_response
    )

    mock_client = MagicMock()
    mock_client.__enter__.return_value = mock_client
    mock_client.__exit__.return_value = None
    mock_client.post.return_value = mock_response
    mock_client_class.return_value = mock_client

    # 调用方法，应抛出QuotaExceededError
    prompt = "测试提示词"
    with pytest.raises(QuotaExceededError) as exc_info:
        tongyi_client.generate_with_first_frame(prompt, mock_first_frame_image)

    assert "积分已耗尽" in str(exc_info.value)
    assert exc_info.value.status_code == 429


def test_generate_with_first_frame_file_not_found(
    tongyi_client: TongyiClient,
) -> None:
    """测试首帧图片不存在异常"""
    non_existent_path = Path("/nonexistent/path/first_frame.png")
    prompt = "测试提示词"

    with pytest.raises(FileNotFoundError) as exc_info:
        tongyi_client.generate_with_first_frame(prompt, non_existent_path)

    assert "不存在" in str(exc_info.value)


# =============================================================================
# 单元测试：角色一致性验证
# =============================================================================


def test_validate_character_consistency_success(
    tongyi_client: TongyiClient,
) -> None:
    """测试成功验证角色一致性"""
    # 创建模拟图片
    temp_dir = Path(tempfile.mkdtemp())
    images = []
    for i in range(3):
        img_path = temp_dir / f"image_{i}.png"
        img_path.write_bytes(f"fake_image_data_{i}".encode())
        images.append(img_path)

    # 模拟人脸特征提取返回非空结果
    with patch.object(tongyi_client, "_extract_face_features") as mock_extract:
        mock_extract.return_value = {
            "features": [0.1, 0.2, 0.3],
            "face_detected": True,
            "image_hash": "test_hash"
        }

        # 调用方法
        similarity = tongyi_client.validate_character_consistency(images)

        # 验证结果
        assert 0 <= similarity <= 100
        assert isinstance(similarity, float)


def test_validate_character_consistency_not_enough_images(
    tongyi_client: TongyiClient,
) -> None:
    """测试图片数量不足异常"""
    temp_dir = Path(tempfile.mkdtemp())
    single_image = temp_dir / "single.png"
    single_image.write_bytes(b"fake_image_data")

    with pytest.raises(ValueError) as exc_info:
        tongyi_client.validate_character_consistency([single_image])

    assert "需要至少2张图片" in str(exc_info.value)


def test_validate_character_consistency_face_detection_error(
    tongyi_client: TongyiClient,
) -> None:
    """测试人脸检测失败异常"""
    # 创建模拟图片
    temp_dir = Path(tempfile.mkdtemp())
    images = []
    for i in range(2):
        img_path = temp_dir / f"image_{i}.png"
        img_path.write_bytes(f"fake_image_data_{i}".encode())
        images.append(img_path)

    # 模拟人脸特征提取返回None（检测失败）
    with patch.object(tongyi_client, "_extract_face_features") as mock_extract:
        mock_extract.return_value = None

        with pytest.raises(FaceDetectionError) as exc_info:
            tongyi_client.validate_character_consistency(images)

        assert "无法从图片检测人脸" in str(exc_info.value)


def test_validate_character_consistency_file_not_found(
    tongyi_client: TongyiClient,
) -> None:
    """测试图片不存在异常"""
    temp_dir = Path(tempfile.mkdtemp())
    existing_image = temp_dir / "existing.png"
    existing_image.write_bytes(b"fake_data")
    non_existent_image = Path("/nonexistent/path/image.png")

    with pytest.raises(FileNotFoundError) as exc_info:
        tongyi_client.validate_character_consistency([existing_image, non_existent_image])

    assert "不存在" in str(exc_info.value)


# =============================================================================
# 单元测试：积分查询
# =============================================================================


@patch("httpx.Client")
def test_get_quota_remaining_success(
    mock_client_class: MagicMock,
    tongyi_client: TongyiClient,
    mock_quota_response: Dict[str, Any],
) -> None:
    """测试成功获取剩余积分"""
    # 模拟HTTP响应
    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 200
    mock_response.json.return_value = mock_quota_response

    mock_client = MagicMock()
    mock_client.__enter__.return_value = mock_client
    mock_client.__exit__.return_value = None
    mock_client.get.return_value = mock_response
    mock_client_class.return_value = mock_client

    # 调用方法
    remaining = tongyi_client.get_quota_remaining()

    # 验证结果
    assert isinstance(remaining, int)
    assert remaining == 1500

    # 验证API调用
    mock_client.get.assert_called_once_with("/api/v1/quotas/remaining")


@patch("httpx.Client")
def test_get_quota_remaining_api_error(
    mock_client_class: MagicMock,
    tongyi_client: TongyiClient,
) -> None:
    """测试获取积分API错误"""
    # 模拟500响应
    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 500
    mock_response.text = "Internal server error"

    mock_client = MagicMock()
    mock_client.__enter__.return_value = mock_client
    mock_client.__exit__.return_value = None
    mock_client.get.return_value = mock_response
    mock_client_class.return_value = mock_client

    # 调用方法，应抛出APIError
    with pytest.raises(APIError) as exc_info:
        tongyi_client.get_quota_remaining()

    assert "获取积分失败" in str(exc_info.value)
    assert exc_info.value.status_code == 500


# =============================================================================
# 单元测试：降级策略
# =============================================================================


@patch("httpx.Client")
def test_generate_with_style_fallback_success(
    mock_client_class: MagicMock,
    tongyi_client: TongyiClient,
    mock_text_to_image_response: Dict[str, Any],
) -> None:
    """测试成功降级生成"""
    # 模拟HTTP响应
    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 200
    mock_response.json.return_value = mock_text_to_image_response

    # 模拟下载图片响应
    mock_image_response = MagicMock(spec=httpx.Response)
    mock_image_response.status_code = 200
    mock_image_response.content = b"fake_fallback_image_data"

    mock_client = MagicMock()
    mock_client.__enter__.return_value = mock_client
    mock_client.__exit__.return_value = None
    mock_client.post.return_value = mock_response
    mock_client.get.return_value = mock_image_response
    mock_client_class.return_value = mock_client

    # 调用方法
    prompt = "一个老年人在书房里看书，光线柔和，表情专注"
    style_description = "写实风格，油画质感"
    generated_path = tongyi_client.generate_with_style_fallback(prompt, style_description)

    # 验证结果
    assert isinstance(generated_path, Path)
    assert generated_path.exists()

    # 验证API调用
    mock_client.post.assert_called_once()
    json_data = mock_client.post.call_args[1]["json"]
    assert json_data["model"] == "wanx-v1"
    assert "写实风格" in json_data["input"]["prompt"]


# =============================================================================
# 单元测试：异常类
# =============================================================================


def test_api_error_exception() -> None:
    """测试APIError异常"""
    error = APIError("测试错误", status_code=400, response_data={"key": "value"})

    assert str(error) == "测试错误"
    assert error.message == "测试错误"
    assert error.status_code == 400
    assert error.response_data == {"key": "value"}


def test_character_mismatch_error_inheritance() -> None:
    """测试CharacterMismatchError继承关系"""
    error = CharacterMismatchError("角色不匹配", status_code=400)

    assert isinstance(error, APIError)
    assert isinstance(error, CharacterMismatchError)
    assert error.message == "角色不匹配"
    assert error.status_code == 400


def test_face_detection_error_inheritance() -> None:
    """测试FaceDetectionError继承关系"""
    error = FaceDetectionError("人脸检测失败")

    assert isinstance(error, APIError)
    assert isinstance(error, FaceDetectionError)
    assert error.message == "人脸检测失败"


def test_quota_exceeded_error_inheritance() -> None:
    """测试QuotaExceededError继承关系"""
    error = QuotaExceededError("积分耗尽", status_code=429)

    assert isinstance(error, APIError)
    assert isinstance(error, QuotaExceededError)
    assert error.message == "积分耗尽"
    assert error.status_code == 429


# =============================================================================
# 单元测试：私有辅助方法
# =============================================================================


def test_simplify_prompt_for_fallback(tongyi_client: TongyiClient) -> None:
    """测试简化提示词用于降级生成"""
    original = "一个年轻人在公园里散步，确保角色一致，相同的脸部特征"
    simplified = tongyi_client._simplify_prompt_for_fallback(original)

    assert "确保角色一致" not in simplified
    assert "相同的脸部特征" not in simplified
    assert "一个年轻人在公园里散步" in simplified


def test_extract_style_from_image(tongyi_client: TongyiClient) -> None:
    """测试从图片提取风格描述"""
    temp_path = Path(tempfile.mktemp(suffix=".png"))
    temp_path.write_bytes(b"fake_image_data")

    style = tongyi_client._extract_style_from_image(temp_path)
    assert isinstance(style, str)
    assert len(style) > 0

    # 清理临时文件
    temp_path.unlink()


def test_build_headers(tongyi_client: TongyiClient) -> None:
    """测试构建请求头"""
    headers = tongyi_client._build_headers()
    assert isinstance(headers, dict)
    assert "Authorization" in headers
    assert "Content-Type" in headers
    assert headers["Content-Type"] == "application/json"
    assert headers["Accept"] == "application/json"
    assert "Bearer" in headers["Authorization"]


def test_handle_http_error_quota_exceeded(tongyi_client: TongyiClient) -> None:
    """测试处理HTTP 429错误（积分耗尽）"""
    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 429
    mock_response.json.return_value = {
        "error": {"message": "Daily quota exceeded", "type": "quota_error"}
    }

    error = httpx.HTTPStatusError(
        "Quota exceeded", request=MagicMock(), response=mock_response
    )

    # 应该抛出QuotaExceededError
    with pytest.raises(QuotaExceededError) as exc_info:
        tongyi_client._handle_http_error(error)

    assert "积分已耗尽" in str(exc_info.value)
    assert exc_info.value.status_code == 429


def test_handle_http_error_face_detection(tongyi_client: TongyiClient) -> None:
    """测试处理人脸检测相关错误"""
    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 400
    mock_response.text = "Face detection failed: no face found"
    # 模拟JSON响应
    mock_response.json.return_value = {
        "error": {
            "message": "Face detection failed: no face found"
        }
    }

    error = httpx.HTTPStatusError(
        "Face detection failed", request=MagicMock(), response=mock_response
    )

    # 应该抛出FaceDetectionError
    with pytest.raises(FaceDetectionError) as exc_info:
        tongyi_client._handle_http_error(error)

    assert "人脸检测失败" in str(exc_info.value)
    assert exc_info.value.status_code == 400