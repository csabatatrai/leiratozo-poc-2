"""Speaker-regisztráció (GDPR) végpontok — docs/phase1-terv.md 6. és 9. szakasz."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, UploadFile
from pydantic import BaseModel

from leiratozo.domain.errors import ProfileNotFoundError

router = APIRouter(prefix="/v1/speakers", tags=["speakers"])


class SpeakerProfileResponse(BaseModel):
    profile_id: str
    display_name: str | None = None


@router.post("", response_model=SpeakerProfileResponse, status_code=201)
async def register_speaker(
    request: Request, file: UploadFile, display_name: str | None = None
) -> SpeakerProfileResponse:
    services = request.app.state.services
    raw_audio = await file.read()
    audio = await services.audio_decoder.decode(raw_audio, filename_hint=file.filename)
    profile = await services.speaker_registration.register(audio, display_name=display_name)
    return SpeakerProfileResponse(profile_id=profile.profile_id, display_name=profile.display_name)


@router.get("", response_model=list[SpeakerProfileResponse])
async def list_speakers(request: Request) -> list[SpeakerProfileResponse]:
    services = request.app.state.services
    profiles = await services.speaker_registration.list_profiles()
    return [SpeakerProfileResponse(profile_id=p.profile_id, display_name=p.display_name) for p in profiles]


@router.delete("/{profile_id}", status_code=204)
async def delete_speaker(request: Request, profile_id: str) -> None:
    services = request.app.state.services
    try:
        await services.speaker_registration.delete(profile_id)
    except ProfileNotFoundError:
        raise HTTPException(status_code=404, detail="profile not found") from None
