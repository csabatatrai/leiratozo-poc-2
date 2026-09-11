# syntax=docker/dockerfile:1
#
# Többlépcsős build a leiratozó workerhez (docs/phase1-terv.md 11. szakasz).
#
# Az ML-adapterek (faster-whisper, Vosk, pyannote, NeMo MSDD, diart, SpeechBrain,
# Resemblyzer, Silero VAD) mindegyike külön, opcionális pyproject extra-csoport
# mögött él (ld. pyproject.toml [project.optional-dependencies]) — ezért a build
# ARG-okkal SZELEKTÍVEN kapcsolhatók be. Ennek oka:
#   1. Méret/licenc-szórás: a NeMo toolkit (+torch) önmagában több GB-ot hozhat be,
#      a pyannote/diart HF gated-licenchez kötött, a Vosk/faster-whisper viszont
#      könnyű és nyilvános — nem minden deploy akar/tud mindent bevállalni.
#   2. Modellagnosztikusság bizonyítéka a build szintjén is: egy adott deploy
#      pontosan azokat az adaptereket kapja meg, amiket a configja ténylegesen
#      használ (ld. 1. kemény megkötés) — nincs kényszerű "minden vagy semmi".
#
# Példa: minden ASR+embedding+VAD extra, diarizáció nélkül (a gated pyannote/nemo/
# diart-ot külön, tudatos döntéssel kell bekapcsolni):
#   docker build \
#     --build-arg EXTRAS=asr-faster-whisper,asr-vosk,embedding-speechbrain,embedding-resemblyzer,vad-silero,audio \
#     -t leiratozo:full .
#
# Alapértelmezett (EXTRAS üres) build: csak a core (FastAPI stb.) — ezzel KIZÁRÓLAG
# a `fake` adapterek működnek (ld. config/config.fake.yaml). Ez a legkisebb, leggyorsabb
# image, jó a teljes API-felület demózására/CI-smoke-tesztre ML-súlyok nélkül.

FROM python:3.11-slim AS build

ARG EXTRAS=""

WORKDIR /build

# ffmpeg kell az `audio`/ffmpeg-decoder extrához futásidőben is (runtime stage-be
# is telepítjük lentebb) — build stage-ben csak a Python csomagok fordításához
# esetenként szükséges build-essential-t tesszük be, hogy natív kiterjesztések
# (pl. egyes ML-csomagok) lefordulhassanak.
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./
COPY src ./src

# Egy izolált venv-be telepítünk, amit a runtime stage egyszerűen átmásol —
# ez tartja karcsún a végső image-et (nincs benne build-essential, apt cache stb.).
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# FONTOS: NEM editable (-e) install — az editable mód a forráskönyvtár abszolút
# útvonalát sütné bele a venv-be (pl. /build/src), ami a runtime stage-ben (más
# WORKDIR, a /build könyvtár nem is létezik ott) ModuleNotFoundError-ral bukna.
# Rendes, nem-editable telepítéssel a csomag ténylegesen bekerül a
# site-packages-be, függetlenül attól, honnan másoltuk át a /opt/venv-et.
RUN --mount=type=cache,target=/root/.cache/pip \
    if [ -n "$EXTRAS" ]; then \
        pip install --upgrade pip && pip install ".[${EXTRAS}]"; \
    else \
        pip install --upgrade pip && pip install "."; \
    fi


FROM python:3.11-slim AS runtime

# ffmpeg: az AudioDecoder port `ffmpeg` adaptere (audio extra) ezt igényli
# futásidőben is a wav/mp3/m4a/ogg/flac dekódoláshoz.
RUN apt-get update && apt-get install -y --no-install-recommends \
        ffmpeg curl \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid 1000 leiratozo

COPY --from=build /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1

WORKDIR /app
# A csomag már a site-packages-ben van (nem-editable install, ld. fent) — itt
# csak a futásidőben szükséges, pip-en kívüli config-példákat másoljuk be.
COPY config ./config

# Modellsúlyok / adatbázisok / speaker-profilok named volume-okra kerülnek
# (ld. docker-compose.yml) — sosem az image-be sütve, hogy (a) a HF gated
# licencek elfogadása a hosztoldali token/volume kezelése maradjon, ne az
# image-építésé, és (b) a GDPR-kritikus profile store fájl a konténer
# életciklusától függetlenül perzisztáljon és törölhető legyen.
RUN mkdir -p /models /data && chown -R leiratozo:leiratozo /models /data /app
VOLUME ["/models", "/data"]

USER leiratozo

ENV CONFIG_PATH=/app/config/config.example.yaml

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -fs http://127.0.0.1:8080/healthz || exit 1

CMD ["uvicorn", "leiratozo.main:app", "--host", "0.0.0.0", "--port", "8080"]
