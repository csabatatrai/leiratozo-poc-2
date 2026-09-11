# Manuális teszt-jegyzetek — 2026-09-12

Ez a dokumentum egy konkrét, valós teszt-munkamenet tapasztalatait rögzíti: a
felhasználó megadott egy `felvetel.wav` fájlt (helyben, gitignore-olva, ld.
`.gitignore`) és egy éles, külső HTTP ASR-végpontot
(`http://192.168.100.7:8001` — egy IDEIGLENES teszt-végpont, "Whisper-large-v3-hu"
nevű szolgáltatás; ld. `adapters/asr/remote_http.py` modul docstring: ez CSAK
egy példány, nem architekturális függőség). A cél: kipróbálni a teljes
pipeline-t valós audio-n, valós (nem `fake`) ASR-lel.

**A teszt-fájl:** 911.8 mp (~15.2 perc), sztereó, 44.1 kHz PCM wav. Tartalma
(a baseline-átirat alapján): magyar nyelvű hírműsor/interjú-részlet,
**legalább 2, jól elkülönülő beszélővel** (riporter + interjúalany,
kérdés-válasz váltásokkal — jó jelölt egy jövőbeli diarizációs teszt-esetnek).
Idő/terhelés-kímélés miatt a legtöbb tesztet egy **60 másodperces**, illetve
egy **20 másodperces** kivágott részleten futtattam, nem a teljes 15 percen.

---

## Mi lett tesztelve ma — állapot-táblázat

| Terület | Állapot | Megjegyzés |
|---|---|---|
| Baseline: nyers hívás a külső ASR-végpontra | ✅ | `curl`+valós audio, pontos válaszséma felderítve (`text`, `segments:[{start,end,text}]`) |
| Harmadik ASR-adapter (`remote_http`) megírása+tesztje | ✅ | Szintetikus beszéddel (espeak-ng) és a valós végponttal is |
| Batch pipeline (`POST /v1/jobs`) valódi távoli ASR-lel | ✅ | A kimenet szövege **pontosan megegyezik** a baseline-nal — a pipeline nem torzítja/veszíti el a szöveget |
| JSON-kontraktus batch módban (schema_version, segments, speaker_aggregates) | ✅ | Helyesen kitöltve, valódi adaton |
| Élő mód (WebSocket) mechanika — partial/final események, session-kezelés | ✅ | Miután 2 valós hibát találtam és javítottam (ld. lent) |
| Élő mód hosszabb (60 mp) munkamenetben, valós hálózaton | ⚠️ részleges | Lásd "Nyitott/tisztázatlan" szakasz — a külső végpont válaszideje a teszt végére jelentősen megnőtt |
| Docker build+run+curl (korábbi munkamenetből) | ✅ | Ld. `docs/tradeoffs_and_decisions.md` |
| GDPR titkosított profile store (korábbi munkamenetből) | ✅ | Nyers fájl bájtszintű ellenőrzéssel |
| **Valódi diarizáció** (pyannote/NeMo/diart) ezen a felvételen | ❌ | HF token nélkül (felhasználói döntés) csak `fake` diarizáció fut — ld. "Mit kell hozzá" |
| **Ismert beszélőre optimalizálás / speaker-matching** ezen a felvételen | ❌ | Ahogy a felhasználó is jelezte — enrollment-minta és valódi diarizáció nélkül nem tesztelhető |
| Leiratozási minőség (WER) számszerű mérése | ❌ | Nincs ember által ellenőrzött referencia-átirat ehhez a felvételhez |
| Diarizációs pontosság (DER) számszerű mérése | ❌ | Nincs ground-truth RTTM |
| Teljes 15.2 perces fájl végigfuttatása | ❌ | Csak 60s/20s kivágat lett tesztelve (idő/terhelés-kímélés) |

---

## Talált és javított hibák (élő mód, `SlidingWindowStreamingAdapter`)

A `remote_http` adaptert élő módban tesztelve **két valós hibát** találtam a
meglévő (2. fázisból származó) `SlidingWindowStreamingAdapter`-ben — egyiket
sem lehetett volna szintetikus, szó-szintű fake ASR-rel felfedezni, mert
mindkettő kifejezetten a **szegmens-szintű** (nem szó-szintű) távoli ASR
viselkedésével interakcióban jelentkezett:

1. **Sosem lett `is_final: true`, amíg a stream véget nem ért.** A régi,
   darabszám-alapú ("utolsó negyed a bizonytalan farok") heurisztika 1-2
   tokennél (egy `remote_http` "token" = egy egész mondat) szinte sosem
   hagyott jóvá semmit. **Javítva:** időalapú stabil/bizonytalan
   szétválasztásra váltottam. Regressziós teszt:
   `tests/unit/test_streaming_adapter.py::test_coarse_segment_engine_confirms_before_stream_end`.
2. **Duplikált szöveg a kimeneten** ("Jelenlegi formájában..." kétszer jelent
   meg egy 60 mp-es élő teszt közben). Ok: a puffer flush utáni zsugorítása
   egy FIX overlap-farkot tartott meg, a következő hívás pedig a zsugorodott
   pufferre ÚJRA t=0-tól transzkribált — a globális `emitted_word_count` egy
   MÁS (frissen újraindexelt) szólistába indexelt bele. **Javítva:** a
   pufferből mostantól KIZÁRÓLAG a ténylegesen megerősített hangidő kerül
   eldobásra, globális idő-eltolás követésével. Regressziós teszt:
   `test_confirmed_content_is_never_re_emitted_after_buffer_shrinks`.
3. **Kiegészítő biztonsági korlát:** ha egy wrappelt engine olyan
   kevés/nagy szegmenst ad, hogy IDŐALAPÚ szétválasztással sem stabilizálódna
   semmi, a puffer korlátlanul nőhetne (lassuló újratranszkripció → végül
   kapcsolat-timeout, ld. lent). Bevezettem egy `max_buffer_sec` felső
   korlátot, ami afölött kényszerűen mindent megerősít. Regressziós teszt:
   `test_max_buffer_sec_forces_periodic_confirmation`.

Mindhárom javítás egység-tesztekkel fedett (ld. `tests/unit/test_streaming_adapter.py`),
és a teljes tesztkészlet (67 passed) zöld a javítások után.

---

## Nyitott / tisztázatlan megfigyelés: lassuló élő válaszidő

Egy 60 másodperces élő teszt közben a távoli ASR-hívások válaszideje
fokozatosan nőtt (kezdetben ~0.5 mp/hívás, a teszt végére 13 mp, majd 23 mp),
végül kliens-oldali "keepalive ping timeout" kapcsolat-bontáshoz vezetett. Egy
**friss, 20 másodperces** munkamenetnél is jelentkezett hasonló lassulás
(egyetlen hívás ~20 mp-et vett igénybe).

**Legvalószínűbb magyarázat:** a külső Whisper-large-v3 végpontot ugyanebben
a munkamenetben már **sok** (15+) tényleges transzkripciós hívással
terheltem (baseline-tesztek, batch pipeline-teszt, 3 külön élő teszt) — ez
egy nagy, CPU-igényes modell, és valószínűleg **a végpont saját gépe
telítődött**, nem a mi kódunk hibázott. **NEM zárható ki teljesen** azonban,
hogy a `max_buffer_sec`-fix ellenére is marad egy finomabb, csak hosszabb
munkameneteknél jelentkező forrás-növekedés a mi oldalunkon.

**Javaslat a tisztázáshoz** (ld. "Mit kell hozzá" is): ismételd meg ugyanezt
a tesztet (1) egy kipihent/dedikált végponttal, VAGY (2) egy helyben futó,
könnyű ASR-adapterrel (pl. Vosk — natívan streamel, nem is megy át a
`SlidingWindowStreamingAdapter`-en), hogy elkülönítsük a "külső végpont
terhelt" és a "saját kódunkban van egy finomabb hiba" magyarázatokat.

---

## Mit kell hozzá, hogy a ❌ pontok is tesztelhetők legyenek

| Hiányzó pont | Konkrét igény |
|---|---|
| Valódi diarizáció | `HF_TOKEN` env-változó + a pyannote-modell licencének elfogadása a Hugging Face-en (docs/phase1-terv.md 10. szakasz), VAGY egy sikeresen telepített NeMo MSDD/diart (ld. docs/tradeoffs_and_decisions.md 3.3-3.4 — ezek ebben a környezetben nem lettek élesen validálva) |
| Ismert-beszélő (speaker-matching) teszt | (a) valódi diarizáció (fentebb) **és** (b) beszélőnként egy **30 mp – 2 perces, tiszta, egy-beszélős enrollment-minta** (más felvételből/pillanatból, mint a teszt-audio) |
| WER (leiratozási minőség) | egy **ember által ellenőrzött, pontos referencia-átirat** legalább a teszt-felvétel egy részéhez |
| DER (diarizációs pontosság) | egy **ground-truth RTTM fájl** (ki mikor beszélt) ugyanahhoz a részhez |
| Teljesebb diarizációs teszt | legalább **2-3 perces**, **2+ (ideálisan 3+) egyértelműen elkülönülő beszélőjű** felvétel, néhány **gyors beszélőváltással** (ez teszi próbára igazán a diarizációt — a mostani 60s kivágat inkább egy hosszú monológ+rövid váltás volt) |
| Élő mód hosszú-távú stabilitás | egy dedikált (nem megterhelt) ASR-végpont, VAGY helyi (Vosk/faster-whisper) adapter, hosszabb (5-10 perces) folyamatos élő teszttel |

**Ezt a felkészítést most, a fenti adatok hiányában is elvégeztem:** a
`eval/` könyvtár alatt egy tartós, újrafuttatható kiértékelő eszköz készült
(nem egyszeri szkript) — ld. `eval/README.md`. Amint a fenti teszt-adatok
(felvétel + referencia-átirat + RTTM + enrollment-minták + HF token)
rendelkezésre állnak, a `python -m eval.run_eval --case eval/data/<eset>/manifest.json`
paranccsal azonnal futtatható a teljes összehasonlítás (baseline vs. pipeline,
batch vs. élő, WER + DER), külön kézi szkriptelés nélkül.

---

## Módosított/létrehozott fájlok ebben a munkamenetben

- `src/leiratozo/adapters/asr/remote_http.py` — harmadik ASR-adapter (korábbi
  üzenetben már bevezetve), most kiegészítve egy felülírható
  `_parse_response`-szal, hogy más válaszsémájú végpontokhoz is könnyen
  bővíthető legyen alosztályozással (a felhasználó jelezte, hogy a kódnak
  NEM szabad egyetlen konkrét teszt-végponthoz kötődnie).
- `src/leiratozo/application/streaming_adapter.py` — a 3 fenti hiba
  javítása (időalapú konfirmálás, helyes puffer-zsugorítás, `max_buffer_sec`
  biztonsági korlát).
- `tests/unit/test_streaming_adapter.py` — 3 új regressziós teszt.
- `config/config.remote-whisper.yaml` — kommentek pontosítva (a `base_url`
  csak példa, nem függőség).
- `eval/` — új, tartós kiértékelő keretrendszer (ld. `eval/README.md`).
- `.gitignore` — hangfájl-kiterjesztések (`*.wav` stb.) és `eval/data/*/`
  gitignore-olva (valós felvétel sosem kerül git alá); a korábbi `data/`/`models/`
  szabály root-relatívra (`/data/`, `/models/`) pontosítva, hogy ne nyelje el
  véletlenül az `eval/data/` alatti dokumentációt is.
