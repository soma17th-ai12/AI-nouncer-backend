from io import BytesIO

import imageio_ffmpeg
from pydub import AudioSegment
from pydub.silence import detect_nonsilent

AudioSegment.converter = imageio_ffmpeg.get_ffmpeg_exe()

_SILENCE_MIN_LEN_MS = 300
_SILENCE_THRESH_OFFSET_DB = -16
_HIGHPASS_HZ = 80
_LOWPASS_HZ = 8000
_TARGET_SR = 16000


def _ext_from_filename(filename: str) -> str:
    if "." in filename:
        return filename.rsplit(".", 1)[-1].lower()
    return "webm"


def preprocess(
    audio_bytes: bytes,
    filename: str,
    *,
    denoise: bool,
    trim_silence: bool,
) -> tuple[bytes, str]:
    """raw 오디오 바이트에 노이즈/무음 전처리를 적용해 16kHz mono wav 바이트로 반환합니다."""
    if not audio_bytes:
        raise ValueError("음성 데이터가 비어 있습니다.")
    if not denoise and not trim_silence:
        return audio_bytes, filename

    try:
        seg = AudioSegment.from_file(BytesIO(audio_bytes), format=_ext_from_filename(filename))
    except Exception:
        # 디코딩 실패는 best-effort. STT 호출 자체를 막지 않고 원본을 그대로 반환합니다.
        return audio_bytes, filename

    seg = seg.set_frame_rate(_TARGET_SR).set_channels(1)

    if denoise:
        seg = seg.high_pass_filter(_HIGHPASS_HZ).low_pass_filter(_LOWPASS_HZ)

    if trim_silence:
        ranges = detect_nonsilent(
            seg,
            min_silence_len=_SILENCE_MIN_LEN_MS,
            silence_thresh=seg.dBFS + _SILENCE_THRESH_OFFSET_DB,
        )
        if ranges:
            trimmed = seg[ranges[0][0] : ranges[0][1]]
            for start, end in ranges[1:]:
                trimmed += seg[start:end]
            seg = trimmed

    out = BytesIO()
    seg.export(out, format="wav")
    return out.getvalue(), "audio.wav"
