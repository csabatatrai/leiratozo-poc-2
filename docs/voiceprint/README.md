# Hangminta-felvételi útmutató (speaker-regisztráció)

Ez a mappa a `leiratozó` projekt **beszélő-regisztrációjához**
(`POST /v1/speakers`) ajánlott felolvasandó szövegeket és az ehhez
tartozó gyakorlati útmutatót tartalmazza — magyarul és angolul, külön
fájlban:

| Fájl | Nyelv | Tartalom |
|---|---|---|
| [`szoveg-magyar.md`](szoveg-magyar.md) | magyar | "Az északi szél és a Nap" mese + kiegészítő mondatok |
| [`szoveg-angol.md`](szoveg-angol.md) | angol | Rainbow Passage + Harvard Sentences (1. lista) |

Ha a hangminta-felvétel *mögötti* fogalmakat (mi az az embedding, mi az a
cosine similarity stb.) is szeretnéd megérteni, azokat a
[`../terminologia.md`](../terminologia.md) "Speaker embedding" és "Cosine
similarity" szócikkei magyarázzák.

---

## 1. Mit jelent itt a "rátanulás" — és mit nem

Fontos elsőként tisztázni: a beszélő-regisztráció **nem** modell-tanítás
vagy finomhangolás. A `SpeakerEmbeddingEngine` port mögötti adapterek
(`speechbrain_ecapa`, `resemblyzer`) egy **előre betanított, általános**
embedding-modellt futtatnak, ami a beküldött hangmintából egyetlen
lépésben kivon egy fix hosszúságú számvektort (a "hanglenyomatot" /
*voiceprint*-et) — a modell maga nem változik, nem tanul semmit a
felhasználó hangjáról a hagyományos értelemben.

A folyamat pontosan ez (`src/leiratozo/api/routes/speakers.py` →
`SpeakerRegistrationService.register`):

```
felolvasott hangminta (1 db audio fájl)
        │
        ▼
SpeakerEmbeddingEngine.extract_embedding()   # egyetlen embedding-vektor
        │
        ▼
ProfileStore.save(profile_id, encrypt(embedding), encrypt(display_name)?)
```

Később, leiratozáskor a rendszer minden diarizált beszélő-szegmensre is
kivon egy embeddinget, és **koszinusz-hasonlósággal** (`cosine_similarity`,
`application/speaker_registration_service.py`) hasonlítja össze a
regisztrált profilokkal — ha a hasonlóság a `speaker_matching.
similarity_threshold` küszöb felett van, a szegmens az adott ismert
beszélőhöz lesz rendelve.

**Gyakorlati következmény:** mivel nincs "tanulási folyamat", nem a
felolvasott *szöveg tartalma* számít, hanem az, hogy a hangminta minél
jobban, minél sokoldalúbban reprezentálja a személy **hangjának
jellemzőit** (hangszín, hangmagasság-tartomány, artikuláció) — ezért
érdemes fonetikailag változatos, természetes tempójú szöveget felolvasni,
nem pedig egy rövid, ismétlődő mondatot.

## 2. Ajánlott felvételi hossz

| Hossz (tiszta beszéd, csend nélkül) | Minőség |
|---|---|
| < 5 másodperc | technikailag lefut, de nem megbízható |
| ~20–30 másodperc | **gyakorlati minimum** — elfogadható éles használatra |
| **~1–2 perc, változatos szöveg** | **ajánlott** — ezt célozzák az itteni szövegek |
| 3+ perc | alig van érdemi minőségjavulás a plusz idő után |

A "tiszta beszéd" azért fontos megkötés, mert a pipeline elején futó
[VAD](../terminologia.md#vad-voice-activity-detection-hangaktivitás-detektálás)
(hangaktivitás-detektálás) már a csendes/szünetes szakaszokat kiszűri —
tehát ha a felolvasó sokat szünetel, a *nyers* felvétel hossza ennél
hosszabb kell legyen ahhoz, hogy a ténylegesen felhasznált beszédidő elérje
a fenti értékeket.

A mappában lévő szövegek pontosan erre a célra vannak méretezve:
- a magyar szöveg 1. része (mese) önmagában ~45–55 mp, a 2. résszel
  kiegészítve ~1,5–2 perc;
- az angol Rainbow Passage önmagában ~2 perc, a Harvard-mondatok pedig
  egy ~20–30 másodperces gyors alternatívát/kiegészítést adnak.

## 3. Miért van külön magyar és angol szöveg?

Technikailag a `SpeechBrainEcapaEngine`/`ResemblyzerEngine` **nyelvfüggetlen**
(text-independent) embedding-modell — nem a szavakat, hanem a hang
akusztikai jellemzőit méri, ezért elvileg *bármelyik* nyelvű szöveg
használható bármelyik konfigurált ASR-motor mellett (a beszélő-azonosítás
független az ASR nyelvétől).

Két nyelvű szöveget mégis érdemes adni, mert:
- **A felolvasó kényelme/természetessége számít, nem a szöveg nyelve.**
  Egy anyanyelvi (vagy jól beszélt) nyelven felolvasott szöveg természetesebb
  intonációt, ritmust és artikulációt eredményez, mint egy nehezen kiolvasott,
  idegen nyelvű szöveg — ez pedig jobb minőségű, reprezentatívabb
  hangmintát ad.
- **A projekt több ASR-adaptert is támogat**, köztük magyar és angol
  nyelvű beszédfelismerést egyaránt (`config/config.example.yaml` —
  `models.asr.adapter`, `language` mező) — konzisztens, hogy a
  regisztrációs útmutató is mindkét célnyelvi felhasználói kört kiszolgálja.
- **A magyar hangkészlet fonetikailag eltér az angolétól** (pl. az összes
  ékezetes magánhangzó: á, é, í, ó, ö, ő, ú, ü, ű; és a `gy`/`ly`/`ny`/
  `ty`/`sz`/`zs`/`cs`/`dz`/`dzs` hangkapcsolatok) — egy angol szöveg
  felolvasása ezeket a magyar beszélőre jellemző hangokat nem szólaltatná
  meg, ami (bár technikailag nem kötelező) kevésbé reprezentatív mintát
  adhat magyar anyanyelvű felhasználóknál.

## 4. Felvételi minőségi tanácsok

Ezek a tényezők jellemzően **nagyobb hatással** vannak a végeredmény
minőségére, mint önmagában a felvétel hossza:

- **Csendes környezet.** Kerüld a háttérzajt (klíma, forgalom, zene, másik
  beszélő) — a VAD és az embedding-modell is a tiszta beszédjelre van
  optimalizálva, nem a zajszűrésre.
- **Állandó mikrofon-távolság.** Tartsd kb. 15–20 cm-re a mikrofont a
  szájtól, és ne mozogj közben — a hirtelen hangerő-ingadozás torzítja az
  embedding-et.
- **Természetes tempó és hanglejtés.** Ne olvasd túl lassan, tagoltan
  vagy monoton, "robotikusan" — a cél, hogy a minta hasonlítson a személy
  *valódi*, hétköznapi beszédhangjára, amivel majd a rendszert használni
  fogja.
- **Egyenletes hangerő, torzításmentesen.** Ne kiabálj, ne suttogj; kerüld
  a mikrofon-kattogást/klippelést (ha a felvevő szoftver "peak"/túlvezérlés
  jelzést ad, halkabban vagy távolabbról vedd fel).
- **Egyetlen, összefüggő felvétel — ne sok apró darab.** A jelenlegi
  `register()` implementáció **egyetlen** feltöltött hangfájlból von ki
  **egyetlen** embeddinget (nincs beépített több-mintás átlagolás) — tehát
  jobb egy folyamatos, jó minőségű felvétel, mint több különálló, rövid
  klip összefésülése.
- **Egy beszélő, más hang nélkül.** Ne legyen háttérben másik személy
  beszéde, rádió vagy tévé — ez összezavarhatja mind a VAD-ot, mind az
  embedding-extrakciót.
- **Formátum:** bármelyik, az `AudioDecoder` port által támogatott formátum
  jó (wav/mp3/m4a/ogg/flac — ld. [`../terminologia.md`](../terminologia.md)
  "AudioDecoder" szócikke), amit a rendszer 16kHz mono PCM-mé normalizál.
  A forrásfelvétel minél kevésbé legyen erősen tömörítve (pl. ne nagyon
  alacsony bitrátás, telefonos hívás-minőségű mp3) — minél kevesebb a
  kódolási torzítás, annál pontosabb az embedding.

## 5. Beküldés a rendszerbe

```bash
curl -F "file=@hangminta.wav" \
     -F "display_name=Teszt Elek" \
     http://127.0.0.1:8080/v1/speakers
```

A válasz egy `profile_id`-t ad vissza (véletlen UUID — ld.
[`../terminologia.md`](../terminologia.md) "UUID" szócikke) — ezt az
azonosítót fogja a rendszer később a `known_speaker_id` mezőben visszaadni
a leiratban, ha a rendszer az adott beszélőt felismeri.

## 6. Mit *ne* csinálj

- Ne olvass fel túl rövid (néhány másodperces) mintát "gyorsítás" céljából
  — ez alacsonyabb minőségű, kevésbé megbízható embeddinget eredményez.
- Ne válassz erősen monoton, ismétlődő szöveget (pl. ugyanazon szó/mondat
  sokszori ismétlése) — ez nem reprezentálja jól a beszélő hangkészletét.
- Ne rögzíts felvételt erős háttérzenével vagy több beszélővel egyszerre.
- Ne keverd a nyelveket egy felvételen belül (pl. felváltva magyarul és
  angolul olvasva) — ez a fonetikai lefedettség szempontjából nem előnyös,
  és a természetes intonációt is megzavarja; válaszd az egyik nyelvi
  szöveget egészben.

## Források

A `szoveg-magyar.md` és `szoveg-angol.md` fájlokban használt szövegek és a
fenti ajánlások megalapozásához az alábbi forrásokat használtam:

- [The Rainbow Passage — IDEA: International Dialects of English Archive](https://www.dialectsarchive.com/the-rainbow-passage) — a Rainbow Passage (Grant Fairbanks) teljes, közkincs szövege.
- [The Rainbow Passage — voxforge.org](https://www.voxforge.org/home/downloads/speech/english/the-rainbow-passage) — a szöveg beszédtechnológiai (ASR-korpusz) felhasználásának megerősítése.
- [Harvard sentences — Wikipédia](https://en.wikipedia.org/wiki/Harvard_sentences) — a Harvard Sentences (IEEE, 1969) eredete, közkincs státusza, felhasználása ASR-benchmarkoláshoz és enrollmenthez.
- [North Wind and The Sun in 70 Languages — phonetics.expert](https://www.phonetics.expert/north-wind-and-the-sun) és a [magyar oldal](https://www.phonetics.expert/hungarian) — az IPA "Északi szél és a Nap" hagyomány, hivatkozva Szende Tamás (1994) magyar IPA-illusztrációjára (*Illustrations of the IPA: Hungarian*, Journal of the International Phonetic Association, 24/2, 91–94).
- [PHOIBLE — hun_szende1994 forrás](https://phoible.org/sources/hun_szende1994) — Szende (1994) tanulmány azonosítása.
- BME beszédinformációs gyakorlati jegyzet (`smartlab.tmit.bme.hu`) és ELTE Fonetikai Tanszék *Fonetikai olvasókönyv* — a magyar fonetikai kiegyensúlyozottság (minden fonéma/bifón/trifón, ill. minden betű lefedése) elvi megalapozásához, mivel ezekhez nem található nyilvánosan egy konkrét, kész, hosszabb "etalon" magyar hangminta-szöveg — ezért a `szoveg-magyar.md` kiegészítő mondatai ez alapján, saját összeállításban készültek.
