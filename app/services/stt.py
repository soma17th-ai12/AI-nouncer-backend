import mimetypes

from openai import OpenAI

from app.config import settings

STT_PROMPT_NEUTRAL = "한국어 발음 연습 음성입니다. 또박또박 읽어 주세요."

_client: OpenAI | None = None

def _get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(api_key=settings.openai_api_key)
    return _client

def transcribe(
    audio_bytes: bytes,
    filename: str = "audio.webm",
    prompt: str | None = None,
) -> str:
    if not audio_bytes:
        raise ValueError("음성 데이터가 비어 있습니다.")
    mime, _ = mimetypes.guess_type(filename)
    kwargs = {
        "model": "whisper-1",
        "file": (filename, audio_bytes, mime or "application/octet-stream"),
        "language": "ko",
    }
    if prompt:
        kwargs["prompt"] = prompt
    result = _get_client().audio.transcriptions.create(**kwargs)
    return result.text.strip()
