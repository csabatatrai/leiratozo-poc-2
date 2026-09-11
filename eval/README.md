# Kiértékelő eszköz (eval/)

Ez **a projekt tartós része**, nem egyszeri szkript. Célja: rendszeresen,
reprodukálhatóan összehasonlítani

1. a **nyers, külső ASR-végpont** kimenetét és a **teljes leiratozó-pipeline**
   (VAD → ASR → diarizáció → aligner → speaker-match) kimenetét —
   **leiratozási minőség** (WER — Word Error Rate) szempontjából, és
2. a pipeline **diarizáció/beszélő-szétválasztás** pontosságát — **DER**
   (Diarization Error Rate) szempontjából —

mind **batch** (korábban rögzített fájlon), mind **élő** (WebSocket-en
streamelt) módban. Így amikor egy adaptert (pl. pyannote helyett NeMo MSDD,
vagy egy jobb ASR-modell) cserélünk, ugyanezzel az eszközzel objektíven
megmérhető, hogy tényleg javult-e valami — nem csak "szemre".

Az eszköz **most, teszt-adat nélkül is használható részlegesen** (a
baseline-vs-pipeline szöveg-összevetés WER-je ground-truth nélkül is fut), és
**azonnal teljes értékű lesz**, amint az alábbi hiányzó bemenetek
rendelkezésre állnak.

## Miért nincs még teljes kiértékelés? (2026-09-12 állapot)

| Amit mérni akarunk | Mihez kell | Jelenlegi állapot |
|---|---|---|
| WER a valósághoz képest | egy **referencia-átirat** (ember által ellenőrzött, pontos szöveg) | ❌ nincs egy teszt-felvételünkhöz sem |
| DER (diarizáció pontossága) | egy **referencia-RTTM** (ki mikor beszélt, ground truth) | ❌ nincs |
| Ismert-beszélő matching pontossága | 2+ **enrollment-minta** (tiszta, egy-beszélős, néhány perces klip) beszélőnként, + tudni, mely szegmensek kihez tartoznak a teszt-felvételben | ❌ nincs |
| Valódi diarizáció (nem `fake`) a pipeline oldalán | HF token (pyannote/diart licenc-elfogadás) VAGY működő NeMo MSDD telepítés | ❌ a felhasználó explicit token nélkül halad egyelőre (ld. docs/phase1-terv.md) |

Lásd **`docs/manual_test_notes.md`** a pontos, dátumozott teszt-előzményekért
és a hiányzó adatok specifikációjáért (hossz, beszélőszám stb.).

## Hogyan add hozzá az első valós teszt-esetet

1. Hozz létre egy könyvtárat: `eval/data/<eset-neve>/` (ez **gitignore-olt**,
   ld. .gitignore `eval/data/` — sosem kerül git alá, mert valós hangfelvétel
   = potenciálisan PII/biometrikus adat).
2. Tedd bele:
   - `audio.wav` — **mono, 16 kHz, 16-bit PCM** (ha nem az, konvertáld:
     `ffmpeg -i eredeti.wav -ac 1 -ar 16000 audio.wav`)
   - `reference.txt` — a teljes, ember által ellenőrzött átirat (ha van)
   - `reference.rttm` — ground-truth diarizáció szabványos RTTM formátumban
     (ha van; pl. `pyannote`/NeMo eszközökkel vagy kézzel annotálva)
   - `enroll_<speaker_id>.wav` fájlok — tiszta, egy-beszélős minták, ha az
     ismert-beszélő matchinget is tesztelni akarod
3. Írj egy `manifest.json`-t ugyanabba a könyvtárba:

```json
{
  "id": "interju_2026_09_12",
  "description": "Kb. 3 perces hírműsor-részlet, 2 beszélővel (riporter + interjúalany)",
  "audio_path": "audio.wav",
  "reference_transcript_path": "reference.txt",
  "reference_rttm_path": "reference.rttm",
  "known_speakers": [
    {"speaker_id": "spk_riporter", "enrollment_audio_path": "enroll_riporter.wav"},
    {"speaker_id": "spk_interjualany", "enrollment_audio_path": "enroll_interjualany.wav"}
  ]
}
```

Minden mező, ami hiányzik/nincs (pl. nincs `reference_rttm_path`), egyszerűen
kihagyja a hozzá tartozó metrikát a jelentésből — nem hiba.

### Minimumkövetelmények egy hasznos teszt-esethez

- **Hossz:** legalább 2-3 perc (a diarizáció és a streaming-közelítés is
  csak néhány beszélőváltás/több ablaknyi audio után értékelhető érdemben;
  egy 10-20 másodperces klip túl kevés).
- **Beszélők:** **legalább 2**, lehetőleg **3+** különböző hangú beszélő —
  hogy a diarizáció/matching tényleges megkülönböztető-képessége mérhető
  legyen, ne csak "van-e egyáltalán szegmentálás".
- **Átfedés/váltakozás:** legyen benne néhány gyors beszélőváltás (pl.
  interjú kérdés-válasz), ez teszi próbára a diarizációt igazán.
- **Enrollment-minták:** beszélőnként kb. **30 mp – 2 perc**, lehetőleg más
  felvételből/pillanatból, mint a teszt-audio (különben az "ismert beszélő
  felismerése" túl könnyű/nem reprezentatív).
- **Zajszint:** ha lehet, legyen egy "tiszta" (stúdió/csendes) ÉS egy
  "zajosabb" (utcai/telefonos) teszt-eset is — ez adja a robusztusság-mérést.

## Futtatás

```bash
pip install -e ".[eval]"                 # DER-hez (pyannote.metrics); WER-hez nem kell semmi extra
python -m leiratozo.main &               # a worker fusson (vagy docker compose up)

python -m eval.run_eval \
  --case eval/data/interju_2026_09_12/manifest.json \
  --remote-asr-url http://192.168.100.7:8001 \
  --api-url http://127.0.0.1:8080 \
  --mode both \
  --report-out eval/data/interju_2026_09_12/report.json
```

`--mode batch|live|both` — melyik pipeline-utat futtassa a nyers baseline
mellett. A jelentés a konzolra íródik, és (ha `--report-out` meg van adva)
egy géppel-feldolgozható JSON-ba is (szintén gitignore-olt `eval/data/` alatt,
ha oda mented).

## Mit NEM automatizál még ez az eszköz

- **Ismert-beszélő (`known_speaker_id`) matching pontosságának mérése** —
  a manifestben megadható enrollment-minták ma még csak dokumentáltak, a
  `run_eval.py` még nem hívja a `POST /v1/speakers` regisztrációs végpontot
  és nem veti össze a kapott `known_speaker_id`-kat egy ground-truth
  szegmens→beszélő hozzárendeléssel. Ez a következő bővítés, amint lesz
  valós, több-beszélős teszt-adat + ground truth hozzárendelés — a
  `dataset.EvalCase.known_speakers` már felkészítve várja.
- **DER wrapper (`eval/metrics.py: diarization_error_rate`)** a
  `pyannote.metrics` dokumentált API-ja szerint készült, de **nincs élesen
  tesztelve** (nincs még ground-truth RTTM-ünk) — az első valós használatkor
  érdemes ellenőrizni, hogy pontosan illeszkedik-e a telepített
  `pyannote.metrics` verzió API-jához.
- **Automatikus regresszió-figyelés** (pl. "a WER ne romoljon 5%-nál
  többet a korábbi futáshoz képest") — ma minden futás önálló, kézzel
  összevetendő jelentést ad; ha lesz elég teszt-eset, érdemes lehet egy
  egyszerű "baseline report vs. jelenlegi report" diff-elő szkriptet írni.
