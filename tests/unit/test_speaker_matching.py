"""A SpeakerRegistrationService matching-logikájának egységtesztjei — hard
constraint #4/#5 (docs/phase1-terv.md 6. szakasz): sosem kényszerít találatot
küszöb alatt vagy üres regisztráció esetén."""
from __future__ import annotations

import pytest

from leiratozo.adapters.speaker_embedding.fake import FakeSpeakerEmbeddingEngine
from leiratozo.adapters.storage.fake import InMemoryProfileStore
from leiratozo.application.speaker_registration_service import SpeakerRegistrationService, cosine_similarity
from leiratozo.domain.models import AudioBuffer, DiarizedSegment, Embedding


def test_cosine_similarity_identical_vectors_is_one():
    emb = Embedding(vector=(1.0, 0.0, 0.0), dim=3)
    assert cosine_similarity(emb, emb) == pytest.approx(1.0)


def test_cosine_similarity_orthogonal_vectors_is_zero():
    a = Embedding(vector=(1.0, 0.0), dim=2)
    b = Embedding(vector=(0.0, 1.0), dim=2)
    assert cosine_similarity(a, b) == pytest.approx(0.0)


def test_cosine_similarity_dimension_mismatch_raises():
    a = Embedding(vector=(1.0, 0.0), dim=2)
    b = Embedding(vector=(1.0, 0.0, 0.0), dim=3)
    with pytest.raises(ValueError):
        cosine_similarity(a, b)


@pytest.fixture
def service() -> SpeakerRegistrationService:
    return SpeakerRegistrationService(
        FakeSpeakerEmbeddingEngine(),
        InMemoryProfileStore(),
        similarity_threshold=0.99,  # szándékosan szigorú, hogy a fake-hash ne "véletlenül" találjon
    )


async def test_match_segments_with_empty_registry_returns_unknown(service: SpeakerRegistrationService):
    audio = AudioBuffer(samples=b"x" * 100, sample_rate=16000, duration_sec=1.0)
    segments = [DiarizedSegment(segment_id="seg-1", start=0.0, end=1.0, speaker_label="S1")]

    matches = await service.match_segments(audio, segments)

    assert matches["seg-1"].known_speaker_id is None
    assert matches["seg-1"].confidence == 0.0


async def test_match_segments_below_threshold_is_unknown_not_forced(service: SpeakerRegistrationService):
    audio = AudioBuffer(samples=b"enrollment-sample", sample_rate=16000, duration_sec=2.0)
    profile = await service.register(audio, display_name="Teszt Elek")

    segments = [DiarizedSegment(segment_id="seg-1", start=0.0, end=1.0, speaker_label="S1")]
    matches = await service.match_segments(audio, segments)

    # A fake embedding a szegmens speaker_label-jéből, az enrollment pedig az
    # audio bájtjaiból hash-el — ezek nem egyeznek, tehát a küszöb alatt marad.
    assert matches["seg-1"].known_speaker_id is None
    assert matches["seg-1"].known_speaker_id != profile.profile_id


async def test_delete_unknown_profile_raises():
    from leiratozo.domain.errors import ProfileNotFoundError

    service = SpeakerRegistrationService(
        FakeSpeakerEmbeddingEngine(), InMemoryProfileStore(), similarity_threshold=0.7
    )
    with pytest.raises(ProfileNotFoundError):
        await service.delete("spk_does-not-exist")


async def test_register_then_list_then_delete_round_trip():
    service = SpeakerRegistrationService(
        FakeSpeakerEmbeddingEngine(), InMemoryProfileStore(), similarity_threshold=0.7
    )
    audio = AudioBuffer(samples=b"sample", sample_rate=16000, duration_sec=3.0)

    profile = await service.register(audio, display_name="Kovács Anna")
    assert (await service.list_profiles())[0].profile_id == profile.profile_id

    await service.delete(profile.profile_id)
    assert await service.list_profiles() == []
