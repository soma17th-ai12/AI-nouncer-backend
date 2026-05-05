import mimetypes

from openai import OpenAI

from app.config import settings

_client: OpenAI | None = None

def _get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(api_key=settings.openai_api_key)
    return _client

def transcribe(audio_bytes: bytes, filename: str = "audio.webm") -> str:
    if not audio_bytes:
        raise ValueError("음성 데이터가 비어 있습니다.")
    mime, _ = mimetypes.guess_type(filename)
    result = _get_client().audio.transcriptions.create(
        model="whisper-1",
        file=(filename, audio_bytes, mime or "application/octet-stream"),
        language="ko",
    )
    return result.text.strip()
