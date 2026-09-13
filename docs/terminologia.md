# Terminológia / szójegyzék

Didaktikus szójegyzék a `leiratozó` projekt megértéséhez. A cél, hogy egy
diák vagy új fejlesztő a projektben előforduló IT szakkifejezéseket
**általánosan** és **a projekt konkrét kontextusában** is megértse.

Minden szócikk felépítése:
- **Általános jelentés** — mit jelent a kifejezés az IT/szoftverfejlesztés
  világában általában.
- **Hol jelenik meg a projektben** — konkrét fájl/mappa/kód-hivatkozás.
- **Mit old meg a projektben** — miért van rá szükség, milyen problémát
  kezel ebben a konkrét rendszerben.

A szócikkek témakörök szerint vannak csoportosítva, hogy tanulásra is jól
használható legyen: érdemes sorban végigolvasni egy adott csoportot. Ha
gyorsan egy konkrét kifejezést keresel, az [alfabetikus
gyorskeresőt](#alfabetikus-gyorskereső) használd a dokumentum végén.

## Tartalomjegyzék

- [1. Mit csinál ez a projekt? (egy mondatban)](#1-mit-csinál-ez-a-projekt-egy-mondatban)
- [2. Architektúra-minta: Hexagonális architektúra (Ports & Adapters)](#2-architektúra-minta-hexagonális-architektúra-ports-adapters)
- [3. Hangfeldolgozási pipeline lépései](#3-hangfeldolgozási-pipeline-lépései)
- [4. Backend / web-szolgáltatás terminológia](#4-backend-web-szolgáltatás-terminológia)
- [5. Konfiguráció](#5-konfiguráció)
- [6. Adattárolás](#6-adattárolás)
- [7. Adatvédelem (GDPR) fogalmak](#7-adatvédelem-gdpr-fogalmak)
- [8. ML-modellekhez kapcsolódó fogalmak](#8-ml-modellekhez-kapcsolódó-fogalmak)
- [9. Tesztelés](#9-tesztelés)
- [10. Konténerizáció](#10-konténerizáció)
- [11. Dokumentáció / diagramok](#11-dokumentáció-diagramok)
- [12. JSON kimeneti kontraktus — kulcsfogalmak](#12-json-kimeneti-kontraktus-kulcsfogalmak)
- [Alfabetikus gyorskereső](#alfabetikus-gyorskereső)

---

## 1. Mit csinál ez a projekt? (egy mondatban)

Hangfelvételt (fájlt vagy élő stream-et) alakít át **beszélőnként
szétbontott, időbélyegzett, JSON formátumú szöveges leirattá** — ezt hívják
a szakmában **ASR + diarizáció** pipeline-nak. A modellek (melyik motor
végzi a felismerést, a beszélő-szétválasztást stb.) configból cserélhetők,
kódmódosítás nélkül.

---

## 2. Architektúra-minta: Hexagonális architektúra (Ports & Adapters)

### Hexagonális architektúra / Ports & Adapters

**Általános jelentés:** Szoftverarchitektúra-minta, amelyben az
üzleti logika (domain) nem függ közvetlenül konkrét külső
technológiáktól (adatbázis, ML-modell, HTTP-kliens). Ehelyett
absztrakt **interfészeket** ("port") definiál, amiket konkrét
implementációk ("adapter") valósítanak meg. Az üzleti logika csak a
portot ismeri, az adaptert futásidőben "bedugják".

**Hol jelenik meg a projektben:** A teljes `src/leiratozo/` mappastruktúra
erre épül: `ports/`, `adapters/`, `domain/`, `application/`. Lásd
`docs/architecture/03-port-adapter-components.md` (UML interfész-realizáció
diagram).

**Mit old meg a projektben:** Az ASR/diarizáció/speaker-embedding modellek
**modellagnosztikusan**, konfigból cserélhetők (pl. `faster_whisper` →
`vosk`), anélkül hogy az alkalmazás logikáját (batch-feldolgozás, API,
GDPR-szabályok) módosítani kellene. Ez a README első mondatában is
kiemelt cél: "Modellagnosztikus, konfigurálható leiratozó worker".

### Port

**Általános jelentés:** Egy absztrakt szerződés (interfész), ami leírja,
*milyen műveleteket* kell egy komponensnek tudnia, de nem írja elő, *hogyan*.
Pythonban gyakran `Protocol` (structural typing) vagy `abstract class`
formájában valósul meg.

**Hol jelenik meg a projektben:** `src/leiratozo/ports/` mappa — pl.
`asr.py` (`TranscriptionEngine`), `diarization.py` (`DiarizationEngine`),
`speaker_embedding.py` (`SpeakerEmbeddingEngine`), `vad.py`
(`VoiceActivityDetector`), `aligner.py` (`Aligner`), `job_store.py`,
`session_store.py`, `profile_store.py`, `metrics.py`.

**Mit old meg a projektben:** Ez a 3 fő port (ASR, diarizáció,
speaker-embedding) rögzíti, hogy egy ML-motornak pontosan milyen
metódusokat kell nyújtania ahhoz, hogy a rendszer többi része
használni tudja, függetlenül attól, hogy ténylegesen melyik konkrét
modell fut mögötte.

### Adapter

**Általános jelentés:** Egy port konkrét, működő implementációja, ami egy
adott külső technológiát (könyvtár, modell, adatbázis) köt be a portba.

**Hol jelenik meg a projektben:** `src/leiratozo/adapters/` — pl.
`adapters/asr/faster_whisper.py`, `adapters/asr/vosk.py`,
`adapters/diarization/pyannote.py`, `adapters/speaker_embedding/resemblyzer.py`,
és minden porthoz egy `fake.py` (teszt/demó célra).

**Mit old meg a projektben:** Lehetővé teszi, hogy pl. az ASR portra 4
különböző motor (faster-whisper, Vosk, egy távoli HTTP Whisper-szolgáltatás,
és egy "fake" teszt-implementáció) is illeszkedjen, és configból
válaszható legyen köztük, kódváltoztatás nélkül.

### Domain layer (domain réteg)

**Általános jelentés:** Az üzleti/adat-modellek és a hozzájuk tartozó
szabályok rétege, technológiai függőségek (ML-könyvtár, adatbázis-driver)
nélkül.

**Hol jelenik meg a projektben:** `src/leiratozo/domain/models.py` (pl.
`AudioBuffer`, `TranscriptSegment`, `WordToken`, `SpeakerProfile`),
`domain/errors.py` (domain-szintű kivételek).

**Mit old meg a projektben:** Tiszta, ML-függőség-mentes adatstruktúrákat
ad, amiket a ports/adapters/application rétegek mind egységesen
használnak — a README is kiemeli: "domain/ — entitások, value objectek,
hibák — nincs ML-függőség".

### Application layer (alkalmazás/szolgáltatás réteg)

**Általános jelentés:** Az a réteg, ami a use case-eket (konkrét
felhasználói folyamatokat) valósítja meg, a portokat orkesztrálva —
maga a "mit csinálunk egymás után" logika.

**Hol jelenik meg a projektben:** `src/leiratozo/application/` —
`batch_service.py` (`BatchTranscriptionService`), `live_service.py`
(`LiveSessionService`), `speaker_registration_service.py`
(`SpeakerRegistrationService`), `streaming_adapter.py`.

**Mit old meg a projektben:** Például a `BatchTranscriptionService`
sorban meghívja a VAD → ASR → diarizáció → aligner → speaker-matching
lépéseket egy feltöltött hangfájlon, és összeállítja a végleges JSON
leiratot — ez a lépéssorozat van itt egy helyen definiálva, a
portoktól/adapterektől függetlenül.

### Registry / Plugin registry

**Általános jelentés:** Egy központi nyilvántartás, ami egy szöveges
azonosítót (pl. configból jövő adapter-nevet) egy konkrét, betölthető
kód-osztályra képez le, gyakran **lusta importtal** (csak akkor tölti be
a modult, amikor ténylegesen szükség van rá).

**Hol jelenik meg a projektben:** `src/leiratozo/registry/plugin_registry.py`
— egy `_REGISTRY` szótár port-kind → adapter-név → `"modul.útvonal:OsztályNév"`
leképezéssel.

**Mit old meg a projektben:** Enélkül minden ML-adapter modult (torch,
speechbrain, pyannote stb.) mindig importálni kellene induláskor, még akkor
is, ha configból csak egyet választanak ki — ez feleslegesen lassítaná az
indulást és feleslegesen sok nehéz függőséget igényelne. A lusta
(`importlib`-alapú) feloldás csak azt tölti be, amire ténylegesen szükség
van.

### DegradedAdapter / Graceful degradation (kecses leépülés)

**Általános jelentés:** Az a tervezési elv, hogy egy rendszer egy rész-hiba
esetén (pl. egy modell nem elérhető) nem omlik össze teljesen, hanem
korlátozott, de működő állapotban marad, és jelzi a hibát.

**Hol jelenik meg a projektben:** `registry/plugin_registry.py` —
`DegradedAdapter` osztály, és a README "HF token nélküli üzemmódról"
szakasza. A `GET /readyz` végpont listázza a degradált portokat.

**Mit old meg a projektben:** Ha pl. a `pyannote` diarizációs modellhez
nincs beállítva Hugging Face token/licenc-elfogadás, a szolgáltatás NEM
áll le teljesen — csak az adott port jelez "degraded" állapotot, miközben
az ASR, embedding, VAD portok továbbra is kiszolgálnak kéréseket.

### Fail-fast

**Általános jelentés:** Az a tervezési elv, hogy egy hibás/inkonzisztens
állapotot (pl. érvénytelen konfiguráció) a lehető leghamarabb, induláskor
kell jelezni és leállítani a rendszert, ahelyett hogy csendben tovább
futna hibás állapotban.

**Hol jelenik meg a projektben:** `domain/errors.py` —
`AdapterNotFoundError` docstringje: "Induláskor dobódik, ha egy configolt
adapter-azonosító nem oldható fel a plugin registryben. Ez fail-fast: a
szolgáltatás nem indul el hibás configgal." Hasonlóan: hiányzó/érvénytelen
`PROFILE_ENCRYPTION_KEY` esetén a szolgáltatás nem indul el.

**Mit old meg a projektben:** Megakadályozza, hogy pl. egy elgépelt
adapter-név, vagy egy hiányzó titkosítási kulcs csak futásidőben, egy
véletlen kérésnél derüljön ki — helyette már induláskor egyértelmű hibával
leáll.

---

## 3. Hangfeldolgozási pipeline lépései

### PCM (Pulse-Code Modulation)

**Általános jelentés:** Digitális hang nyers, tömörítetlen
mintavételezett reprezentációja — egy sorozat számérték, ami a
hanghullám amplitúdóját rögzíti adott időközönként (mintavételi
frekvencia).

**Hol jelenik meg a projektben:** `ports/audio_decoder.py` docstring:
"...egységes 16kHz mono PCM AudioBuffer-ré normalizálása."

**Mit old meg a projektben:** A bemeneti fájl formátuma (wav/mp3/m4a/ogg/
flac) bármi lehet, de az ASR/VAD/diarizáció modellek egységes, nyers PCM
formátumot várnak — az `AudioDecoder` port ezt a normalizálást végzi el
egyszer, a pipeline elején.

### Mintavételi frekvencia (sample rate) — 16 kHz mono

**Általános jelentés:** Hány mintát vesz a rendszer másodpercenként a
hangjelből (Hz-ben), és hány csatornán (mono = 1 csatorna, sztereó = 2).

**Hol jelenik meg a projektben:** `AudioDecoder` port — minden bemenet
16kHz mono PCM-mé alakul.

**Mit old meg a projektben:** A legtöbb beszédfelismerő/diarizációs modell
16kHz mono bemenetre van tanítva/optimalizálva — a normalizálás
biztosítja, hogy a modellek konzisztens, elvárt formátumú bemenetet
kapjanak, függetlenül attól, milyen minőségű/formátumú volt az eredeti
felvétel.

### VAD (Voice Activity Detection, hangaktivitás-detektálás)

**Általános jelentés:** Az a lépés, ami a hangfelvételben megkülönbözteti a
beszédet tartalmazó szakaszokat a csendtől/zajtól.

**Hol jelenik meg a projektben:** `ports/vad.py`
(`VoiceActivityDetector`), adapter: `adapters/vad/silero.py` (a Silero VAD
modellt használja, `torch.hub`-on keresztül).

**Mit old meg a projektben:** Előfeldolgozó lépésként kiszűri a néma
szakaszokat, mielőtt a (drágább) ASR/diarizáció fusson — ez a README
szerint egy "kötelező előfeldolgozó lépés" (6. kemény megkötés). Gyorsítja
a feldolgozást és javítja a diarizáció pontosságát.

### ASR (Automatic Speech Recognition, automatikus beszédfelismerés)

**Általános jelentés:** Az a technológia/folyamat, ami a hangban elhangzó
beszédet írott szöveggé alakítja.

**Hol jelenik meg a projektben:** `ports/asr.py` (`TranscriptionEngine`
port), adapterek: `faster_whisper.py`, `vosk.py`, `remote_http.py`,
`fake.py`.

**Mit old meg a projektben:** Ez a projekt egyik fő funkciója — a
`TranscriptionEngine` port absztrahálja, hogy melyik konkrét motor (helyi
Whisper-modell, Vosk, vagy egy külső HTTP-szolgáltatás) végzi a tényleges
szöveggé-alakítást, `transcribe_batch` (fájl) és opcionálisan
`transcribe_stream` (élő) metódusokkal.

### Diarizáció (speaker diarization, beszélő-szétválasztás)

**Általános jelentés:** Az a folyamat, ami egy hangfelvételben
megállapítja, hogy **ki mikor beszélt** — vagyis időszakaszokat rendel
egyes (egyelőre névtelen) beszélőkhöz (pl. "S1", "S2"), anélkül hogy
tudná, kik ők valójában.

**Hol jelenik meg a projektben:** `ports/diarization.py`
(`DiarizationEngine`), adapterek: `pyannote.py`, `nemo_msdd.py` (batch),
`diart.py` (élő). A kimeneti JSON-ban a `speaker_label` mező (pl. `"S1"`).

**Mit old meg a projektben:** A projekt neve is erre utal
("leiratozó" — beszélőnként szétbontott leirat). A README explicit kiemeli,
hogy a **batch és élő diarizáció két, architekturálisan különböző
minőségi szint** — nem ugyanaz az algoritmus két módban futtatva, ezért
külön port-kind-ek vannak (`diarization_batch` / `diarization_live`).

### Speaker embedding (beszélő-lenyomat / hangvektor)

**Általános jelentés:** Egy hangmintából egy numerikus vektort (fix
dimenziójú számsorozatot) állít elő, ami az adott beszélő hangjának
jellemzőit "sűríti be" úgy, hogy hasonló hangú beszélők vektorai
egymáshoz közel legyenek egy matematikai térben.

**Hol jelenik meg a projektben:** `ports/speaker_embedding.py`
(`SpeakerEmbeddingEngine`), adapterek: `speechbrain_ecapa.py`,
`resemblyzer.py`. Domain modell: `Embedding` (`domain/models.py`).

**Mit old meg a projektben:** Ez teszi lehetővé, hogy a rendszer egy
diarizált, de névtelen beszélő-szegmenst (`"S1"`) össze tudjon vetni egy
korábban regisztrált, **ismert** beszélő-profillal — ez alapozza meg a
beszélő-azonosítást (lásd lejjebb: cosine similarity).

### Cosine similarity (koszinusz-hasonlóság)

**Általános jelentés:** Két vektor közötti hasonlóság mértéke, ami a
köztük lévő szög koszinuszát számolja ki (1 = teljesen egyező irány, 0 =
teljesen független, -1 = ellentétes). Gyakran használt metrika
embedding-vektorok összehasonlítására.

**Hol jelenik meg a projektben:**
`application/speaker_registration_service.py` — `cosine_similarity(a, b)`
függvény, és a `similarity_threshold` (config: `speaker_matching.
similarity_threshold`).

**Mit old meg a projektben:** Amikor egy új diarizált szegmens
embedding-jét összeveti a korábban regisztrált beszélő-profilok
embedding-jeivel, a legnagyobb koszinusz-hasonlóságú profilt választja
ki — ha ez a hasonlóság a küszöb (`similarity_threshold`) felett van,
a szegmens az adott ismert beszélőhöz (`known_speaker_id`) lesz rendelve,
egyébként "unknown" marad.

### Aligner / Forced alignment (kényszerített illesztés)

**Általános jelentés:** Az a lépés, ami az ASR által felismert szavakhoz
pontos, szó-szintű időbélyeget rendel (mikor kezdődik és ér véget az adott
szó a hangfelvételben), és ezt összeilleszti a diarizációs
(beszélő-)szegmensekkel.

**Hol jelenik meg a projektben:** `ports/aligner.py` (`Aligner`),
adapter: `adapters/aligner/passthrough.py`.

**Mit old meg a projektben:** Két stratégiát absztrahál: ha az ASR motor
natívan ad szó-szintű időbélyeget (`passthrough`), azt egyszerűen
felhasználja; ha nem, egy `forced_alignment` fallback-ra lenne szükség
(dokumentált, 3. fázisban tervezett funkció). Ez teszi lehetővé, hogy a
végső JSON-ban minden szóhoz (`WordToken`) legyen pontos `start`/`end`
időbélyeg, és hogy a szavak helyesen legyenek hozzárendelve az egyes
beszélő-szegmensekhez.

### Batch mód vs. élő (live/streaming) mód

**Általános jelentés:**
- **Batch feldolgozás:** egy már teljes egészében rendelkezésre álló
  adaton (itt: egy feltöltött hangfájlon) fut le a teljes folyamat egyszerre.
- **Streaming/élő feldolgozás:** folyamatosan érkező adaton (itt: élő
  mikrofon-/hívás-audio) kell részeredményeket (`partial`) és végleges
  eredményeket (`final`) adni, ahogy az adat érkezik.

**Hol jelenik meg a projektben:** `application/batch_service.py`
(`BatchTranscriptionService`) vs. `application/live_service.py`
(`LiveSessionService`); API-ban: `POST /v1/jobs` (batch) vs.
`WS /v1/live/{session_id}` (élő, WebSocketen).

**Mit old meg a projektben:** A két mód más minőségi/architekturális
kompromisszumot igényel (pl. a diarizáció élőben csak "best-effort",
`live_approx` módú, míg batch-ben pontos, teljes-audión futó algoritmus
használható) — a rendszer ezt explicit két külön útként kezeli, nem
próbálja egy kóddal lefedni mindkettőt.

### Sliding window (csúszóablakos) streaming-közelítés

**Általános jelentés:** Olyan technika, amivel egy alapvetően nem
streaming-képes (csak teljes bemeneten dolgozó) algoritmust úgy lehet
"élőnek" álcázni, hogy a bejövő adatot átfedő, mozgó időablakokban
("csúszóablak") dolgozza fel újra és újra, és minden ablaknál
újraszámolt, közelítő részeredményt ad.

**Hol jelenik meg a projektben:**
`application/streaming_adapter.py` — `SlidingWindowStreamingAdapter`.
A `ports/asr.py` docstring külön kiemeli: "ha `capabilities.
supports_native_streaming` False... egy SlidingWindowStreamingAdapter
dekorátorral közelíti — ez explicit, dokumentált közelítés, **nem valódi
kauzális streaming**."

**Mit old meg a projektben:** Olyan ASR motorok (pl. faster-whisper),
amelyek nem támogatnak natív streaminget, így is használhatók élő módban
— a config `streaming.*` szekciója (chunk/overlap méret) vezérli ezt a
közelítést. A projekt tudatosan dokumentálja, hogy ez **nem** ugyanolyan
minőségű, mint egy natívan streaming-képes motor (pl. Vosk).

### Partial / final transzkript

**Általános jelentés:** Élő beszédfelismerésnél a "partial" egy
ideiglenes, még módosulható részeredmény (a mondat még nem ért véget),
a "final" pedig a véglegesített, már nem változó eredmény egy adott
szakaszra.

**Hol jelenik meg a projektben:** `domain/models.py` —
`PartialOrFinalTranscript`; JSON kontraktus: `is_final` mező szegmensenként;
API: `WS /v1/live/{session_id}` — "partial/final esemény ki".

**Mit old meg a projektben:** Az élő felhasználói felület (kliens) így
tud korai, gyorsan frissülő visszajelzést mutatni (partial), miközben
tudja, mely szakaszok már véglegesek és nem fognak többé változni
(final).

### RTF (Real-Time Factor)

**Általános jelentés:** A feldolgozási idő és a hangfelvétel valós
időtartamának aránya (feldolgozási_idő / hang_hossza). RTF < 1 azt
jelenti, hogy a rendszer gyorsabban dolgozza fel a hangot, mint amennyi
ideig az eredetileg tart (tehát valós idejű vagy annál gyorsabb
feldolgozásra alkalmas).

**Hol jelenik meg a projektben:** `ports/metrics.py`
(`MetricsSink.observe_rtf`).

**Mit old meg a projektben:** Mérhetővé teszi, hogy egy adott
ASR/diarizációs adapter mennyire "gyors" a valós hanghosszhoz képest —
ez fontos metrika élő/streaming használati esetekben, ahol a feldolgozás
nem lehet lassabb, mint a beszéd maga.

---

## 4. Backend / web-szolgáltatás terminológia

### REST API / végpont (endpoint)

**Általános jelentés:** HTTP-alapú felület, ahol előre definiált URL-ekhez
(végpontokhoz) és HTTP-igékhez (GET/POST/DELETE) kötött műveleteket lehet
hívni, jellemzően JSON adatformátummal.

**Hol jelenik meg a projektben:** `src/leiratozo/api/routes/` —
`jobs.py`, `speakers.py`, `health.py`, `config.py`, `live.py`. Konkrét
végpontok: `POST /v1/jobs`, `GET /v1/jobs/{id}`, `GET /v1/jobs/{id}/result`,
`POST /v1/speakers`, `GET /v1/speakers`, `DELETE /v1/speakers/{id}`.

**Mit old meg a projektben:** Ez a felület, amin keresztül egy külső
kliens (pl. egy másik alkalmazás, vagy `curl`) hangfájlt tud feltölteni,
job-státuszt lekérdezni, eredményt letölteni, és beszélő-profilokat tud
kezelni.

### FastAPI

**Általános jelentés:** Python webkeretrendszer REST API-k (és
WebSocket-ek) építésére, beépített adatvalidációval (Pydantic-alapú) és
automatikus OpenAPI/Swagger dokumentáció-generálással.

**Hol jelenik meg a projektben:** `src/leiratozo/api/app.py` — az
alkalmazás FastAPI-alapú; a README említi a `/docs` végpontot (automatikus
API-dokumentáció).

**Mit old meg a projektben:** Ez szolgálja ki a HTTP/WebSocket API-t
(`worker` service a `docker-compose.yml`-ben), és adja az automatikusan
generált interaktív API-dokumentációt (`/docs`).

### WebSocket

**Általános jelentés:** Kétirányú, folyamatos (tartós) hálózati
kapcsolat protokoll, ami — a hagyományos HTTP kérés-válasz modelltől
eltérően — lehetővé teszi, hogy a szerver és a kliens bármikor, aszinkron
módon küldjenek egymásnak üzeneteket ugyanazon a nyitva tartott
kapcsolaton.

**Hol jelenik meg a projektben:** `WS /v1/live/{session_id}` végpont
(`api/routes/live.py`).

**Mit old meg a projektben:** Az élő (streaming) leiratozáshoz szükséges,
hiszen a kliens folyamatosan küldi az audio-chunk-okat, a szerver pedig
folyamatosan (partial/final) transzkript-eseményeket küld vissza —
ehhez egy hagyományos, egyszeri HTTP-kérés-válasz nem elég.

### Job / Job queue (feladat / feladatsor)

**Általános jelentés:** Egy "job" egy háttérben elvégzendő, jellemzően
hosszabb ideig tartó munkaegység, amit nem szinkron módon, a kérés-válasz
cikluson belül végeznek el, hanem beütemezve, egy sorba (queue) állítva,
és egy külön "worker" folyamat dolgoz fel.

**Hol jelenik meg a projektben:** `domain/models.py` —
`TranscriptJob`; `ports/job_store.py` — `JobStore`; `queue/worker.py` —
`arq` worker; API: `POST /v1/jobs`, `GET /v1/jobs/{id}`.

**Mit old meg a projektben:** Egy hangfájl leiratozása percekig is
eltarthat — ezért a kliens nem várja meg szinkron módon: feltölti a
fájlt, azonnal kap egy `job_id`-t, majd külön kérdezi le a státuszt/
eredményt, miközben a tényleges feldolgozás egy háttér-worker
processzben, egy sorból kiolvasva zajlik.

### arq / Redis-queue

**Általános jelentés:** Az `arq` egy Python könyvtár aszinkron
háttér-feladatok (job-ok) Redis-alapú sorba állítására és feldolgozására
— hasonló céllal, mint pl. a Celery, de `asyncio`-natívan. A **Redis** egy
memóriában tárolt, gyors kulcs-érték adattár, amit itt üzenet-/
feladatsorként (message queue) használnak.

**Hol jelenik meg a projektben:** `src/leiratozo/queue/worker.py`
(`WorkerSettings`, `on_startup`/`on_shutdown`/`run_batch_job`),
`docker-compose.yml` — `arq-worker` és `redis` service-ek. Config:
`queue.backend: redis`.

**Mit old meg a projektben:** Production üzemmódban (`queue.backend:
redis`) a batch job-feldolgozás egy **külön processzben** (`arq-worker`)
fut, elválasztva a HTTP API-t kiszolgáló `worker` service-től — így egy
hosszú ideig tartó leiratozási feladat nem blokkolja/terheli az API
válaszidejét, és a workerek száma is függetlenül skálázható. Dev/teszt
módban az `inline` backend (szinkron, azonnali feldolgozás, Redis
nélkül) egyszerűbb, gyorsabb iterációt tesz lehetővé.

### Healthz / Readyz (liveness / readiness probe)

**Általános jelentés:** Két gyakori "egészség-ellenőrző" HTTP-végpont
konvenció konténerizált/orkesztrált szolgáltatásoknál:
- **Liveness** (`/healthz`): "fut-e egyáltalán a folyamat" — ha nem
  válaszol, a rendszer (pl. Kubernetes) újraindítja a konténert.
- **Readiness** (`/readyz`): "készen áll-e valódi kérések kiszolgálására"
  — akkor is lehet "nem kész", ha a folyamat fut, de pl. egy függő
  modell/erőforrás még nem érhető el.

**Hol jelenik meg a projektben:** `api/routes/health.py` — `GET /healthz`
és `GET /readyz` (utóbbi a degradált portok listájával).

**Mit old meg a projektben:** A `/readyz` konkrétan felsorolja, mely
portok futnak `degraded` állapotban (pl. hiányzó HF-token miatt) — ez
lehetővé teszi, hogy egy külső monitorozó/orkesztráló rendszer (vagy
egyszerűen egy adminisztrátor) lássa, hogy a szolgáltatás technikailag fut,
de esetleg csökkentett funkcionalitással.

### Correlation ID

**Általános jelentés:** Egy egyedi azonosító, amit egy adott kérés/job
összes kapcsolódó log-bejegyzéséhez, metrikájához hozzáfűznek, hogy
utólag egy elosztott rendszerben is össze lehessen kötni, mely
log-sorok tartoznak ugyanahhoz a kéréshez.

**Hol jelenik meg a projektben:** `ports/metrics.py` —
`observe_processing_time(*, correlation_id: str, ...)`.

**Mit old meg a projektben:** Lehetővé teszi, hogy egy adott `job_id`
vagy `session_id` teljes feldolgozási útját (VAD → ASR → diarizáció →
...) egységesen nyomon lehessen követni a metrikákban/logokban, még akkor
is, ha a feldolgozás több lépésben/komponensben történik.

### Strukturált logolás (structured logging)

**Általános jelentés:** Naplózási módszer, ahol a log-üzenetek nem
szabad szöveges mondatok, hanem gépileg is feldolgozható, strukturált
(jellemzően JSON) formátumúak — mezőkkel (pl. `level`, `timestamp`,
`job_id`, `message`).

**Hol jelenik meg a projektben:** `src/leiratozo/logging_setup.py`.

**Mit old meg a projektben:** Egyrészt megkönnyíti a log-elemzést/
keresést (pl. log-aggregátor eszközökben); másrészt itt kifejezetten
adatvédelmi célt is szolgál — a logger egy explicit **tiltólistát**
alkalmaz, hogy érzékeny adat (nyers audio, embedding, `display_name`)
soha ne kerülhessen bele a strukturált logba.

---

## 5. Konfiguráció

### YAML

**Általános jelentés:** Ember által is könnyen olvasható,
behúzás-alapú szöveges adatszerializációs formátum, gyakran használt
konfigurációs fájlokhoz.

**Hol jelenik meg a projektben:** `config/config.example.yaml`,
`config/config.fake.yaml`, `config/config.remote-whisper.yaml`.

**Mit old meg a projektben:** Ebben van deklarálva, hogy melyik adapter
töltődjön be az egyes portokhoz (`models.asr.adapter: vosk` stb.), és az
összes egyéb futásidejű paraméter (device, queue backend, storage,
speaker-matching küszöb, streaming chunk-méret, biztonsági beállítások).

### Pydantic / pydantic-settings

**Általános jelentés:** Python könyvtár, ami Python
típusannotációkból automatikusan adatvalidációt és -parse-olást végez;
a `pydantic-settings` kiterjesztése ezt konfiguráció-betöltésre
specializálja (több forrásból: kód-default, fájl, környezeti változó).

**Hol jelenik meg a projektben:** `src/leiratozo/config/schema.py`
(a konfiguráció sémája), `config/loader.py` (a rétegzett betöltő).

**Mit old meg a projektben:** Biztosítja, hogy a betöltött konfiguráció
típushelyesen és validáltan álljon rendelkezésre (pl. elgépelt vagy
hiányzó mező már induláskor kiderül — lásd fail-fast), és egységesen
kezeli a több forrásból (YAML + env) jövő értékek egyesítését.

### Rétegzett konfiguráció-betöltés és 12-factor elv

**Általános jelentés:** A "12-factor app" egy elterjedt
alkalmazás-tervezési alapelv-gyűjtemény, amelynek egyik pontja, hogy a
konfigurációt **környezeti változókban** kell tárolni, nem a kódba
égetve — így ugyanaz a kódbázis, változtatás nélkül, eltérő
környezetekben (dev/staging/prod) is futtatható eltérő beállításokkal.

**Hol jelenik meg a projektben:** README: "Rétegzett betöltés:
kód-defaultok → `CONFIG_PATH` alatti YAML → környezeti változók (env
mindig nyer, 12-factor)." Env-override szintaxis: `MODELS__ASR__ADAPTER=vosk`
(dupla aláhúzás = beágyazott kulcs elválasztó).

**Mit old meg a projektben:** Lehetővé teszi, hogy pl. egy Docker-
konténerben induló szolgáltatás konfigurációját futásidőben, a YAML
fájl módosítása nélkül, egyszerű környezeti változókkal felül lehessen
írni (pl. CI/CD, titkok injektálása).

### `.env` fájl

**Általános jelentés:** Egyszerű, `KULCS=érték` sorokból álló fájl,
amiből az alkalmazás induláskor környezeti változókat tölt be — gyakran
titkok (jelszavak, tokenek), amiket nem szabad verziókezelőbe (git)
belekerülniük.

**Hol jelenik meg a projektben:** `.env.example` (sablon, git alatt),
amiből `cp .env.example .env` paranccsal hozható létre a valódi (git alól
kizárt) `.env`.

**Mit old meg a projektben:** A `docker compose` innen olvassa be pl. a
`HF_TOKEN`-t vagy a `PROFILE_ENCRYPTION_KEY`-t anélkül, hogy ezek a
verziókezelt konfigurációs fájlokba (YAML) kerülnének.

---

## 6. Adattárolás

### SQLite

**Általános jelentés:** Egyetlen fájlba szervezett, szerver nélküli
relációs adatbázis-motor — nincs külön adatbázis-szerver folyamat,
maga a program fájlban tárolja az adatokat.

**Hol jelenik meg a projektben:** `src/leiratozo/adapters/storage/`
— `job_store_sqlite.py`, `session_store_sqlite.py`,
`profile_store_encrypted_sqlite.py`.

**Mit old meg a projektben:** Egyszerű, külön infrastruktúra
(adatbázis-szerver) nélküli perzisztenciát ad a job-oknak, élő
session-öknek és a regisztrált beszélő-profiloknak — ideális egy
önálló worker/POC-szintű rendszerhez, ahol nem indokolt egy külön
adatbázis-szerver üzemeltetése.

### Fernet (szimmetrikus titkosítás)

**Általános jelentés:** A Python `cryptography` könyvtár által
biztosított, egyszerűen használható szimmetrikus titkosítási séma (egy
kulcs a titkosításhoz ÉS a visszafejtéshez is), ami hitelesítést
(authenticated encryption) is végez, tehát az is kiderül, ha valaki
módosította a titkosított adatot.

**Hol jelenik meg a projektben:**
`adapters/storage/profile_store_encrypted_sqlite.py`; README: "az
`encrypted_sqlite` ProfileStore mezőszinten (Fernet) titkosítja az
embedding-vektort és a `display_name`-et."

**Mit old meg a projektben:** Ez biztosítja a GDPR-kötelezettséget
("titkosítás nyugalmi állapotban" / *encryption at rest*): a biometrikus
adat (hangvektor) és a személynév még akkor sem olvasható ki nyers
formában az adatbázis-fájlból, ha valaki hozzáfér a fájlhoz, csak a
`PROFILE_ENCRYPTION_KEY` env-változóban tárolt kulcs ismeretében.

---

## 7. Adatvédelem (GDPR) fogalmak

### GDPR (General Data Protection Regulation)

**Általános jelentés:** Az Európai Unió általános adatvédelmi
rendelete, ami szigorú szabályokat ír elő a személyes adatok
kezelésére — különösen a "különleges kategóriájú" adatokra (pl.
biometrikus adat).

**Hol jelenik meg a projektben:** README "Adatvédelem (GDPR)" szakasza;
`docs/phase1-terv.md` 6. szakasza.

**Mit old meg a projektben:** A rendszer egy **biometrikus** adatot
(a beszélő hangjának embedding-vektorát) tárol el a beszélő-azonosítás
funkcióhoz — ez explicit GDPR-relevanciát von maga után, amit a rendszer
tudatosan, dedikált tervezési döntésekkel (titkosítás, hard delete,
tiltólistás logolás, retenció) kezel.

### Biometrikus / különleges kategóriájú személyes adat

**Általános jelentés:** A GDPR külön, szigorúbb védelmet ír elő olyan
adatokra, amik egy személy testi/fiziológiai/viselkedési
jellemzőiből egyedi azonosítást tesznek lehetővé (pl. ujjlenyomat,
arckép, hangprofil).

**Hol jelenik meg a projektben:** A regisztrált `SpeakerProfile`
embedding-vektora — README: "A regisztrált speaker-profil biometrikus,
különleges kategóriájú személyes adat."

**Mit old meg a projektben:** Ez indokolja, hogy a speaker-embedding
miért kap külön, szigorúbb bánásmódot (kötelező titkosítás,
tiltólistás logolás) a rendszer többi adatához (pl. maga a szöveges
transzkript) képest.

### Right to erasure / hard delete (törléshez való jog)

**Általános jelentés:** A GDPR egyik alapjoga, hogy egy érintett
személy kérheti a rá vonatkozó személyes adatok **végleges** törlését.
A "hard delete" azt jelenti, hogy az adat ténylegesen, visszaállíthatatlanul
törlődik — szemben a "soft delete"-tel, ahol csak egy "törölt" jelzőt
állítanak be, de az adat fizikailag megmarad.

**Hol jelenik meg a projektben:** `DELETE /v1/speakers/{id}` végpont;
`ports/profile_store.py` — `delete()` docstring: "Hard delete, nem soft."

**Mit old meg a projektben:** Biztosítja, hogy egy beszélő
profiljának törlésekor az embedding és a személyes adat ténylegesen,
maradék nélkül eltűnjön az adatbázisból, megfelelve a GDPR törléshez
való jogának.

### Retenció / adatmegőrzési idő (retention)

**Általános jelentés:** Az az időtartam, ameddig egy rendszer egy adott
adatot jogosan megőrizhet, mielőtt automatikusan törölnie kellene.

**Hol jelenik meg a projektben:** Config: `retention.
profile_retention_days`.

**Mit old meg a projektben:** Lehetővé teszi (opcionálisan) a
beszélő-profilok automatikus lejáratának beállítását — alapértelmezésben
nincs auto-lejárat, csak az explicit `DELETE` törli a profilt.

### UUID (Universally Unique Identifier)

**Általános jelentés:** Egy szabványos formátumú, gyakorlatilag
egyedi (ütközésmentes), véletlenszerűen generált azonosító, amit
elosztott rendszerekben is biztonságosan lehet központi koordináció
nélkül generálni.

**Hol jelenik meg a projektben:** `profile_id` (README: "random UUID,
nem a személy neve"), `job_id`, `session_id` hasonlóan generált
azonosítók.

**Mit old meg a projektben:** Biztosítja, hogy egy beszélő-profil
azonosítója **ne** hordozzon személyes információt (pl. ne legyen a
személy neve vagy ebből képzett string) — ez önmagában is
adatvédelmi jó gyakorlat (az azonosító és a hozzá tartozó
`display_name` külön mezőkben, a `display_name` pedig titkosítva van).

---

## 8. ML-modellekhez kapcsolódó fogalmak

### Gated model / licenc-elfogadás (Hugging Face token)

**Általános jelentés:** Néhány publikusan elérhető ML-modellt a
kiadója csak azoknak enged letölteni/használni, akik előzetesen
elfogadják a modell licencfeltételeit (jellemzően egy fiókkal
azonosítva, egy hozzáférési token/kulcs kiadásával).

**Hol jelenik meg a projektben:** Config: `security.
huggingface_token_env` — mely env-változóban várja a HF tokent a
`pyannote`/`diart` adapter.

**Mit old meg a projektben:** A `pyannote` és `diart` diarizációs
modellek gated licencűek — a projekt ezt tudatosan **nem** teszi
kötelezővé: `HF_TOKEN` nélkül a rendszer elindul, csak az adott port
lesz `degraded` (lásd: DegradedAdapter), a többi funkció zavartalanul
működik.

### Device: `auto` / `cpu` / `cuda`

**Általános jelentés:** Megadja, hogy egy ML-modell számításai melyik
hardveren fussanak: `cpu` = processzoron, `cuda` = NVIDIA GPU-n (a CUDA
NVIDIA GPU-gyorsítási platform neve), `auto` = a rendszer automatikusan
eldönti, elérhető-e GPU.

**Hol jelenik meg a projektben:** Config: `device.default`.

**Mit old meg a projektben:** Lehetővé teszi, hogy ugyanaz a
konfiguráció eltérő hardver-környezetekben (fejlesztői gép GPU
nélkül vs. GPU-val rendelkező szerver) is működjön, anélkül hogy a
kódot módosítani kellene.

### Confidence score (megbízhatósági/konfidencia érték)

**Általános jelentés:** Egy 0 és 1 közötti (vagy százalékos) érték,
amit egy ML-modell ad a saját predikciója mellé, jelezve, mennyire
"biztos" az adott eredményben.

**Hol jelenik meg a projektben:** JSON kontraktus: `asr_confidence`
(szegmensenként), `confidence` (szavanként, `WordToken`),
`speaker_match_confidence` (beszélő-egyeztetéshez).

**Mit old meg a projektben:** Lehetővé teszi a leirat fogyasztói
(kliens-alkalmazás, felhasználó) számára, hogy megkülönböztesse a
biztosan, illetve a bizonytalanul felismert szövegrészeket/beszélő-
hozzárendeléseket — pl. UI-ban kiemelhető, mi igényel emberi
ellenőrzést.

---

## 9. Tesztelés

### Unit teszt / integrációs teszt / kontraktus-teszt (contract test)

**Általános jelentés:**
- **Unit teszt:** egyetlen, kis egységet (pl. egy függvényt/osztályt)
  tesztel, elszigetelve a többi komponenstől.
- **Integrációs teszt:** több komponens **együttes** működését teszteli
  (pl. egy teljes szolgáltatás-réteg valódi vagy fake adapterekkel).
- **Kontraktus-teszt (contract test):** azt ellenőrzi, hogy egy adott
  kimenet (itt: a JSON leirat) megfelel-e egy előre rögzített
  formátum-szerződésnek (sémának).

**Hol jelenik meg a projektben:** `tests/unit/`, `tests/integration/`,
`tests/contract/`.

**Mit old meg a projektben:** A `contract` tesztek biztosítják, hogy a
kimeneti JSON mindig megfeleljen a `schema_version: "1.0"` szerződésnek
(`contracts/transcript_schema.py`) — ez különösen fontos egy olyan
rendszerben, ahol a kimenetet más, külső rendszerek fogyasztják, és a
formátum-stabilitás alapkövetelmény.

### pytest

**Általános jelentés:** A legelterjedtebb Python teszt-futtató
keretrendszer.

**Hol jelenik meg a projektben:** `pytest -q` (README, "Gyors indítás"
és "Tesztek" szakasz), `pyproject.toml`.

**Mit old meg a projektben:** Ezzel futtatható a teljes teszt-suite;
a README kiemeli, hogy `fake` adapterekkel, ML-függőség nélkül **mindig
zöldnek** kell lennie — ez egy gyors, megbízható smoke-teszt/CI-alap,
míg a valódi ML-adapterek tesztjei hiányzó függőség esetén automatikusan
**skip**-elnek (nem buknak el hamisan).

### Fake adapter

**Általános jelentés:** Egy port egyszerű, determinisztikus, "kamu"
implementációja, ami nem végez valódi (pl. ML-alapú) munkát, csak
előre kiszámítható, gyors választ ad — tesztelésre/demózásra.

**Hol jelenik meg a projektben:** Minden port alatt egy `fake.py` (pl.
`adapters/asr/fake.py`), és a `config/config.fake.yaml` ezekkel a
adapterekkel konfigurálja a rendszert.

**Mit old meg a projektben:** Lehetővé teszi, hogy a teljes
API/pipeline **ML-modellek és nehéz függőségek (torch, GPU stb.)
nélkül**, gyorsan, determinisztikusan tesztelhető és demózható legyen —
ez a README szerint kifejezett cél: "demó/CI-smoke-teszt".

### Smoke test (füst-teszt)

**Általános jelentés:** Egy gyors, felületes teszt, ami csak azt
ellenőrzi, hogy a rendszer alapvetően elindul és a legfontosabb
útvonalak nem törnek el azonnal — nem helyettesíti a részletes
teszteket, de gyorsan kiszűri a durva hibákat.

**Hol jelenik meg a projektben:** README: "fake adapterek, gyors
smoke-teszt" (Docker Compose szakasz).

**Mit old meg a projektben:** Gyors visszajelzést ad arra, hogy egy
build/deploy alapvetően működőképes-e, mielőtt a lassabb, valódi
ML-modelles teszteket futtatnák.

---

## 10. Konténerizáció

### Docker / konténer

**Általános jelentés:** A Docker egy technológia, ami egy alkalmazást
a teljes futtatási környezetével (függőségek, könyvtárak, beállítások)
együtt egy elszigetelt, hordozható egységbe (**konténerbe**) csomagol,
ami bármilyen Docker-t támogató gépen ugyanúgy futtatható.

**Hol jelenik meg a projektben:** `Dockerfile`, `.dockerignore`,
`docker-compose.yml`.

**Mit old meg a projektben:** Biztosítja, hogy a szolgáltatás
(worker, arq-worker, redis) konzisztensen, a fejlesztői géptől
függetlenül futtatható és telepíthető legyen.

### Multi-stage build (többlépcsős build)

**Általános jelentés:** Egy Dockerfile-technika, ahol több egymást
követő "build szakasz" (stage) van definiálva — pl. az egyik stage
fordítja/telepíti a nehéz build-függőségeket, a végső stage pedig
csak a futtatáshoz szükséges, kész eredményt másolja át, elhagyva a
felesleges build-eszközöket. Ez kisebb, tisztább végső image-et
eredményez.

**Hol jelenik meg a projektben:** `Dockerfile` — README: "többlépcsős
Dockerfile".

**Mit old meg a projektben:** Kisebb, gyorsabban letölthető/futtatható
végső konténer-image-et biztosít, elkerülve, hogy a build-hez szükséges
(de futtatáshoz felesleges) eszközök bekerüljenek a végleges image-be.

### Docker Compose / service

**Általános jelentés:** Eszköz több, egymással együttműködő Docker-
konténer (ún. "service") egyetlen konfigurációs fájlból történő
együttes indítására/kezelésére.

**Hol jelenik meg a projektben:** `docker-compose.yml` — `worker`,
`arq-worker`, `redis` service-ek.

**Mit old meg a projektben:** Egyetlen paranccsal (`docker compose up`)
elindítja az összes szükséges, egymástól függő komponenst (API-szerver,
háttér-worker, Redis) a helyes hálózati összekapcsolással együtt.

---

## 11. Dokumentáció / diagramok

### UML (Unified Modeling Language)

**Általános jelentés:** Szabványosított, széles körben elfogadott
grafikus jelölésrendszer szoftverrendszerek felépítésének és
viselkedésének ábrázolására (pl. osztálydiagram, szekvenciadiagram,
komponensdiagram).

**Hol jelenik meg a projektben:** `docs/architecture/` mappa teljes
tartalma.

**Mit old meg a projektben:** Szabványos, más fejlesztők/diákok
számára is ismerős jelöléssel dokumentálja a rendszer architektúráját,
nem projekt-specifikus, egyedi ábrázolással.

### Szekvenciadiagram (sequence diagram)

**Általános jelentés:** UML-diagramtípus, ami komponensek/szereplők
közötti üzenetváltásokat mutatja be **időrendi sorrendben**, függőleges
"élettartam-sávokkal" (lifeline) és vízszintes nyilakkal (hívás/
visszatérés).

**Hol jelenik meg a projektben:**
`docs/architecture/01-sequence-batch-flow.md`.

**Mit old meg a projektben:** Megmutatja pontosan, milyen sorrendben
hívja meg a `BatchTranscriptionService` a VAD → ASR → diarizáció →
aligner → speaker-matching lépéseket egy batch kérés feldolgozása
során.

### Komponensdiagram (component diagram)

**Általános jelentés:** UML-diagramtípus, ami egy rendszer nagyobb
építőelemeit (komponenseit) és a köztük lévő függőségi/kapcsolódási
viszonyokat mutatja be, gyakran `<<component>>` sztereotípiával jelölve.

**Hol jelenik meg a projektben:**
`docs/architecture/02-component-context.md` (kontextus-nézet: kliensek,
fogyasztók, infrastruktúra), `docs/architecture/03-port-adapter-
components.md` (port-adapter nézet).

**Mit old meg a projektben:** Megmutatja a worker külső kapcsolódási
pontjait (kliensek, Redis, storage), illetve azt, hogy a 3 fő port
(mint UML `<<interface>>`) mögött mely konkrét adapterek "realizálják"
(`..|>` nyíl) az adott interfészt.

### Mermaid

**Általános jelentés:** Szöveges (kód-szerű) szintaxissal írt
diagram-leíró nyelv/eszköz, ami Markdown-ban is renderelhető
diagramokat (folyamatábra, szekvenciadiagram, osztálydiagram stb.) tud
generálni egyszerű szöveges definícióból.

**Hol jelenik meg a projektben:** `docs/architecture/*.md` fájlok
kódblokkjai (` ```mermaid `).

**Mit old meg a projektben:** Lehetővé teszi, hogy a diagramok
**szövegesen, verziókezelhetően** (git-ben diff-elhetően) legyenek
tárolva a kódbázis mellett, ahelyett hogy külön, bináris
rajzoló-eszközzel készült képfájlokat kellene karbantartani.

---

## 12. JSON kimeneti kontraktus — kulcsfogalmak

### Schema / séma (és `schema_version`)

**Általános jelentés:** Egy adatszerkezet formális leírása (milyen
mezők, milyen típussal, kötelezőek-e), ami alapján ellenőrizhető, hogy
egy konkrét adat megfelel-e az elvárt formátumnak. A verziószám
(`schema_version`) jelzi, ha a formátum idővel változik.

**Hol jelenik meg a projektben:**
`src/leiratozo/contracts/transcript_schema.py` —
`"schema_version": "1.0"`.

**Mit old meg a projektben:** Garantálja, hogy a kimeneti JSON leirat
formátuma **stabil és dokumentált szerződés** legyen a rendszer és a
kimenetet fogyasztó külső rendszerek között — ha a formátum jövőben
változik, azt a verziószám emelése jelzi, nem váratlan, néma
mezőváltozás.

### Segment (szegmens)

**Általános jelentés:** A teljes hangfelvétel/leirat egy időben
körülhatárolt, összefüggő darabja (itt: egy beszélő egy
megszólalása), saját kezdő/vég időbélyeggel.

**Hol jelenik meg a projektben:** JSON kontraktus `segments` tömbje —
mezők: `segment_id`, `start`, `end`, `text`, `speaker_label`,
`known_speaker_id`, `speaker_match_confidence`, `asr_confidence`,
`is_final`, `words`.

**Mit old meg a projektben:** Ez a leirat alapvető építőeleme — minden
egyes, egy beszélőhöz köthető, összefüggő megszólalást egy `segments`
tömb-elem reprezentál, benne a felismert szöveggel, a beszélő
azonosításával és a szó-szintű bontással (`words`).

### Speaker aggregates (beszélőnkénti összesítés)

**Általános jelentés:** Egy nyers, szegmensenkénti adatsorból
képzett, beszélőnként csoportosított összesítő nézet (pl. összes
beszédidő, hány szegmens tartozik az adott beszélőhöz).

**Hol jelenik meg a projektben:** JSON kontraktus
`speaker_aggregates` tömbje — `speaker_label`, `known_speaker_id`,
`total_speech_sec`, `segment_ids`.

**Mit old meg a projektben:** A fogyasztó alkalmazásnak nem kell
magának végigszámolnia az összes szegmensen, hogy pl. mennyit
beszélt összesen egy adott résztvevő — ezt a rendszer előre
kiszámolva mellékeli a válaszhoz.

---

## Alfabetikus gyorskereső

Az összes szócikk ABC-sorrendben, gyors visszakereséshez (a témakör
szerinti sorrendhez lásd a [tartalomjegyzéket](#tartalomjegyzék)).

- [`.env` fájl](#env-fájl) — 5. szakasz
- [Adapter](#adapter) — 2. szakasz
- [Aligner / Forced alignment (kényszerített illesztés)](#aligner-forced-alignment-kényszerített-illesztés) — 3. szakasz
- [Application layer (alkalmazás/szolgáltatás réteg)](#application-layer-alkalmazásszolgáltatás-réteg) — 2. szakasz
- [arq / Redis-queue](#arq-redis-queue) — 4. szakasz
- [ASR (Automatic Speech Recognition, automatikus beszédfelismerés)](#asr-automatic-speech-recognition-automatikus-beszédfelismerés) — 3. szakasz
- [Batch mód vs. élő (live/streaming) mód](#batch-mód-vs-élő-livestreaming-mód) — 3. szakasz
- [Biometrikus / különleges kategóriájú személyes adat](#biometrikus-különleges-kategóriájú-személyes-adat) — 7. szakasz
- [Confidence score (megbízhatósági/konfidencia érték)](#confidence-score-megbízhatóságikonfidencia-érték) — 8. szakasz
- [Correlation ID](#correlation-id) — 4. szakasz
- [Cosine similarity (koszinusz-hasonlóság)](#cosine-similarity-koszinusz-hasonlóság) — 3. szakasz
- [DegradedAdapter / Graceful degradation (kecses leépülés)](#degradedadapter-graceful-degradation-kecses-leépülés) — 2. szakasz
- [Device: `auto` / `cpu` / `cuda`](#device-auto-cpu-cuda) — 8. szakasz
- [Diarizáció (speaker diarization, beszélő-szétválasztás)](#diarizáció-speaker-diarization-beszélő-szétválasztás) — 3. szakasz
- [Docker / konténer](#docker-konténer) — 10. szakasz
- [Docker Compose / service](#docker-compose-service) — 10. szakasz
- [Domain layer (domain réteg)](#domain-layer-domain-réteg) — 2. szakasz
- [Fail-fast](#fail-fast) — 2. szakasz
- [Fake adapter](#fake-adapter) — 9. szakasz
- [FastAPI](#fastapi) — 4. szakasz
- [Fernet (szimmetrikus titkosítás)](#fernet-szimmetrikus-titkosítás) — 6. szakasz
- [Gated model / licenc-elfogadás (Hugging Face token)](#gated-model-licenc-elfogadás-hugging-face-token) — 8. szakasz
- [GDPR (General Data Protection Regulation)](#gdpr-general-data-protection-regulation) — 7. szakasz
- [Healthz / Readyz (liveness / readiness probe)](#healthz-readyz-liveness-readiness-probe) — 4. szakasz
- [Hexagonális architektúra / Ports & Adapters](#hexagonális-architektúra-ports-adapters) — 2. szakasz
- [Job / Job queue (feladat / feladatsor)](#job-job-queue-feladat-feladatsor) — 4. szakasz
- [Komponensdiagram (component diagram)](#komponensdiagram-component-diagram) — 11. szakasz
- [Mermaid](#mermaid) — 11. szakasz
- [Mintavételi frekvencia (sample rate) — 16 kHz mono](#mintavételi-frekvencia-sample-rate-16-khz-mono) — 3. szakasz
- [Multi-stage build (többlépcsős build)](#multi-stage-build-többlépcsős-build) — 10. szakasz
- [Partial / final transzkript](#partial-final-transzkript) — 3. szakasz
- [PCM (Pulse-Code Modulation)](#pcm-pulse-code-modulation) — 3. szakasz
- [Port](#port) — 2. szakasz
- [Pydantic / pydantic-settings](#pydantic-pydantic-settings) — 5. szakasz
- [pytest](#pytest) — 9. szakasz
- [Registry / Plugin registry](#registry-plugin-registry) — 2. szakasz
- [REST API / végpont (endpoint)](#rest-api-végpont-endpoint) — 4. szakasz
- [Retenció / adatmegőrzési idő (retention)](#retenció-adatmegőrzési-idő-retention) — 7. szakasz
- [Right to erasure / hard delete (törléshez való jog)](#right-to-erasure-hard-delete-törléshez-való-jog) — 7. szakasz
- [RTF (Real-Time Factor)](#rtf-real-time-factor) — 3. szakasz
- [Rétegzett konfiguráció-betöltés és 12-factor elv](#rétegzett-konfiguráció-betöltés-és-12-factor-elv) — 5. szakasz
- [Schema / séma (és `schema_version`)](#schema-séma-és-schema_version) — 12. szakasz
- [Segment (szegmens)](#segment-szegmens) — 12. szakasz
- [Sliding window (csúszóablakos) streaming-közelítés](#sliding-window-csúszóablakos-streaming-közelítés) — 3. szakasz
- [Smoke test (füst-teszt)](#smoke-test-füst-teszt) — 9. szakasz
- [Speaker aggregates (beszélőnkénti összesítés)](#speaker-aggregates-beszélőnkénti-összesítés) — 12. szakasz
- [Speaker embedding (beszélő-lenyomat / hangvektor)](#speaker-embedding-beszélő-lenyomat-hangvektor) — 3. szakasz
- [SQLite](#sqlite) — 6. szakasz
- [Strukturált logolás (structured logging)](#strukturált-logolás-structured-logging) — 4. szakasz
- [Szekvenciadiagram (sequence diagram)](#szekvenciadiagram-sequence-diagram) — 11. szakasz
- [UML (Unified Modeling Language)](#uml-unified-modeling-language) — 11. szakasz
- [Unit teszt / integrációs teszt / kontraktus-teszt (contract test)](#unit-teszt-integrációs-teszt-kontraktus-teszt-contract-test) — 9. szakasz
- [UUID (Universally Unique Identifier)](#uuid-universally-unique-identifier) — 7. szakasz
- [VAD (Voice Activity Detection, hangaktivitás-detektálás)](#vad-voice-activity-detection-hangaktivitás-detektálás) — 3. szakasz
- [WebSocket](#websocket) — 4. szakasz
- [YAML](#yaml) — 5. szakasz

---

## Kapcsolódó dokumentumok

- [`../README.md`](../README.md) — gyors indítás, projektszerkezet,
  végpontok, adatvédelem áttekintése.
- [`phase1-terv.md`](phase1-terv.md) — a teljes, részletes tervdokumentum
  (minden itt említett fogalom eredeti, bővebb kifejtése).
- [`architecture/README.md`](architecture/README.md) és a hozzá tartozó
  3 UML-diagram — vizuálisan mutatja be a fenti fogalmak közötti
  kapcsolatokat.
- [`tradeoffs_and_decisions.md`](tradeoffs_and_decisions.md) — miért
  ezekkel a technológiai döntésekkel készült a rendszer.
