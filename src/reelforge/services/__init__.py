"""Services layer (External APIs) - External service clients."""

try:
    from .tts_client import (
        TTSClient,
        VoiceProfile,
        TTSError,
        TimeoutError,
        VoiceNotFoundError,
    )
except ImportError:
    # Fallback during development
    pass

__all__ = [
    "TTSClient",
    "VoiceProfile",
    "TTSError",
    "TimeoutError",
    "VoiceNotFoundError",
]