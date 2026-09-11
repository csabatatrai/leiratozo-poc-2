# Tradeoff-ok és tervezési döntések

Ez a dokumentum összegzi, milyen architekturális/technológiai döntéseket
hoztunk a leiratozó worker 1–3. fázisában, mi szólt mellettük, mi ellenük, és
mit vállaltunk be cserébe. Nem ismétli meg a `phase1-terv.md` teljes tervét —
arra hivatkozik, ahol releváns — hanem utólagos, kritikus mérleget ad:
**hol erős ez az implementáció, hol gyenge, és melyik döntésen mit
nyertünk/vesztettünk.**

---

## 1. Összegzés — erősségek

- **Valódi hexagonális határok, nem csak papíron.** A domain-mag és az
  alkalmazásréteg (`domain/`, `application/`) egyetlen sora sem importál
  ML-könyvtárat — ezt a 3. fázisban ténylegesen ellenőriztük: a fő teszt-venv
  ML-függőség nélkül fut, és minden valós adapter külön, izolált venv-ben lett
  bevonva anélkül, hogy a domain/application kódot módosítani kellett volna.
- **A modellagnosztikusság bizonyított, nem csak ígért.** Mind a 3 fő portra
  (ASR, diarizáció, speaker-embedding) legalább 2, architekturálisan eltérő
  adapter készült, és a váltás ténylegesen configból történik (`config.models.*.adapter`),
  kódmódosítás nélkül — ezt élő teszttel is igazoltuk (pl. `MODELS__ASR__ADAPTER=vosk` env-override).
- **A batch/streaming és offline/élő kompromisszumok nem vannak elrejtve.** A
  JSON kontraktus explicit jelzi (`streaming_mode: "approximated"|"native"`,
  `is_final`), melyik eredmény mennyire végleges — a fogyasztó szolgáltatás
  tudatosan dönthet.
- **A GDPR-kritikus rész nem csak deklarált, hanem bizonyított.** A
  titkosított profile store tesztje ténylegesen kinyitja a nyers .db fájlt, és
  assertálja, hogy plaintext PII/embedding NEM jelenik meg benne — ez erősebb
  garancia, mint egy puszta "encrypted" felirat a kódban.
- **Degradált-üzemmód valós hibaesetre tesztelve.** A hiányzó HF token miatti
  degradációt (pyannote) élesen kiváltottuk és ellenőriztük — nem csak
  feltételeztük, hogy a `try/except` ág helyesen viselkedik.
- **A Docker-integráció valós build+run+curl teszttel igazolt**, és ez a
  teszt egy tényleges hibát (editable install töréke a runtime stage-ben) is
  felszínre hozott és javított — ez self-fulfilling bizonyíték arra, hogy a
  "csak papíron jó" kockázat itt nem állt fenn.

## 2. Összegzés — gyengeségek / ismert korlátok

- **NeMo MSDD és diart nincs élesen validálva** (ld. lent, 3.3 és 3.4 szakasz)
  — a kód a dokumentált API szerint készült, de tényleges futtatás nélkül. Ez
  a legnagyobb kockázati pont: elképzelhető, hogy egy valós, kompatibilis
  környezetben apró API-eltérések (pl. NeMo config-mezőnevek, diart pipeline
  hívási konvenció) még finomítást igényelnek.
- **Nincs valódi megfigyelhetőségi (metrics) adapter.** A `MetricsSink` port
  létezik, de nincs mögötte Prometheus/OpenTelemetry implementáció — csak a
  strukturált logolás valós.
- **Nincs forced-alignment fallback**, csak a `PassthroughAligner` — ha egy
  jövőbeli ASR-adapter NEM ad szó-szintű időbélyeget, ez az adapter üres
  eredményt adna. Jelenleg mindkét valós ASR-adapter (faster-whisper, Vosk)
  ad szóidőt, tehát ez ma nem éles hiba, de dokumentált rés.
- **A speaker-matching lineáris keresés** (`SpeakerRegistrationService.match_segments`
  minden regisztrált profillal koszinusz-hasonlóságot számol) — néhány tucat
  profilnál triviális, de több ezres regisztrációnál ANN-indexelés
  (pl. FAISS/HNSW) nélkül lassulna.
- **Az élő diarizáció beszélő-címkézése (`LiveSessionService`) leegyszerűsített
  drótozás** a 2. fázisból: a diarizer minden ASR-eseményhez egy placeholder
  (üres bájtú) `AudioChunk`-ot kap a valódi audio helyett — ez fake
  adapterekkel helyesen működik, de valós diarizációs adapterrel (diart) a
  pontos audio-illesztés finomítást igényelne (ld. `live_service.py` docstring
  és 3.7 szakasz).
- **Nincs authN/authZ**, csak egy egyszerű API-key placeholder — feltételezés
  szerint egy külső API-gateway/beágyazó szolgáltatás védi (ld.
  `phase1-terv.md` 0. szakasz feltételezései).
- **A diart élő állapota process-lokális** (nem a SessionStore-on át
  perzisztált) — egyetlen worker node-on belül helyes, de horizontális
  skálázásnál session-affinitás routing nélkül nem működne.

---

## 3. Döntésenkénti tradeoff-elemzés

Minden szakasz: **Választás — Alternatíva(k) — Mit nyertünk — Mit adtunk fel /
mit kockáztattunk**.

### 3.1 Hexagonális (ports & adapters) architektúra

- **Választás:** szigorú port-interfészek (Protocol), domain-mag ML-függőség
  nélkül, konkrét modellek csak adapter mögött.
- **Alternatíva:** egyenes, "pragmatikus" integráció — pl. a FastAPI route
  közvetlenül hívja a `faster_whisper.WhisperModel`-t.
- **Mit nyertünk:** valódi modellcserélhetőség kódmódosítás nélkül; a domain-
  logika (speaker-matching, streaming-közelítés) ML-függőség nélkül
  tesztelhető és gyorsan fut; egy adapter hibája (ld. degradáció) nem viszi el
  a többit.
- **Mit adtunk fel:** több boilerplate (Protocol-ok, registry, DI-drótozás
  `deps.py`-ban) egy kisebb, egy-modelles projekthez képest — kis-közepes
  méretű, egy-adapteres rendszerhez ez az architektúra túlbiztosítás lenne,
  de a feladat kifejezetten a modellagnosztikusságot kérte, tehát ez itt
  indokolt komplexitás, nem felesleges.

### 3.2 ASR: faster-whisper (batch-natív) + Vosk (natív streaming)

- **Választás:** két architekturálisan eltérő motor — az egyik pontos de
  csak batch, a másik gyors/könnyű de valóban streamel.
- **Alternatíva:** két Whisper-variáns (pl. faster-whisper + whisper.cpp) —
  hasonlóbb pontosság, de mindkettő batch-natív, tehát nem bizonyítaná, hogy a
  rendszer valódi streaminget IS tud kezelni model-szinten, csak a
  közelítést.
- **Mit nyertünk:** a `SlidingWindowStreamingAdapter` (közelítés) ÉS a natív
  streaming út is le van fedve, valós teszttel — ez pontosan demonstrálja a
  2. kemény megkötés szerinti "ne ígérj valódi real-time-ot, ahol csak
  imitáció van" elvet, mert van kontraszt-alapunk.
- **Mit adtunk fel:** Vosk pontossága messze elmarad a Whisper-családétól —
  éles, magyar nyelvű, pontosságra érzékeny élő use case-hez érdemes lehet
  egy jobb natív-streaming motort keresni (pl. NVIDIA NeMo Conformer-streaming,
  ami viszont ugyanabba a nehéz-telepítésű kategóriába esne, mint a
  diarizációs NeMo-adapter — ld. 3.3).

### 3.3 Diarizáció (batch): pyannote + NeMo MSDD

- **Választás:** két batch-adapter, eltérő architektúrával (szegmentálás+
  klaszterezés vs. multi-scale neurális dekóder), a felhasználó explicit
  kérésére (2. modul jóváhagyás).
- **Alternatíva:** egyetlen batch-adapter (pyannote) + az élő diart mint
  "2. adapter" — ezt javasoltam elsőként az 1. fázisban, de a felhasználó
  ragaszkodott egy VALÓDI második batch-motorhoz.
- **Mit nyertünk:** a batch oldalon is bizonyított a modellagnosztikusság
  (nem csak batch-vs-élő kontraszt); a NeMo MSDD emellett Apache-2.0, nem
  igényel HF gated-licencet — gyakorlati fallback, ha valaki nem akar
  HF-fiókot/tokent kezelni.
- **Mit adtunk fel/kockáztattunk:** a NeMo toolkit telepítése ~15 perc után
  sem fejeződött be ebben a munkamenetben (nagy dependency-fa: torch,
  pytorch-lightning, transformers, hydra, stb.) — a NeMo MSDD adapter kódja
  emiatt **nincs élesen validálva**. Ez konkrét, mérhető ára annak, hogy egy
  nehéz, sokrétegű ML-toolkit-ot választottunk második adapterként a
  könnyebb (de HF-gated) alternatívák helyett.

### 3.4 Diarizáció (élő): diart

- **Választás:** `diart` mint az egyetlen "igazi" élő diarizációs adapter
  (pyannote szegmentációra épül).
- **Alternatíva:** saját, egyszerű online klaszterező (pl. sliding-window
  embedding + inkrementális agglomeratív klaszterezés kézzel, ahogy a
  `FakeLiveDiarizer` demonstrálja elvben) — kevesebb függőség, teljes
  kontroll, de "újra feltalálja a kereket", és rosszabb minőségű lenne, mint
  egy erre szakosodott, karbantartott könyvtár.
- **Mit nyertünk volna éles működés esetén:** karbantartott, kutatásalapú
  inkrementális klaszterezés, ami a pyannote embeddingekre épül — konzisztens
  minőség a batch úttal.
- **Mit vesztettünk ténylegesen:** a `diart` telepítése ebben a
  munkamenetben KÉTSZER, két különböző módon is valós verzió-
  inkompatibilitásba futott (host: `numpy<2` pin fordítást igényelt volna
  gcc nélkül; tiszta konténerben: a `diart` maga által behúzott `torchaudio`
  verzió inkompatibilis volt a vele együtt települő `pyannote.audio`-val —
  `AttributeError: module 'torchaudio' has no attribute 'AudioMetaData'`).
  Ez egy valós, dokumentált ökoszisztéma-törékenységi jel: a diart+pyannote+
  torch+torchaudio négyes explicit verzió-pinnelést igényel éles
  bevezetéskor, amit ez a munkamenet nem tudott kísérleti úton kideríteni.

### 3.5 Speaker embedding: SpeechBrain ECAPA-TDNN + Resemblyzer

- **Választás:** x-vector (ECAPA-TDNN) és GE2E d-vector (Resemblyzer) —
  architekturálisan eltérő embedding-családok.
- **Alternatíva:** pyannote saját embedding-modellje (`pyannote/embedding`)
  második adapterként — egyszerűbb, mert már úgyis HF-en vagyunk a
  diarizációval, de akkor NEM lenne architekturális kontraszt, csak ugyanaz a
  család más csomagolásban.
- **Mit nyertünk:** valódi architekturális diverzitás + mindkettő NYILVÁNOS,
  HF token nélkül működik — ez a legjobban validált modul ebben a
  munkamenetben (mindkét adapter élesen tesztelve, a Resemblyzer speciális
  natívkód-függősége miatt Docker-konténerben).
- **Mit adtunk fel:** a Resemblyzer natívan a `webrtcvad` csomagra épül, ami
  csak Python 3.11/3.12-n épül elő prekompilált wheelként — a host Python
  3.14-es környezetben ez direkt telepítési akadály volt (áthidalva Docker-
  konténerrel), ami éles CI/CD-ben is figyelmet igényel (Python-verzió pin).

### 3.6 GDPR profile store: mezőszintű Fernet-titkosítás SQLite-ban

- **Választás:** saját SQLite tábla + `cryptography.Fernet` mezőszintű
  titkosítás, kulcs env-változóból.
- **Alternatíva:** külső KMS/Vault-integráció (AWS KMS, HashiCorp Vault,
  Google Cloud KMS) a kulcskezeléshez; vagy egy teljes titkosított
  fájlrendszer/disk-encryption szintű megoldás az alkalmazás-szintű
  titkosítás helyett.
- **Mit nyertünk:** zéró külső infrastruktúra-függés, egyszerű, auditálható,
  a "kis-közepes, single-node" skálához illeszkedő megoldás; a titkosítás
  ténylegesen bizonyított (ld. 1. szakasz).
- **Mit adtunk fel:** nincs kulcsrotáció, nincs központi audit-napló a
  kulcshasználatról, nincs hardver biztonsági modul (HSM) — ez egy valódi
  enterprise/multi-tenant GDPR-megfelelőségi programnál elvárt lenne. Ha a
  szervezet mérete/kockázati profilja indokolja, ez a `ProfileStore` port
  mögött KMS-alapú adapterre cserélhető kódmódosítás nélkül máshol a
  rendszerben — ezt a portot pontosan emiatt terveztük elkülönítve.

### 3.7 Élő session vezénylés: egyszerűsített audio→diarizer drótozás

- **Választás:** a 2. fázisban a `LiveSessionService.process_chunks` minden
  ASR-eseményhez egy placeholder (üres) `AudioChunk`-ot ad tovább a
  diarizernek, nem az eredeti audio-bájtokat.
- **Alternatíva:** az ASR-wrapper (`SlidingWindowStreamingAdapter`) és a
  diarizer közötti audio-chunkokat explicit "tee"-zni (elágaztatni), hogy
  mindkettő ugyanazt a nyers audio-t lássa szinkronban.
- **Mit nyertünk:** egyszerűbb, gyorsabban leszállítható vezénylési logika,
  ami fake adapterekkel (és a diart hiányában, ld. 3.4) teljes értékűen
  tesztelhető és helyesen működik.
- **Mit adtunk fel:** valós diart-adapterrel (ha/amikor telepíthető lesz) ez
  a réteg finomítást igényel, hogy a diarizer ténylegesen a helyes audio-
  szeletet kapja — ezt a kódban explicit TODO-ként jelöltük, nem hallgatólagos
  hiányosságként.

### 3.8 Batch job-queue: `arq` + Redis (nem Celery)

- **Választás:** `arq` (async-natív Redis-queue) + configolható `inline`
  fallback dev/tesztre.
- **Alternatíva:** Celery (érettebb ökoszisztéma, ütemezés, retry-politikák,
  flower monitoring) vagy egy teljesen egyedi, adatbázis-alapú queue.
- **Mit nyertünk:** natív asyncio-integráció a FastAPI-val (nincs szükség
  szinkron/aszinkron híd-kódra), kevesebb infrastruktúra-komponens, gyors
  fejlesztés; a `queue.backend: inline` mód lehetővé teszi, hogy a
  fake-adapteres teszt/demó út SOSEM függjön Redis-től.
- **Mit adtunk fel:** Celery gazdagabb retry/ütemezési/monitoring
  ökoszisztémáját — ha a szervezet már Celery-re épít, ez csereszabatos
  lenne, mert a queue-interakció a `ServiceContainer.submit_batch_job`-ban
  van elszigetelve.

### 3.9 Storage: SQLite (nem Postgres az elejétől)

- **Választás:** SQLAlchemy-mentes, közvetlen `aiosqlite`/`sqlite3` adapterek.
- **Alternatíva:** Postgres + SQLAlchemy ORM az első naptól.
- **Mit nyertünk:** zéró külső DB-infrastruktúra a "kis-közepes, single-node"
  céllal összhangban; a portok (JobStore/SessionStore/ProfileStore) úgy
  vannak tervezve, hogy egy Postgres-adapter kódmódosítás nélkül,
  máshol a rendszerben, becsatlakozhasson.
- **Mit adtunk fel:** SQLite írási konkurenciakorlátai (egyetlen írófolyamat)
  — több párhuzamos worker-node esetén (skálázási igény esetén)
  Postgres-re kellene váltani; ezt tudatosan halasztottuk, nem elfelejtettük.

### 3.10 Live streaming transport: WebSocket (nem gRPC)

- **Választás:** WebSocket + JSON esemény-envelope.
- **Alternatíva:** gRPC bidirectional streaming (típusos, generált
  kliensekkel, jobb bináris hatékonysággal).
- **Mit nyertünk:** egyszerűbb integráció böngésző-közeli/HTTP-alapú
  fogyasztóknak (a célintegráció — meeting-leiratozás — tipikusan ilyen);
  nincs szükség protobuf-fordításra a fogyasztó oldalán.
- **Mit adtunk fel:** szigorú, generált típusosságot és jobb bináris
  hatékonyságot nagy áteresztésnél — ha később szükséges, egy gRPC-facade
  hozzáadható az API-rétegben a domain/portok érintése nélkül (ezt a tervben
  is jeleztük).

### 3.11 Plugin-betöltés: kézzel írt registry (nem DI-framework/entry_points)

- **Választás:** egy egyszerű `dict[str, str]` registry + `importlib`, lusta
  importtal, `DegradedAdapter` degradációs mintával.
- **Alternatíva:** setuptools `entry_points` (igazi, csomagolt harmadik-fél
  plugin-ök) vagy egy teljes DI-framework (pl. `dependency-injector`).
- **Mit nyertünk:** nulla extra keretrendszer-függőség, könnyen olvasható,
  tesztelhető (`tests/unit/test_plugin_registry.py` saját stubot regisztrál
  futásidőben); a `DegradedAdapter` minta pontosan illeszkedik a
  "nem-fatális modellbetöltési hiba" követelményhez.
- **Mit adtunk fel:** nincs automatikus, csomagolás-alapú plugin-felfedezés
  (egy harmadik fél nem tud egyszerűen `pip install`-lal új adaptert
  regisztrálni — a `register()` függvényt kellene hívnia kódból). Kis-közepes
  méretű, belső fejlesztésű adapterkészlethez ez nem korlátozó tényező.

### 3.12 Tesztstratégia: valódi modellek + skip-fixture (nem mély mockolás)

- **Választás:** minden valós adapterhez valódi, futtatott modell-tesztet
  írtunk (kis modellméretekkel), `pytest.skip`-pel, ha a függőség/hálózat
  hiányzik — a fake adapterek pedig a teljes API-t lefedik mock nélkül.
- **Alternatíva:** `unittest.mock`-kal szimulálni a modellek válaszait,
  gyorsabb és determinisztikusabb, de sosem deríti ki, ha egy könyvtár API-ja
  megváltozott.
- **Mit nyertünk:** ez a döntés ténylegesen két valós hibát fogott meg ebben
  a munkamenetben (Dockerfile editable-install, streaming-adapter is_final
  logika) — mock-alapú tesztek ezeket NEM vették volna észre.
- **Mit adtunk fel:** lassabb, hálózat-függő, néha (diart/NeMo esetén)
  egyáltalán nem futtatható teszt-lefedettség; több, külön venv-et igényel
  párhuzamos fejlesztéskor (ld. 3.13).

### 3.13 Fejlesztői venv-ek: modulonként külön (nem egy közös mega-venv)

- **Választás:** `.venv` (fő, ML-mentes) + `.venv-asr`/`.venv-diar`/`.venv-embed`
  a nehéz, egymással esetlegesen ütköző függőségekhez (pl. eltérő torch-
  verziók).
- **Alternatíva:** egyetlen venv minden extrával együtt telepítve.
- **Mit nyertünk:** párhuzamos modulfejlesztés lehetségessé vált anélkül,
  hogy egy `pip install` a másik modul függőségeit összetörte volna;
  gyorsabb, kisebb, célzott telepítések.
- **Mit adtunk fel:** a végső, éles image-nek (Dockerfile) továbbra is egy
  konszolidált, EXTRAS build-arg alapján összeállított környezetet kell
  telepítenie — ezt a build-time integrációt VALÓS docker-build-bel
  igazoltuk a "lean" (fake-only) konfigurációra, de a teljes,
  minden-extrás image build-jét tudatosan NEM futtattuk végig (túl nagy/lassú
  lenne) — ld. Dockerfile fejléce.

---

## 4. Ha újrakezdeném — mit csinálnék másképp

- **Előbb egy gyors, olcsó "smoke install" mátrixot futtatnék** minden nehéz
  függőségre (NeMo, diart, resemblyzer) egy python:3.11 konténerben, MIELŐTT
  a modulokat párhuzamos agentekre osztom — ez korábban felszínre hozta volna
  a diart verzió-inkompatibilitást és a NeMo telepítési idő-igényt, jobb
  időbecslést adva.
- **A párhuzamos háttér-agenteket kisebb, rövidebb lépésekre bontanám**,
  gyakoribb checkpointtal — a 4 egyidejű agent rate-limitbe futása pont azért
  volt fájdalmas, mert nagy, hosszú lépésekben dolgoztak checkpoint nélkül.
- **A `LiveSessionService` audio→diarizer drótozását (3.7) elsőre helyesen
  írnám meg**, nem placeholder-rel — ez most dokumentált adósság, ami egy
  valós diart-integrációkor úgyis vissza fog jönni.
