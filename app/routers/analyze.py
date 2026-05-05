from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from app.routers.sentences import BY_ID
from app.schemas.analysis import Advice, AnalysisResponse
from app.services import aligner, coach, detector, stt

router = APIRouter(tags=["analyze"])

@router.post("/analyze", response_model=AnalysisResponse)
async def analyze(
    audio: UploadFile = File(...),
    sentence_id: str = Form(...),
) -> AnalysisResponse:
    sentence = BY_ID.get(sentence_id)
    if sentence is None:
        raise HTTPException(status_code=404, detail="존재하지 않는 문장 ID 입니다.")

    audio_bytes = await audio.read()
    transcript = stt.transcribe(audio_bytes, filename=audio.filename or "audio.webm")
    alignment = aligner.align(sentence.text, transcript)
    candidates = detector.detect_candidates(alignment)
    advice = coach.coach(sentence.text, transcript, candidates)

    return AnalysisResponse(
        transcript=transcript,
        alignment=alignment,
        candidates=candidates,
        advice=Advice(**advice),
    )
