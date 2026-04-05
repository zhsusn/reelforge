"""
文件：__tests__/test_deepseek_client.py
职责：DeepSeekClient 模块单元测试（覆盖率 > 80%）
"""

from __future__ import annotations

import json
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, Generator, List
from unittest.mock import MagicMock, Mock, patch

import httpx
import pytest

import sys

sys.path.insert(0, "src")

from reelforge.services.deepseek_client import (
    APIError,
    DeepSeekClient,
    ParseError,
    RateLimitError,
    ShotDescription,
    Storyboard,
    TimeoutError,
)

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_api_key() -> str:
    """模拟API密钥"""
    return "test_api_key_1234567890abcdef"


@pytest.fixture
def mock_base_url() -> str:
    """模拟基础URL"""
    return "https://api.test.deepseek.com"


@pytest.fixture
def mock_storyboard_response() -> Dict[str, Any]:
    """模拟故事板生成的API响应"""
    return {
        "id": "chatcmpl-1234567890",
        "object": "chat.completion",
        "created": 1677652288,
        "model": "deepseek-chat",
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": """这是一个故事板：

```json
{
  "shots": [
    {
      "sequence": 1,
      "scene_description": "清晨，男主角站在窗前，阳光照在他脸上，表情沉思",
      "dialogue": "新的一天开始了...",
      "emotion": "沉思",
      "camera_movement": "推",
      "shot_type": "特写"
    },
    {
      "sequence": 2,
      "scene_description": "办公室场景，女主角在电脑前工作，周围是忙碌的同事",
      "dialogue": "N/A",
      "emotion": "专注",
      "camera_movement": "摇",
      "shot_type": "中景"
    },
    {
      "sequence": 3,
      "scene_description": "会议室，男主角和女主角面对面坐着，表情严肃",
      "dialogue": "我们需要谈谈项目进展...",
      "emotion": "严肃",
      "camera_movement": "固定",
      "shot_type": "近景"
    }
  ],
  "total_duration": 15.5
}
```""",
                },
                "finish_reason": "stop",
            }
        ],
        "usage": {
            "prompt_tokens": 120,
            "completion_tokens": 350,
            "total_tokens": 470,
        },
    }


@pytest.fixture
def mock_stream_response_chunks() -> List[str]:
    """模拟流式响应的chunks"""
    return [
        'data: {"choices":[{"index":0,"delta":{"role":"assistant"},"finish_reason":null}]}\n',
        'data: {"choices":[{"index":0,"delta":{"content":"这是"},"finish_reason":null}]}\n',
        'data: {"choices":[{"index":0,"delta":{"content":"流式"},"finish_reason":null}]}\n',
        'data: {"choices":[{"index":0,"delta":{"content":"响应"},"finish_reason":null}]}\n',
        'data: {"choices":[{"index":0,"delta":{"content":"。"},"finish_reason":null}]}\n',
        "data: [DONE]\n",
    ]


@pytest.fixture
def mock_usage_response() -> Dict[str, Any]:
    """模拟使用情况API响应"""
    return {
        "total_usage": 12500,
        "remaining_quota": 487500,
        "period": "monthly",
        "reset_at": "2026-05-01T00:00:00Z",
    }


@pytest.fixture
def deepseek_client(
    mock_api_key: str, mock_base_url: str
) -> Generator[DeepSeekClient, None, None]:
    """提供DeepSeekClient实例"""
    client = DeepSeekClient(api_key=mock_api_key, base_url=mock_base_url)
    # 等待后台初始化完成
    time.sleep(0.1)
    yield client


# =============================================================================
# 单元测试：初始化与属性
# =============================================================================


def test_deepseek_client_initialization(
    mock_api_key: str, mock_base_url: str
) -> None:
    """测试DeepSeekClient初始化"""
    client = DeepSeekClient(api_key=mock_api_key, base_url=mock_base_url)

    # 检查属性
    assert client.api_key == f"{mock_api_key[:4]}...{mock_api_key[-4:]}"
    assert client.base_url == mock_base_url

    # 检查初始使用统计
    usage = client.get_usage()
    assert isinstance(usage, dict)
    assert "tokens_used" in usage
    assert usage["tokens_used"] == 0


def test_api_key_property_masked(mock_api_key: str) -> None:
    """测试API密钥属性（掩码显示）"""
    client = DeepSeekClient(api_key=mock_api_key)

    # 检查掩码格式
    masked_key = client.api_key
    assert masked_key.startswith(mock_api_key[:4])
    assert masked_key.endswith(mock_api_key[-4:])
    assert "..." in masked_key

    # 测试过短密钥
    short_key = "abc"
    client2 = DeepSeekClient(api_key=short_key)
    assert client2.api_key == "***"


# =============================================================================
# 单元测试：故事板生成
# =============================================================================


@patch("httpx.Client")
def test_generate_storyboard_success(
    mock_client_class: MagicMock,
    deepseek_client: DeepSeekClient,
    mock_storyboard_response: Dict[str, Any],
) -> None:
    """测试成功生成故事板"""
    # 模拟HTTP响应
    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 200
    mock_response.json.return_value = mock_storyboard_response
    mock_response.raise_for_status.return_value = None

    # 模拟客户端
    mock_client = MagicMock()
    mock_client.__enter__.return_value = mock_client
    mock_client.__exit__.return_value = None
    mock_client.post.return_value = mock_response
    mock_client_class.return_value = mock_client

    # 调用方法
    script = "这是一个测试剧本，包含多个场景和对话。"
    roles = ["男主角", "女主角", "配角"]
    storyboard = deepseek_client.generate_storyboard(script, roles)

    # 验证结果
    assert isinstance(storyboard, Storyboard)
    assert len(storyboard.shots) == 3
    assert storyboard.total_duration == 15.5

    # 验证分镜数据
    shot = storyboard.shots[0]
    assert isinstance(shot, ShotDescription)
    assert shot.sequence == 1
    assert "窗前" in shot.scene_description
    assert shot.dialogue == "新的一天开始了..."
    assert shot.emotion == "沉思"
    assert shot.camera_movement == "推"
    assert shot.shot_type == "特写"

    # 验证API调用参数
    mock_client.post.assert_called_once()
    call_args = mock_client.post.call_args
    assert call_args[0][0] == "/v1/chat/completions"

    json_data = call_args[1]["json"]
    assert json_data["model"] == "deepseek-chat"
    assert len(json_data["messages"]) == 2
    assert json_data["messages"][0]["role"] == "system"
    assert json_data["messages"][1]["role"] == "user"
    assert "这是一个测试剧本" in json_data["messages"][1]["content"]


@patch("httpx.Client")
def test_generate_storyboard_rate_limit(
    mock_client_class: MagicMock, deepseek_client: DeepSeekClient
) -> None:
    """测试触发速率限制异常"""
    # 模拟HTTP 429响应
    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 429
    mock_response.text = "Rate limit exceeded"
    mock_response.json.return_value = {
        "error": {"message": "Rate limit exceeded", "type": "rate_limit_error"}
    }
    mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
        "Rate limit", request=MagicMock(), response=mock_response
    )

    mock_client = MagicMock()
    mock_client.__enter__.return_value = mock_client
    mock_client.__exit__.return_value = None
    mock_client.post.return_value = mock_response
    mock_client_class.return_value = mock_client

    # 调用方法，应抛出RateLimitError
    with pytest.raises(RateLimitError) as exc_info:
        deepseek_client.generate_storyboard("测试剧本", ["角色"])

    assert "速率限制" in str(exc_info.value)
    assert exc_info.value.status_code == 429


@patch("httpx.Client")
def test_generate_storyboard_timeout(
    mock_client_class: MagicMock, deepseek_client: DeepSeekClient
) -> None:
    """测试请求超时异常"""
    # 模拟超时异常
    mock_client = MagicMock()
    mock_client.__enter__.return_value = mock_client
    mock_client.__exit__.return_value = None
    mock_client.post.side_effect = httpx.TimeoutException("Request timed out")

    mock_client_class.return_value = mock_client

    # 调用方法，应抛出TimeoutError
    with pytest.raises(TimeoutError) as exc_info:
        deepseek_client.generate_storyboard("测试剧本", ["角色"])

    assert "超时" in str(exc_info.value)


@patch("httpx.Client")
def test_generate_storyboard_parse_error(
    mock_client_class: MagicMock,
    deepseek_client: DeepSeekClient,
    mock_storyboard_response: Dict[str, Any],
) -> None:
    """测试响应解析失败异常"""
    # 模拟无效JSON响应
    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 200
    # 修改响应，移除JSON部分
    bad_response = mock_storyboard_response.copy()
    bad_response["choices"][0]["message"]["content"] = "这不是JSON数据"
    mock_response.json.return_value = bad_response
    mock_response.raise_for_status.return_value = None

    mock_client = MagicMock()
    mock_client.__enter__.return_value = mock_client
    mock_client.__exit__.return_value = None
    mock_client.post.return_value = mock_response
    mock_client_class.return_value = mock_client

    # 调用方法，应抛出ParseError
    with pytest.raises(ParseError) as exc_info:
        deepseek_client.generate_storyboard("测试剧本", ["角色"])

    assert "未找到JSON数据" in str(exc_info.value)


@patch("httpx.Client")
def test_generate_storyboard_invalid_structure(
    mock_client_class: MagicMock,
    deepseek_client: DeepSeekClient,
    mock_storyboard_response: Dict[str, Any],
) -> None:
    """测试无效的故事板数据结构"""
    # 模拟缺少shots字段的响应
    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 200
    bad_response = mock_storyboard_response.copy()
    bad_response["choices"][0]["message"][
        "content"
    ] = '{"not_shots": [], "total_duration": 10}'
    mock_response.json.return_value = bad_response
    mock_response.raise_for_status.return_value = None

    mock_client = MagicMock()
    mock_client.__enter__.return_value = mock_client
    mock_client.__exit__.return_value = None
    mock_client.post.return_value = mock_response
    mock_client_class.return_value = mock_client

    # 调用方法，应抛出ParseError
    with pytest.raises(ParseError) as exc_info:
        deepseek_client.generate_storyboard("测试剧本", ["角色"])

    assert "缺少shots字段" in str(exc_info.value)


# =============================================================================
# 单元测试：流式生成
# =============================================================================


@patch("httpx.Client")
def test_stream_generate_success(
    mock_client_class: MagicMock,
    deepseek_client: DeepSeekClient,
    mock_stream_response_chunks: List[str],
) -> None:
    """测试成功流式生成"""
    # 模拟流式响应
    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 200
    mock_response.raise_for_status.return_value = None

    # 模拟iter_lines方法
    mock_response.iter_lines.return_value = iter(mock_stream_response_chunks)

    # 模拟stream方法（返回上下文管理器）
    mock_stream_context = MagicMock()
    mock_stream_context.__enter__.return_value = mock_response
    mock_stream_context.__exit__.return_value = None

    mock_client = MagicMock()
    mock_client.__enter__.return_value = mock_client
    mock_client.__exit__.return_value = None
    mock_client.stream.return_value = mock_stream_context
    mock_client_class.return_value = mock_client

    # 调用流式生成
    script = "流式生成测试剧本"
    chunks = list(deepseek_client.stream_generate(script))

    # 验证结果
    assert len(chunks) == 4  # 排除role和DONE
    assert "".join(chunks) == "这是流式响应。"

    # 验证API调用
    mock_client.stream.assert_called_once()
    call_args = mock_client.stream.call_args
    assert call_args[0][0] == "POST"
    assert call_args[0][1] == "/v1/chat/completions"

    json_data = call_args[1]["json"]
    assert json_data["stream"] is True
    assert "流式生成测试剧本" in json_data["messages"][0]["content"]


@patch("httpx.Client")
def test_stream_generate_timeout(
    mock_client_class: MagicMock, deepseek_client: DeepSeekClient
) -> None:
    """测试流式生成超时异常"""
    # 模拟超时：stream方法返回上下文管理器，__enter__时抛出TimeoutException
    mock_stream_context = MagicMock()
    mock_stream_context.__enter__.side_effect = httpx.TimeoutException("Stream timeout")
    mock_stream_context.__exit__.return_value = None

    mock_client = MagicMock()
    mock_client.__enter__.return_value = mock_client
    mock_client.__exit__.return_value = None
    mock_client.stream.return_value = mock_stream_context
    mock_client_class.return_value = mock_client

    # 调用方法，应抛出TimeoutError
    with pytest.raises(TimeoutError) as exc_info:
        list(deepseek_client.stream_generate("测试剧本"))

    assert "超时" in str(exc_info.value)


# =============================================================================
# 单元测试：API密钥验证
# =============================================================================


@patch("httpx.Client")
def test_validate_key_success(
    mock_client_class: MagicMock,
    deepseek_client: DeepSeekClient,
    mock_usage_response: Dict[str, Any],
) -> None:
    """测试API密钥验证成功"""
    # 模拟成功响应
    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 200
    mock_response.json.return_value = mock_usage_response

    mock_client = MagicMock()
    mock_client.__enter__.return_value = mock_client
    mock_client.__exit__.return_value = None
    mock_client.get.return_value = mock_response
    mock_client_class.return_value = mock_client

    # 调用验证方法
    test_key = "test_validate_key"
    is_valid, message = deepseek_client.validate_key(test_key)

    # 验证结果
    assert is_valid is True
    assert "有效" in message
    assert "已用" in message

    # 验证API调用
    mock_client.get.assert_called_once_with("/v1/usage")


@patch("httpx.Client")
def test_validate_key_invalid(mock_client_class: MagicMock, deepseek_client: DeepSeekClient) -> None:
    """测试API密钥验证失败（无效密钥）"""
    # 模拟401响应
    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 401

    mock_client = MagicMock()
    mock_client.__enter__.return_value = mock_client
    mock_client.__exit__.return_value = None
    mock_client.get.return_value = mock_response
    mock_client_class.return_value = mock_client

    # 调用验证方法
    test_key = "invalid_key"
    is_valid, message = deepseek_client.validate_key(test_key)

    # 验证结果
    assert is_valid is False
    assert "无效" in message or "过期" in message


@patch("httpx.Client")
def test_validate_key_timeout(mock_client_class: MagicMock, deepseek_client: DeepSeekClient) -> None:
    """测试API密钥验证超时"""
    # 模拟超时
    mock_client = MagicMock()
    mock_client.__enter__.return_value = mock_client
    mock_client.__exit__.return_value = None
    mock_client.get.side_effect = httpx.TimeoutException("Validation timeout")

    mock_client_class.return_value = mock_client

    # 调用验证方法
    test_key = "test_key"
    is_valid, message = deepseek_client.validate_key(test_key)

    # 验证结果
    assert is_valid is False
    assert "超时" in message or "网络连接" in message


# =============================================================================
# 单元测试：使用情况统计
# =============================================================================


@patch("httpx.Client")
def test_get_usage_with_refresh(
    mock_client_class: MagicMock,
    deepseek_client: DeepSeekClient,
    mock_usage_response: Dict[str, Any],
) -> None:
    """测试获取使用情况（需要刷新）"""
    # 模拟使用情况API响应
    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 200
    mock_response.json.return_value = mock_usage_response

    mock_client = MagicMock()
    mock_client.__enter__.return_value = mock_client
    mock_client.__exit__.return_value = None
    mock_client.get.return_value = mock_response
    mock_client_class.return_value = mock_client

    # 调用get_usage，应该触发刷新
    usage = deepseek_client.get_usage()

    # 验证结果
    assert isinstance(usage, dict)
    assert usage["tokens_used"] == 12500
    assert usage["tokens_remaining"] == 487500
    assert "last_updated" in usage
    assert usage["last_updated"] is not None

    # 验证API调用
    mock_client.get.assert_called_once_with("/v1/usage")


def test_get_usage_cached(deepseek_client: DeepSeekClient) -> None:
    """测试获取使用情况（缓存）"""
    # 首先设置一些使用数据
    deepseek_client._usage_stats = {
        "tokens_used": 5000,
        "tokens_remaining": 495000,
        "last_updated": time.time() - 100,  # 100秒前更新
        "raw_data": {"test": "data"},
    }

    # 调用get_usage，应该返回缓存数据（因为没过期）
    with patch.object(deepseek_client, "_refresh_usage_stats") as mock_refresh:
        usage = deepseek_client.get_usage()

        # 验证使用了缓存，没有调用刷新
        mock_refresh.assert_not_called()

    # 验证返回了缓存数据
    assert usage["tokens_used"] == 5000
    assert usage["tokens_remaining"] == 495000


@patch("httpx.Client")
def test_get_usage_refresh_failed(
    mock_client_class: MagicMock, deepseek_client: DeepSeekClient
) -> None:
    """测试刷新使用情况失败"""
    # 模拟刷新失败
    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 500

    mock_client = MagicMock()
    mock_client.__enter__.return_value = mock_client
    mock_client.__exit__.return_value = None
    mock_client.get.return_value = mock_response
    mock_client_class.return_value = mock_client

    # 设置过期的使用数据
    deepseek_client._usage_stats["last_updated"] = time.time() - 4000  # 超过1小时

    # 调用get_usage，应该尝试刷新但失败，返回缓存数据
    usage = deepseek_client.get_usage()

    # 验证结果
    assert isinstance(usage, dict)
    assert "tokens_used" in usage
    # 即使刷新失败，也应返回现有数据


# =============================================================================
# 单元测试：辅助方法
# =============================================================================


def test_build_storyboard_system_prompt(deepseek_client: DeepSeekClient) -> None:
    """测试构建系统提示"""
    roles = ["男主角", "女主角", "反派"]
    prompt = deepseek_client._build_storyboard_system_prompt(roles)

    # 验证提示内容
    assert isinstance(prompt, str)
    assert "男主角、女主角、反派" in prompt
    assert "电影导演和分镜师" in prompt
    assert "JSON格式" in prompt
    assert "sequence" in prompt
    assert "scene_description" in prompt
    assert "dialogue" in prompt
    assert "emotion" in prompt
    assert "camera_movement" in prompt
    assert "shot_type" in prompt


def test_build_storyboard_user_prompt(deepseek_client: DeepSeekClient) -> None:
    """测试构建用户提示"""
    script = "这是一个测试剧本内容。"
    roles = ["角色A", "角色B"]
    prompt = deepseek_client._build_storyboard_user_prompt(script, roles)

    # 验证提示内容
    assert isinstance(prompt, str)
    assert script in prompt
    assert "角色列表：" in prompt
    assert "- 角色A" in prompt
    assert "- 角色B" in prompt


def test_format_balance_info(deepseek_client: DeepSeekClient) -> None:
    """测试格式化余额信息"""
    # 测试包含total_usage的情况
    usage_data1 = {"total_usage": 15000, "remaining_quota": 485000}
    result1 = deepseek_client._format_balance_info(usage_data1)
    assert "已用: 15000" in result1
    assert "剩余: 485000" in result1

    # 测试包含usage的情况
    usage_data2 = {"usage": {"total_tokens": 500}}
    result2 = deepseek_client._format_balance_info(usage_data2)
    assert "本次调用使用: 500" in result2

    # 测试未知格式
    usage_data3 = {"unknown": "format"}
    result3 = deepseek_client._format_balance_info(usage_data3)
    assert "信息不明确" in result3 or "未知" in result3


def test_handle_http_error_429(deepseek_client: DeepSeekClient) -> None:
    """测试处理HTTP 429错误"""
    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 429
    mock_response.json.return_value = {
        "error": {"message": "Rate limit exceeded", "type": "rate_limit_error"}
    }

    error = httpx.HTTPStatusError(
        "Rate limit", request=MagicMock(), response=mock_response
    )

    # 应该抛出RateLimitError
    with pytest.raises(RateLimitError) as exc_info:
        deepseek_client._handle_http_error(error)

    assert "速率限制" in str(exc_info.value)
    assert exc_info.value.status_code == 429


def test_handle_http_error_401(deepseek_client: DeepSeekClient) -> None:
    """测试处理HTTP 401错误"""
    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 401
    mock_response.text = "Unauthorized"
    mock_response.json.side_effect = json.JSONDecodeError("Invalid JSON", "", 0)

    error = httpx.HTTPStatusError(
        "Unauthorized", request=MagicMock(), response=mock_response
    )

    # 应该抛出APIError
    with pytest.raises(APIError) as exc_info:
        deepseek_client._handle_http_error(error)

    assert "认证失败" in str(exc_info.value)
    assert exc_info.value.status_code == 401


def test_handle_http_error_500(deepseek_client: DeepSeekClient) -> None:
    """测试处理HTTP 500错误"""
    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 500
    mock_response.json.return_value = {
        "error": {"message": "Internal server error"}
    }

    error = httpx.HTTPStatusError(
        "Server error", request=MagicMock(), response=mock_response
    )

    # 应该抛出APIError
    with pytest.raises(APIError) as exc_info:
        deepseek_client._handle_http_error(error)

    assert "服务器错误" in str(exc_info.value)
    assert exc_info.value.status_code == 500


# =============================================================================
# 单元测试：数据模型
# =============================================================================


def test_shot_description_dataclass() -> None:
    """测试ShotDescription数据模型"""
    shot = ShotDescription(
        sequence=1,
        scene_description="测试场景描述",
        dialogue="测试台词",
        emotion="测试情绪",
        camera_movement="推",
        shot_type="特写",
    )

    assert shot.sequence == 1
    assert shot.scene_description == "测试场景描述"
    assert shot.dialogue == "测试台词"
    assert shot.emotion == "测试情绪"
    assert shot.camera_movement == "推"
    assert shot.shot_type == "特写"


def test_storyboard_dataclass() -> None:
    """测试Storyboard数据模型"""
    shots = [
        ShotDescription(
            sequence=1,
            scene_description="场景1",
            dialogue="台词1",
            emotion="情绪1",
            camera_movement="推",
            shot_type="特写",
        ),
        ShotDescription(
            sequence=2,
            scene_description="场景2",
            dialogue="N/A",
            emotion="情绪2",
            camera_movement="摇",
            shot_type="中景",
        ),
    ]

    storyboard = Storyboard(shots=shots, total_duration=10.5)

    assert len(storyboard.shots) == 2
    assert storyboard.total_duration == 10.5
    assert storyboard.shots[0].sequence == 1
    assert storyboard.shots[1].sequence == 2


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


def test_rate_limit_error_inheritance() -> None:
    """测试RateLimitError继承关系"""
    error = RateLimitError("速率限制", status_code=429)

    assert isinstance(error, APIError)
    assert isinstance(error, RateLimitError)
    assert error.message == "速率限制"
    assert error.status_code == 429


def test_timeout_error_inheritance() -> None:
    """测试TimeoutError继承关系"""
    error = TimeoutError("超时错误")

    assert isinstance(error, APIError)
    assert isinstance(error, TimeoutError)
    assert error.message == "超时错误"


def test_parse_error_inheritance() -> None:
    """测试ParseError继承关系"""
    error = ParseError("解析错误", response_data={"raw": "data"})

    assert isinstance(error, APIError)
    assert isinstance(error, ParseError)
    assert error.message == "解析错误"
    assert error.response_data == {"raw": "data"}