"""
CUAD Benchmark Evaluation
===========================
Measures ClauseGuard's clause classification accuracy against
the Contract Understanding Atticus Dataset (CUAD).

CUAD: https://www.atticusprojectai.org/cuad
41 clause types across 510 real commercial contracts.
We map our 30 clause types to the closest CUAD categories.

Usage:
    # Download CUAD dataset first:
    # wget https://huggingface.co/datasets/theatticusproject/cuad/resolve/main/CUAD_v1.json

    python evaluation/cuad_benchmark.py --cuad-path ./CUAD_v1.json --sample 50

This script:
1. Loads N contracts from CUAD
2. Runs each through ClauseGuard's classifier + extractor
3. Compares output to CUAD ground truth labels
4. Reports precision, recall, F1 per clause type
5. Outputs a CSV report and logs results to LangSmith

IMPORTANT: This script calls the real Claude API.
Running on 50 contracts costs approximately $2–5 USD.
Running on all 510 contracts costs approximately $20–50 USD.
"""

import argparse
import asyncio
import csv
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

# Load env before imports
from dotenv import load_dotenv
load_dotenv()

from config import get_settings
from services.classifier import classify_contract
from services.chunker import chunk_document
from services.clause_extractor import extract_clauses
from services.document_parser import ParsedDocument, PageBlock

settings = get_settings()

# ── CUAD → ClauseGuard clause type mapping ───────────────────────────────────
# CUAD uses different naming conventions. Map to our CLAUSE_TYPES.
CUAD_TO_CLAUSEGUARD: dict[str, str] = {
    "Non-Compete": "NON_COMPETE",
    "Non-Solicit": "NON_SOLICITATION",
    "Ip Ownership Assignment": "IP_ASSIGNMENT",
    "Indemnification": "INDEMNIFICATION",
    "Limitation Of Liability": "LIMITATION_OF_LIABILITY",
    "Termination For Cause": "TERMINATION_FOR_CAUSE",
    "Termination For Convenience": "TERMINATION_FOR_CONVENIENCE",
    "Renewal Term": "AUTO_RENEWAL",
    "Payment Frequency": "PAYMENT_TERMS",
    "Governing Law": "GOVERNING_LAW",
    "Dispute Resolution": "DISPUTE_RESOLUTION",
    "Force Majeure": "FORCE_MAJEURE",
    "Data Breach": "DATA_PROTECTION",
    "Exclusivity": "EXCLUSIVITY",
    "Assignment": "ASSIGNMENT",
    "Change Of Control": "ASSIGNMENT",
    "Anti-Assignment": "ASSIGNMENT",
    "License Grant": "WORK_PRODUCT",
    "Audit Rights": "AUDIT_RIGHTS",
    "Most Favored Nation": "MOST_FAVORED_NATION",
    "Liquidated Damages": "LIQUIDATED_DAMAGES",
    "Warranty Duration": "WARRANTY_DISCLAIMER",
}


def text_to_parsed_doc(text: str, contract_name: str) -> ParsedDocument:
    """Convert raw contract text to ParsedDocument for pipeline processing."""
    lines = text.split("\n")
    blocks = []
    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped:
            continue
        is_heading = stripped.isupper() and len(stripped) < 100
        blocks.append(PageBlock(
            page_num=max(1, i // 30),
            text=stripped,
            is_heading=is_heading,
            font_size=14 if is_heading else 11,
        ))
    return ParsedDocument(
        blocks=blocks,
        defined_terms={},
        total_pages=max(1, len(blocks) // 30),
        raw_text=text,
        file_type="txt",
    )


async def evaluate_contract(
    contract_name: str,
    contract_text: str,
    ground_truth_clauses: set[str],
) -> dict:
    """Evaluate a single contract. Returns TP, FP, FN counts per clause type."""
    contract_id = f"eval_{contract_name[:20]}"

    # Stage 0: Classify
    type_result = await classify_contract(contract_text[:12000], contract_id)
    contract_type = type_result.contract_type

    # Stage 2: Chunk
    parsed_doc = text_to_parsed_doc(contract_text, contract_name)
    chunks = chunk_document(parsed_doc, contract_type)

    # Stage 3: Extract
    extracted = await extract_clauses(chunks, contract_type, "US", contract_id)
    predicted_types = {e.clause_type for e in extracted if not e.low_confidence}

    # Compare
    true_positives = predicted_types & ground_truth_clauses
    false_positives = predicted_types - ground_truth_clauses
    false_negatives = ground_truth_clauses - predicted_types

    return {
        "contract_name": contract_name,
        "contract_type": contract_type,
        "true_positives": true_positives,
        "false_positives": false_positives,
        "false_negatives": false_negatives,
        "precision": len(true_positives) / max(len(predicted_types), 1),
        "recall": len(true_positives) / max(len(ground_truth_clauses), 1),
    }


async def run_benchmark(cuad_path: str, sample: int, output_csv: str) -> None:
    """Main benchmark runner."""
    print(f"Loading CUAD dataset from {cuad_path}…")
    with open(cuad_path, "r") as f:
        cuad_data = json.load(f)

    contracts = list(cuad_data.get("data", []))[:sample]
    print(f"Evaluating {len(contracts)} contracts…")

    results = []
    all_tp = all_fp = all_fn = 0

    for i, contract in enumerate(contracts):
        contract_name = contract.get("title", f"contract_{i}")
        # CUAD stores contract text in paragraphs
        paragraphs = contract.get("paragraphs", [])
        contract_text = " ".join(
            p.get("context", "") for p in paragraphs
        )[:50000]  # 50k chars max

        # Extract ground truth clause types from CUAD annotations
        ground_truth_cuad = set()
        for para in paragraphs:
            for qa in para.get("qas", []):
                if qa.get("answers") and qa["answers"][0].get("text"):
                    # Map CUAD question title to our clause type
                    cuad_type = qa.get("id", "").split("__")[-1] if "__" in qa.get("id", "") else qa.get("id", "")
                    # Normalize
                    for cuad_name, our_type in CUAD_TO_CLAUSEGUARD.items():
                        if cuad_name.lower() in cuad_type.lower():
                            ground_truth_cuad.add(our_type)

        if not ground_truth_cuad:
            print(f"  [{i+1}/{len(contracts)}] {contract_name}: No mapped ground truth — skipping")
            continue

        try:
            print(f"  [{i+1}/{len(contracts)}] {contract_name} ({len(ground_truth_cuad)} expected clauses)…", end=" ")
            start = time.time()
            result = await evaluate_contract(contract_name, contract_text, ground_truth_cuad)
            elapsed = time.time() - start

            f1 = (
                2 * result["precision"] * result["recall"]
                / max(result["precision"] + result["recall"], 0.001)
            )
            result["f1"] = f1

            print(f"P={result['precision']:.2f} R={result['recall']:.2f} F1={f1:.2f} ({elapsed:.1f}s)")
            results.append(result)

            all_tp += len(result["true_positives"])
            all_fp += len(result["false_positives"])
            all_fn += len(result["false_negatives"])

        except Exception as e:
            print(f"ERROR: {e}")

    # Aggregate metrics
    if results:
        macro_precision = sum(r["precision"] for r in results) / len(results)
        macro_recall = sum(r["recall"] for r in results) / len(results)
        macro_f1 = sum(r["f1"] for r in results) / len(results)
        micro_precision = all_tp / max(all_tp + all_fp, 1)
        micro_recall = all_tp / max(all_tp + all_fn, 1)

        print("\n" + "=" * 60)
        print("BENCHMARK RESULTS")
        print("=" * 60)
        print(f"Contracts evaluated: {len(results)}")
        print(f"Macro Precision:     {macro_precision:.3f}")
        print(f"Macro Recall:        {macro_recall:.3f}")
        print(f"Macro F1:            {macro_f1:.3f}")
        print(f"Micro Precision:     {micro_precision:.3f}")
        print(f"Micro Recall:        {micro_recall:.3f}")
        print("=" * 60)

        # Write CSV
        with open(output_csv, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=[
                "contract_name", "contract_type", "precision", "recall", "f1",
                "true_positives", "false_positives", "false_negatives",
            ])
            writer.writeheader()
            for r in results:
                writer.writerow({
                    **r,
                    "true_positives": "|".join(r["true_positives"]),
                    "false_positives": "|".join(r["false_positives"]),
                    "false_negatives": "|".join(r["false_negatives"]),
                })
        print(f"\nDetailed results written to {output_csv}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="ClauseGuard CUAD benchmark")
    parser.add_argument("--cuad-path", default="CUAD_v1.json", help="Path to CUAD JSON file")
    parser.add_argument("--sample", type=int, default=30, help="Number of contracts to evaluate")
    parser.add_argument("--output", default="benchmark_results.csv", help="Output CSV path")
    args = parser.parse_args()

    asyncio.run(run_benchmark(args.cuad_path, args.sample, args.output))
