"""Domain-szintű hibatípusok. Adapterek és szolgáltatások dobják; az API réteg
felelős a HTTP-státuszkódra/válasz-kontraktusra fordításért. Ld.
docs/phase1-terv.md 10. szakasz (hibaforgatókönyvek)."""
from __future__ import annotations


class LeiratozoError(Exception):
    """Minden domain-szintű hiba őse."""

    error_code: str = "internal_error"


class DecodeError(LeiratozoError):
    """Rossz minőségű / dekódolhatatlan audio."""

    error_code = "decode_error"


class TooShortAudioError(LeiratozoError):
    error_code = "audio_too_short"


class NotSupportedError(LeiratozoError):
    """Egy adapter olyan képességet kapott hívásra, amit nem implementál (pl.
    transcribe_stream egy batch-only ASR engine-en)."""

    error_code = "not_supported"


class ModelUnavailableError(LeiratozoError):
    """Configolt modell/adapter futásidőben nem használható — hiányzó
    licenc-elfogadás, hiányzó token, nem elérhető eszköz, sikertelen betöltés. A
    port regisztrálva marad, de 'degraded'-ként jelzi magát ahelyett, hogy az
    egész szolgáltatást elvinné."""

    error_code = "model_unavailable"


class AdapterNotFoundError(LeiratozoError):
    """Induláskor dobódik, ha egy configolt adapter-azonosító nem oldható fel a
    plugin registryben. Ez fail-fast: a szolgáltatás nem indul el hibás configgal."""

    error_code = "adapter_not_found"


class SessionNotFoundError(LeiratozoError):
    error_code = "session_not_found"


class SessionExpiredError(LeiratozoError):
    error_code = "session_expired"


class ProfileNotFoundError(LeiratozoError):
    error_code = "profile_not_found"
