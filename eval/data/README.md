# eval/data/

Ez a könyvtár **gitignore-olva van** (ld. gyökér `.gitignore`: `eval/data/`)
— valós hangfelvételek és ground-truth annotációk kerülnek majd ide, amik
sosem mennek git alá (PII/biometrikus adat, ld. docs/phase1-terv.md 6.
szakasz).

Minden teszt-esethez hozz létre egy alkönyvtárat egy `manifest.json`-nal —
a pontos séma és a minimumkövetelmények (hossz, beszélőszám stb.) a
[`../README.md`](../README.md)-ben vannak dokumentálva.

Ez a `README.md` fájl maga NEM gitignore-olt (csak a könyvtár TARTALMA
azt), hogy a könyvtár struktúrája és a dokumentáció git alatt maradjon,
miközben a valós adatok kimaradnak.
