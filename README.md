# leiratozó

Modellagnosztikus, konfigurálható leiratozó worker (ASR + diarizáció +
speaker-embedding). Terv és architektúra: [`docs/phase1-terv.md`](docs/phase1-terv.md).

**Állapot:** 2. fázis (skeleton) — portok, domain-modell, config-betöltő,
plugin-registry, fake adapterek és a teljes API-felület kész és tesztelt. A
valódi ML-adapterek (faster-whisper, Vosk, pyannote, NeMo MSDD, diart,
SpeechBrain, Resemblyzer, Silero, ffmpeg, SQLite-storage) a 3. fázisban
készülnek el — a hozzájuk tartozó stub osztályok addig `NotImplementedError`-t
dobnak. A teljes README (futtatás, config, JSON-kontraktus, adatvédelem) a
3. fázis végén készül el.

## Gyors indítás (fake adapterekkel, ML-függőség nélkül)

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

pytest -q

CONFIG_PATH=config/config.fake.yaml python -m leiratozo.main
# -> http://127.0.0.1:8080/healthz, /v1/config, /docs
```

## Projektszerkezet

```
src/leiratozo/
  domain/       entitások, value objectek, hibák — nincs ML-függőség
  ports/        a 3 fő port (asr, diarization, speaker_embedding) + kiegészítők
  contracts/    a verziózott JSON kimeneti kontraktus (schema_version 1.0)
  registry/     lusta plugin-registry (config -> adapter osztály)
  adapters/     konkrét adapterek: fake/*.py (2. fázis) + valódi stub-ok (3. fázis)
  application/  BatchTranscriptionService, LiveSessionService, SpeakerRegistrationService
  config/       pydantic-settings séma + rétegzett (YAML+env) betöltő
  api/          FastAPI végpontok
config/         config.example.yaml (éles), config.fake.yaml (dev/skeleton)
tests/          unit, integration, contract
```
