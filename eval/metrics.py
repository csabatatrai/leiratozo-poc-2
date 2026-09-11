"""Kiértékelési metrikák: WER (leiratozási minőség) és DER (diarizációs
pontosság). Ld. eval/README.md a fogalmakért és a szükséges ground-truth
formátumokért.

WER: tiszta Python, nincs extra függőség — MOST is használható, amint van
referencia-szöveg (nem kell ground-truth diarizáció hozzá).

DER: a `pyannote.metrics` csomagra épül (eval extra: `pip install -e
".[eval]"` a leiratozo pyproject.toml-jában) — ehhez ground-truth RTTM fájl
kell. FIGYELEM: ez a wrapper a pyannote.metrics dokumentált API-ja szerint
készült, de ebben a munkamenetben NEM lett élesen tesztelve (nincs még
ground-truth RTTM-ünk) — az első valós használatkor érdemes ellenőrizni."""
from __future__ import annotations

import re
from dataclasses import dataclass


def normalize_text(text: str) -> str:
    """Kisbetűsít + írásjeleket eltávolít, hogy a WER a tényleges szóhibákat
    mérje, ne az írásjel-/nagybetű-eltéréseket (amik ASR-eknél gyakran csak
    stilisztikai különbségek, nem valódi felismerési hibák)."""
    text = text.lower()
    text = re.sub(r"[^\w\s]", " ", text, flags=re.UNICODE)
    return " ".join(text.split())


def _levenshtein_token_distance(ref: list[str], hyp: list[str]) -> int:
    n, m = len(ref), len(hyp)
    dp = list(range(m + 1))
    for i in range(1, n + 1):
        prev = dp[0]
        dp[0] = i
        for j in range(1, m + 1):
            tmp = dp[j]
            if ref[i - 1] == hyp[j - 1]:
                dp[j] = prev
            else:
                dp[j] = 1 + min(prev, dp[j - 1], dp[j])
            prev = tmp
    return dp[m]


@dataclass(frozen=True)
class WerResult:
    wer: float
    reference_word_count: int
    hypothesis_word_count: int
    edit_distance: int


def word_error_rate(reference: str, hypothesis: str, *, normalize: bool = True) -> WerResult:
    """Szó-szintű hibaarány: szerkesztési távolság (behelyettesítés+törlés+
    beszúrás összevonva) osztva a referencia szóhosszával. 0.0 = tökéletes
    egyezés; 1.0+ = a hipotézis legalább annyira eltér, mint a teljes
    referencia hossza (lehet 1 fölött is, ha sok a beszúrás)."""
    ref_text = normalize_text(reference) if normalize else reference
    hyp_text = normalize_text(hypothesis) if normalize else hypothesis
    ref_words = ref_text.split()
    hyp_words = hyp_text.split()

    distance = _levenshtein_token_distance(ref_words, hyp_words)
    wer = (distance / len(ref_words)) if ref_words else (0.0 if not hyp_words else 1.0)
    return WerResult(
        wer=wer,
        reference_word_count=len(ref_words),
        hypothesis_word_count=len(hyp_words),
        edit_distance=distance,
    )


@dataclass(frozen=True)
class DerResult:
    der: float
    detail: dict


def diarization_error_rate(reference_rttm_path: str, hypothesis_segments: list[dict]) -> DerResult:
    """`hypothesis_segments`: [{"start": float, "end": float, "speaker_label": str}, ...]
    (pontosan a mi DiarizedSegment/TranscriptSegment szerkezetünkből
    kinyerhető). A `reference_rttm_path` egy szabványos RTTM fájl (a
    pyannote/NeMo ökoszisztémában szokásos ground-truth diarizációs formátum).

    NEM tesztelve élesen ebben a munkamenetben — ld. modul docstring."""
    try:
        from pyannote.core import Annotation, Segment
        from pyannote.database.util import load_rttm
        from pyannote.metrics.diarization import DiarizationErrorRate
    except ImportError as exc:
        raise RuntimeError(
            "DER számításhoz a 'pyannote.metrics' (és 'pyannote.database') csomag "
            "szükséges. Telepítés: pip install -e '.[eval]' (ld. pyproject.toml "
            "[eval] extra, majd eval/README.md)."
        ) from exc

    reference_by_uri = load_rttm(reference_rttm_path)
    if not reference_by_uri:
        raise ValueError(f"Az RTTM fájl ({reference_rttm_path}) nem tartalmazott egyetlen annotációt sem")
    reference = next(iter(reference_by_uri.values()))

    hypothesis = Annotation()
    for seg in hypothesis_segments:
        hypothesis[Segment(seg["start"], seg["end"])] = seg["speaker_label"]

    metric = DiarizationErrorRate()
    der_value = metric(reference, hypothesis)
    return DerResult(der=float(der_value), detail=dict(metric[reference, hypothesis]))
