# 2. Komponensdiagram — rendszerkontextus / végpont-térkép

UML komponensdiagram (Mermaid `classDiagram`, `<<component>>`/`<<actor>>`
sztereotípiákkal és `..>` függőségi nyilakkal — ld. `docs/architecture/README.md`
a jelölési döntés indoklásáért). Azt mutatja, milyen külső szereplők
kapcsolódnak a worker mely végpontjaihoz, és a worker belül milyen
infrastruktúra-komponensekre támaszkodik. Ld. `docs/phase1-terv.md` 9. és
12.2. szakasz a kontextusért.

```mermaid
classDiagram
    class FileUploadClient {
        <<actor>>
    }
    class LiveAudioSource {
        <<actor>>
    }
    class MeetingConsumerService {
        <<actor>>
    }
    class AdminOrMonitoring {
        <<actor>>
    }

    class LeiratozoWorker {
        <<component>>
        +POST /v1/jobs
        +GET /v1/jobs/{id}
        +GET /v1/jobs/{id}/result
        +WS /v1/live/{session_id}
        +POST /v1/speakers
        +GET /v1/speakers
        +DELETE /v1/speakers/{id}
        +GET /healthz
        +GET /readyz
        +GET /v1/config
    }

    class RedisQueue {
        <<component>>
    }
    class ArqWorkerProcess {
        <<component>>
    }
    class SqliteJobSessionStore {
        <<component>>
    }
    class EncryptedProfileStore {
        <<component>>
    }
    class ExternalAsrEndpoint {
        <<component>>
        HF/Whisper/egyéb — configból cserélhető
    }

    FileUploadClient ..> LeiratozoWorker : REST\n(multipart audio upload)
    LiveAudioSource ..> LeiratozoWorker : WebSocket\n(audio chunk-ok)
    LeiratozoWorker ..> MeetingConsumerService : JSON eredmény /\nWS partial-final esemény
    AdminOrMonitoring ..> LeiratozoWorker : GET /healthz, /readyz, /v1/config

    LeiratozoWorker --> RedisQueue : batch job enqueue
    RedisQueue --> ArqWorkerProcess : job dequeue + feldolgozás
    ArqWorkerProcess --> SqliteJobSessionStore : eredmény mentése
    LeiratozoWorker --> SqliteJobSessionStore : job/session állapot
    LeiratozoWorker --> EncryptedProfileStore : speaker-profil CRUD (GDPR)
    LeiratozoWorker ..> ExternalAsrEndpoint : opcionális — ha az ASR-port\n`remote_http` adapterre van állítva
```

**Olvasási megjegyzés:** a `LeiratozoWorker` komponens itt a teljes FastAPI
alkalmazást reprezentálja (API réteg + alkalmazásréteg + portok/adapterek
összevonva) — a belső port/adapter felépítést a 3. ábra
(`03-port-adapter-components.md`) bontja ki. Az `ExternalAsrEndpoint` szaggatott
függőségi nyila jelzi, hogy ez NEM mindig aktív rész — csak akkor, ha az ASR
port `remote_http` adapterre van állítva (ld. `config/config.remote-whisper.yaml`);
alapértelmezetten in-process modell (faster-whisper/Vosk) fut.
