# 1. Szekvenciadiagram — batch leiratozási folyamat

UML szekvenciadiagram (Mermaid `sequenceDiagram` — natívan szabványos UML
jelölés: `actor`/`participant` élettartam-sávok, `->>` szinkron hívás, `-->>`
visszatérés, `+`/`-` explicit aktivációs sáv). A `POST /v1/jobs` kérés teljes
lefolyását mutatja a válasz JSON elkészültéig — ld. `docs/phase1-terv.md` 8.
és 12.1. szakasz a kontextusért, `src/leiratozo/application/batch_service.py`
a tényleges implementációért.

```mermaid
sequenceDiagram
    actor Client
    participant API as API réteg (FastAPI)
    participant JobStore
    participant Queue as Redis (arq)
    participant Worker as ArqWorker / BatchTranscriptionService
    participant Decoder as AudioDecoder
    participant VAD as VoiceActivityDetector
    participant ASR as TranscriptionEngine
    participant Diar as DiarizationEngine
    participant Align as Aligner
    participant SpeakerReg as SpeakerRegistrationService
    participant Profiles as ProfileStore

    Client->>+API: POST /v1/jobs (audio file)
    API->>+JobStore: create(job) [status=queued]
    JobStore-->>-API: ok
    API->>+Queue: enqueue_job(run_batch_job, job_id, audio)
    Queue-->>-API: ok
    API-->>-Client: 202 Accepted {job_id}

    Queue->>+Worker: dequeue -> run_batch_job(job_id, audio)
    Worker->>+JobStore: update(status=running)
    JobStore-->>-Worker: ok
    Worker->>+Decoder: decode(raw_bytes)
    Decoder-->>-Worker: AudioBuffer
    Worker->>+VAD: detect_speech(audio)
    VAD-->>-Worker: vad_segments[]
    Worker->>+ASR: transcribe_batch(audio, hints)
    ASR-->>-Worker: word_tokens[]
    Worker->>+Diar: diarize_batch(audio, vad_segments)
    Diar-->>-Worker: diarized_segments[]
    Worker->>+Align: align(word_tokens, diarized_segments)
    Align-->>-Worker: transcript_segments[]
    Worker->>+SpeakerReg: match_segments(audio, diarized_segments)
    SpeakerReg->>+Profiles: list_with_embeddings()
    Profiles-->>-SpeakerReg: [(profile, embedding)]
    SpeakerReg-->>-Worker: {segment_id: SpeakerMatch}
    Worker->>+JobStore: save_result(document) [status=done]
    JobStore-->>-Worker: ok
    deactivate Worker

    Client->>+API: GET /v1/jobs/{id}/result
    API->>+JobStore: get_result(job_id)
    JobStore-->>-API: TranscriptDocument
    API-->>-Client: 200 OK (JSON, schema_version 1.0)
```

**Megjegyzés:** `queue.backend: inline` (dev/teszt) esetén a `Queue`/`Worker`
elkülönítés elmarad — az API-process maga futtatja le szinkron-inline a
`run_batch_job`-nak megfelelő logikát (ld. `ServiceContainer.submit_batch_job`,
`docs/tradeoffs_and_decisions.md` 3.8. szakasz).
