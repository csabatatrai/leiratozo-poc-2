# Architektúra-diagramok (UML, Mermaid)

A három diagram, ami a `docs/phase1-terv.md` 12. szakaszában eldöntött és
jóváhagyott ábrákat **szabványos UML jelöléssel** (nem generikus flowchart-tal)
adja vissza. A tartalom megegyezik a phase1-terv.md-ben leírtakkal — itt a
**jelölésrendszer** lett UML-konformra cserélve, és a kódbázis 3. fázisos
állapotához igazítva (pl. tényleges `arq`/Redis queue, `SpeakerRegistrationService`
néven).

| Fájl | UML diagramtípus | Mit mutat |
|---|---|---|
| [`01-sequence-batch-flow.md`](01-sequence-batch-flow.md) | **Szekvenciadiagram** | A batch leiratozási kérés időrendi lefolyása, aktivációs sávokkal |
| [`02-component-context.md`](02-component-context.md) | **Komponensdiagram** (kontextus-nézet) | A worker külső kapcsolódási pontjai: kliensek, fogyasztók, belső infrastruktúra-komponensek |
| [`03-port-adapter-components.md`](03-port-adapter-components.md) | **Komponens-/interfész-diagram** | A 3 fő port mint UML-interfész, és a mögöttük megvalósító (realizáló) konkrét adapterek |

## Miért ezt a 3 diagramot, és milyen jelölést használnak

- **Szekvenciadiagram** (`sequenceDiagram`): ez natívan, teljesen szabványos
  UML jelölés Mermaid-ben — `actor`/`participant` sávok, szinkron hívás
  (`->>`), visszatérés (`-->>`), explicit aktivációs sávok (`+`/`-`).
- **Komponensdiagram**: a szabványos UML komponensdiagram jelöléseket
  (`<<component>>` sztereotípia, port-lollipopok) Mermaid nem rendereli
  natívan külön diagramtípusként — ezért `classDiagram`-ot használunk
  `<<component>>`/`<<actor>>` sztereotípiákkal és függőségi nyilakkal
  (`..>`), ami a legközelebbi, valóban UML-konform reprezentáció, amit a
  Mermaid motor ki tud rajzolni. Ez tudatos, dokumentált kompromisszum, nem
  rejtett pontatlanság.
- **Port-adapter diagram**: ez lényegében egy UML **interfész-realizáció**
  ábra — a 3 fő port `<<interface>>`-ként, a konkrét adapterek pedig
  `..|>` (realizálja/implementálja) nyilakkal kapcsolódnak hozzájuk. Ez a
  `classDiagram` natívan, pontosan szabványos UML jelöléssel támogatja
  (szaggatott vonal + üres háromszög nyílhegy — ez a realizáció klasszikus
  UML jele).

Miért NEM osztálydiagram vagy állapotgép a 3 közé: egy klasszikus UML
osztálydiagram (mezők, láthatóság, öröklés) túl sok implementációs
részletet mutatna, kevesebb architekturális belátást adna; egy
állapotgép-diagram (pl. élő session `queued→running→degraded` állapotai)
hasznos kiegészítés lenne, de inkább egy komponens belső viselkedésének
részlete, mint a teljes rendszer architektúrájának áttekintése — ha lenne
negyedik ábra, ez lenne a jelölt.
