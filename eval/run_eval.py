"""CLI: egy eval-case lefuttatása és kiértékelése.

Használat:
    python -m eval.run_eval --case eval/data/<eset>/manifest.json \\
        --remote-asr-url http://192.168.100.7:8001 \\
        --api-url http://127.0.0.1:8080 \\
        --mode both

Ld. eval/README.md a manifest-sémáért és a szükséges ground-truth
adatokért. Minden összehasonlítás, amihez hiányzik a bemenet (pl. nincs
reference_transcript_path -> nincs WER a referenciához, csak baseline-vs-
pipeline diff), egyszerűen kimarad a jelentésből — a szkript sosem bukik el
emiatt, csak kevesebbet tud mondani.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from eval.clients import run_baseline_batch, run_pipeline_batch, run_pipeline_live
from eval.dataset import load_case
from eval.metrics import diarization_error_rate, word_error_rate


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--case", required=True, help="Eval-case manifest.json útvonala")
    parser.add_argument("--remote-asr-url", default=None, help="A nyers ASR-végpont base_url-je (baseline-hoz)")
    parser.add_argument("--api-url", default="http://127.0.0.1:8080", help="A saját worker HTTP base_url-je")
    parser.add_argument("--ws-url", default="ws://127.0.0.1:8080", help="A saját worker WS base_url-je")
    parser.add_argument("--mode", choices=["batch", "live", "both"], default="batch")
    parser.add_argument("--report-out", default=None, help="Ha megadod, ide ment egy JSON jelentést is")
    args = parser.parse_args()

    case = load_case(args.case)
    report: dict = {
        "case_id": case.case_id,
        "description": case.description,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "mode": args.mode,
    }

    print(f"=== eval-case: {case.case_id} ===")
    print(case.description)
    print()

    baseline_text = None
    if args.remote_asr_url:
        print("--- baseline (nyers ASR-végpont) ---")
        baseline = await run_baseline_batch(case.audio_path, base_url=args.remote_asr_url)
        baseline_text = baseline.text
        report["baseline_text"] = baseline_text
        print(baseline_text)
        print()
    else:
        print("(--remote-asr-url nincs megadva -> baseline kihagyva)")

    pipeline_batch_text = None
    pipeline_document = None
    if args.mode in ("batch", "both"):
        print("--- pipeline (batch, /v1/jobs) ---")
        pipeline_result = await run_pipeline_batch(case.audio_path, api_base_url=args.api_url)
        pipeline_document = pipeline_result.document
        pipeline_batch_text = pipeline_result.text
        report["pipeline_batch_text"] = pipeline_batch_text
        report["pipeline_batch_models"] = pipeline_document.get("models")
        print(pipeline_batch_text)
        print()

    pipeline_live_text = None
    if args.mode in ("live", "both"):
        print("--- pipeline (élő, WebSocket) ---")
        live_result = await run_pipeline_live(
            case.audio_path, ws_base_url=args.ws_url, session_id=f"eval-{case.case_id}"
        )
        pipeline_live_text = live_result.final_text
        report["pipeline_live_events"] = live_result.events
        report["pipeline_live_final_text"] = pipeline_live_text
        print(pipeline_live_text)
        print(f"({len(live_result.events)} esemény, ebből {sum(1 for e in live_result.events if e['is_final'])} final)")
        print()

    print("--- kiértékelés ---")
    if case.has_transcript_ground_truth():
        reference = case.reference_transcript
        if baseline_text is not None:
            wer = word_error_rate(reference, baseline_text)
            report["wer_baseline_vs_reference"] = asdict(wer)
            print(f"WER (baseline vs. referencia):        {wer.wer:.3f}")
        if pipeline_batch_text is not None:
            wer = word_error_rate(reference, pipeline_batch_text)
            report["wer_pipeline_batch_vs_reference"] = asdict(wer)
            print(f"WER (pipeline/batch vs. referencia):  {wer.wer:.3f}")
        if pipeline_live_text is not None:
            wer = word_error_rate(reference, pipeline_live_text)
            report["wer_pipeline_live_vs_reference"] = asdict(wer)
            print(f"WER (pipeline/élő vs. referencia):    {wer.wer:.3f}")
    else:
        print("(nincs reference_transcript_path a manifestben -> nincs abszolút WER)")
        if baseline_text is not None and pipeline_batch_text is not None:
            relative = word_error_rate(baseline_text, pipeline_batch_text)
            report["relative_diff_baseline_vs_pipeline_batch"] = asdict(relative)
            print(f"Relatív eltérés (baseline vs. pipeline/batch, NEM abszolút hibaarány): {relative.wer:.3f}")

    if case.has_diarization_ground_truth() and pipeline_document is not None:
        try:
            der = diarization_error_rate(str(case.reference_rttm_path), pipeline_document.get("segments", []))
            report["der_pipeline_batch"] = asdict(der)
            print(f"DER (pipeline/batch vs. referencia-RTTM): {der.der:.3f}")
        except RuntimeError as exc:
            print(f"DER kihagyva: {exc}")
    else:
        print("(nincs reference_rttm_path, vagy nem futott batch pipeline -> nincs DER)")

    if case.has_known_speakers():
        print(
            f"({len(case.known_speakers)} ismert beszélő enrollment-mintája megadva a manifestben — "
            "a known_speaker_id egyezés kiértékelése MÉG NINCS automatizálva ebben a szkriptben, "
            "ld. eval/README.md 'Ismert-beszélő egyezés kiértékelése' szakasz)"
        )
    else:
        print("(nincs known_speakers a manifestben -> ismert-beszélő matching kiértékelés kihagyva)")

    if args.report_out:
        Path(args.report_out).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\nRészletes jelentés elmentve: {args.report_out}")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        sys.exit(1)
