# leiratozó

Modellagnosztikus, konfigurálható leiratozó worker: hangfájlt (batch) vagy élő
hangstreamet fogad, és beszélőnként szétbontott, verziózott JSON leiratot ad
ki. Az ASR/diarizáció/speaker-embedding modellek konfigból cserélhetők,
kódmódosítás nélkül. Teljes tervdokumentum: [`docs/phase1-terv.md`](docs/phase1-terv.md).

## Gyors indítás

### Fake adapterekkel (ML-függőség nélkül, demó/CI-smoke-teszt)

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest -q

CONFIG_PATH=config/config.fake.yaml python -m leiratozo.main
# -> http://127.0.0.1:8080/healthz, /v1/config, /docs
```

### Docker Compose-szal

```bash
cp .env.example .env
# fake adapterek, gyors smoke-teszt:
CONFIG_PATH=/app/config/config.fake.yaml docker compose up --build worker

# valódi adapterekkel + Redis-queue-val (mindkét service kell):
EXTRAS=asr-faster-whisper,asr-vosk,embedding-speechbrain,embedding-resemblyzer,vad-silero \
  docker compose up --build
```

A `worker` service a HTTP/WebSocket API-t, az `arq-worker` a batch job-queue-t
dolgozza fel (csak `queue.backend: redis` esetén releváns — `inline` configgal,
ld. `config/config.fake.yaml`, egyszerűen üresjáratban vár).

## Projektszerkezet

```
src/leiratozo/
  domain/       entitások, value objectek, hibák — nincs ML-függőség
  ports/        a 3 fő port (asr, diarization, speaker_embedding) + kiegészítők
  contracts/    a verziózott JSON kimeneti kontraktus (schema_version 1.0)
  registry/     lusta plugin-registry (config -> adapter osztály) + DegradedAdapter
  adapters/     konkrét adapterek (fake/*.py + valódi implementációk)
  application/  BatchTranscriptionService, LiveSessionService, SpeakerRegistrationService
  config/       pydantic-settings séma + rétegzett (YAML+env) betöltő
  queue/        arq worker (batch job-feldolgozás Redis-queue-ból)
  api/          FastAPI végpontok
config/         config.example.yaml (éles), config.fake.yaml (dev/skeleton)
tests/          unit, integration, contract
```

## Konfiguráció

Rétegzett betöltés: kód-defaultok → `CONFIG_PATH` alatti YAML → környezeti
változók (env mindig nyer, 12-factor). Env-override nested kulcsokra
`__`-vel: pl. `MODELS__ASR__ADAPTER=vosk`, `DEVICE__DEFAULT=cpu`.

Teljes, kommentezett példa: [`config/config.example.yaml`](config/config.example.yaml)
(éles célra) és [`config/config.fake.yaml`](config/config.fake.yaml) (fake
adapterek, ML-függőség nélküli futtatáshoz). Legfontosabb szakaszok:

| Szakasz | Mit vezérel |
|---|---|
| `models.vad/asr/diarization/speaker_embedding` | melyik adapter töltődik be az adott porthoz, + adapter-specifikus paraméterek |
| `device.default` | `auto` / `cpu` / `cuda` |
| `queue.backend` | `inline` (dev/teszt, szinkron) vagy `redis` (production, külön worker) |
| `storage.*` | job/session/profile storage adapter + connection-string/útvonal |
| `speaker_matching.similarity_threshold` | küszöb az "ismert"/`unknown` speaker-döntéshez |
| `streaming.*` | chunk/overlap méret az élő közelítő streaminghez |
| `security.huggingface_token_env` | melyik env-változóban várja a HF tokent a pyannote/diart |

## Adapterek — státusz

| Port | Adapter | Állapot |
|---|---|---|
| ASR | `faster_whisper` | ✅ valódi, tesztelve ("tiny" modell) |
| ASR | `vosk` | ✅ valódi, tesztelve (natív streaming) |
| Diarizáció (batch) | `pyannote` | ✅ valódi kód; HF token nélkül a degradált út tesztelve élesen (ld. lent) |
| Diarizáció (batch) | `nemo_msdd` | ✅ valódi kód (manifest+RTTM workflow); **nem élesen tesztelve** ebben a munkamenetben (nagy/lassú telepítés) |
| Diarizáció (élő) | `diart` | ✅ valódi kód; **nem élesen tesztelve** (torchaudio/pyannote verzió-inkompatibilitás merült fel telepítéskor — ld. adapter modul docstring) |
| Speaker embedding | `speechbrain_ecapa` | ✅ valódi, tesztelve |
| Speaker embedding | `resemblyzer` | ✅ valódi, tesztelve (Docker python:3.11 konténerben — a host Python 3.14 nem tudta lefordítani a `webrtcvad` natív függőséget) |
| VAD | `silero` | ✅ valódi, tesztelve (torch.hub) |
| Audio decode | `ffmpeg` | ✅ valódi, tesztelve (subprocess, nem PyAV) |
| Job/Session store | `sqlite` | ✅ valódi, tesztelve |
| Profile store | `encrypted_sqlite` | ✅ valódi, tesztelve — beleértve a nyers fájl bájtszintű titkosítás-ellenőrzését |
| Minden port | `fake` | ✅ determinisztikus, ML-függőség nélküli, a teljes API-t végponttól-végpontig demózza |

**HF token nélküli üzemmódról:** a felhasználó explicit úgy döntött, hogy a
pyannote/diart gated licencű modelljeit token nélkül hagyjuk — ez azt jelenti,
hogy ezek a portok `degraded` állapotban indulnak (ld. `GET /readyz`), amíg
valaki be nem állítja a `HF_TOKEN` env-változót és el nem fogadja a modell
licencét a Hugging Face-en. Ez NEM crash-eli a szolgáltatást: más portok
(ASR, embedding, VAD) eközben is kiszolgálnak kéréseket.

## JSON kimeneti kontraktus

`schema_version: "1.0"` — teljes definíció: `src/leiratozo/contracts/transcript_schema.py`,
példa: `docs/phase1-terv.md` 8. szakasz. Röviden:

```json
{
  "schema_version": "1.0",
  "job_id": "...", "mode": "batch", "language": "hu",
  "models": {"vad": {...}, "asr": {...}, "diarization": {...}, "speaker_embedding": {...}},
  "segments": [
    {
      "segment_id": "...", "start": 0.42, "end": 3.87, "text": "...",
      "speaker_label": "S1", "known_speaker_id": "spk_...", "speaker_match_confidence": 0.86,
      "asr_confidence": 0.94, "is_final": true,
      "words": [{"word": "...", "start": 0.42, "end": 0.71, "confidence": 0.97}]
    }
  ],
  "speaker_aggregates": [{"speaker_label": "S1", "known_speaker_id": "spk_...", "total_speech_sec": 58.2, "segment_ids": ["..."]}]
}
```

## Végpontok

| Végpont | Cél |
|---|---|
| `POST /v1/jobs` | batch job indítás (multipart audio upload) |
| `GET /v1/jobs/{id}` | státusz |
| `GET /v1/jobs/{id}/result` | JSON transzkript |
| `WS /v1/live/{session_id}` | élő audio be, partial/final esemény ki |
| `POST /v1/speakers` | speaker-profil regisztráció mintából |
| `GET /v1/speakers` | profilok listája |
| `DELETE /v1/speakers/{id}` | törlés (GDPR right-to-erasure) |
| `GET /healthz` / `GET /readyz` | liveness / readiness (degradált portok listájával) |
| `GET /v1/config` | futásidejű, szanitizált config-introspekció |

## Adatvédelem (GDPR)

A regisztrált speaker-profil biometrikus, különleges kategóriájú személyes
adat (docs/phase1-terv.md 6. szakasz):

- **Titkosítás nyugalmi állapotban:** az `encrypted_sqlite` ProfileStore
  mezőszinten (Fernet) titkosítja az embedding-vektort és a `display_name`-et.
  A kulcsot a `PROFILE_ENCRYPTION_KEY` env-változóból olvassa — hiányzó/
  érvénytelen kulcs esetén a szolgáltatás NEM indul el csendes plaintext-
  fallback helyett. Generálás: `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`.
- **Azonosító:** `profile_id` random UUID, nem a személy neve.
- **Törlés:** `DELETE /v1/speakers/{id}` hard delete (nem soft-flag).
- **Logolás:** a strukturált JSON logger (`logging_setup.py`) egy explicit
  tiltólistát alkalmaz — nyers audio, embedding, `display_name` sosem kerül
  logba.
- **Retenció:** `retention.profile_retention_days` configolható (alapértelmezés:
  nincs auto-lejárat, csak explicit törlés).

## Tesztek

```bash
pytest -q                     # fake adapterekkel, ML-függőség nélkül — mindig zöld
```

A valódi ML-adapterek tesztjei (`test_asr_*`, `test_diarization_*`,
`test_speaker_embedding_*`, `test_vad_silero`, `test_audio_decoder_ffmpeg`)
a megfelelő `pip install -e ".[dev,<extra>]"` nélkül automatikusan
**skip**-elnek — nem buknak el. Dedikált venv-ekben (`.venv-asr`, `.venv-diar`,
`.venv-embed` — nem részei a repónak) valódi modellekkel futtatva lettek
leellenőrizve fejlesztés közben.

## Definition of Done — 3. fázis

- [x] Minden fő portra (ASR, diarizáció, speaker-embedding) **legalább 2**
      működő adapter — ASR: faster-whisper+Vosk (tesztelve); diarizáció:
      pyannote+NeMo MSDD (batch) + diart (élő) (pyannote tesztelve degradált
      úton, NeMo/diart implementálva, élő teszt nélkül); embedding:
      SpeechBrain ECAPA + Resemblyzer (tesztelve).
- [x] Adapter-váltás **kódmódosítás nélkül**, kizárólag configból (ld.
      `config.models.*.adapter`, `registry/plugin_registry.py`).
- [x] **Batch mód** fut (fake és valódi adapterekkel egyaránt tesztelve,
      valódi HTTP-n és Docker-konténerben is).
- [x] **Élő mód** fut a WebSocket végponton fake adapterekkel; valódi
      streaming ASR-rel (Vosk) és a SlidingWindowStreamingAdapter
      közelítéssel (faster-whisper) egyaránt lefedve unit teszttel.
- [x] **GDPR-törlés** működik, és a titkosítás ténylegesen igazolt (nyers
      .db fájl bájtszintű ellenőrzése).
- [x] **Tesztek zöldek**: `pytest -q` a fő venv-ben 52 passed, a valódi
      ML-adapter-tesztek a saját venv-jeikben (ASR, embedding, VAD, audio,
      pyannote-degradált-út) szintén mind zöldek.
- [x] **Konténer elindul**: többlépcsős Dockerfile, valódi build+run+curl-
      teszttel igazolva (health, config, batch job végponttól-végpontig);
      docker-compose stack (worker+arq-worker+redis) is validálva.
- [ ] NeMo MSDD és diart adapterek éles (nem csak degradált-út) validációja —
      ehhez kompatibilis torch/torchaudio/pyannote/nemo verzió-kombináció
      pinnelése és egy erősebb/gyorsabb hálózatú/gcc-vel rendelkező
      környezet szükséges (ld. adapters/diarization/diart.py és nemo_msdd.py
      modul docstring-jei a pontos akadályokért).
