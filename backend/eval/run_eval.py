"""Compare providers on a labelled set of car photos.

Usage (from the backend/ folder, with .env configured):
    python -m eval.run_eval
    python -m eval.run_eval --providers groq --limit 5

Reads eval/labels.csv (columns: filename, make, model) and the images in
eval/images/. Every image goes through every configured provider, *without*
fallback, so each provider is measured on its own. Prints top-1 and top-3
accuracy plus average latency per provider, and writes one row per
(image, provider) to eval/results/results_<timestamp>.csv.
"""

import argparse
import asyncio
import csv
import re
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path

# Make `import app...` work when this file is run directly (python eval/run_eval.py).
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import get_settings  # noqa: E402
from app.identify import InvalidModelOutputError, identify_with_provider  # noqa: E402
from app.image_prep import InvalidImageError, prepare_image  # noqa: E402
from app.providers import ProviderError, VisionProvider, build_providers  # noqa: E402
from app.schemas import CarCandidate  # noqa: E402

EVAL_DIR = Path(__file__).resolve().parent

# Spellings that should count as the same manufacturer. Extend as you find more.
MAKE_ALIASES = {
    "vw": "volkswagen",
    "mercedes": "mercedesbenz",
    "merc": "mercedesbenz",
    "chevy": "chevrolet",
    "landrover": "landrover",
    "alfa": "alfaromeo",
}


def _norm(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", text.lower())


def make_matches(expected: str, predicted: str) -> bool:
    e, p = _norm(expected), _norm(predicted)
    return MAKE_ALIASES.get(e, e) == MAKE_ALIASES.get(p, p)


def model_matches(expected: str, predicted: str) -> bool:
    """Lenient match: "Golf" matches "Golf GTI", "MX-5" matches "MX5 Miata"."""
    e, p = _norm(expected), _norm(predicted)
    return bool(e) and bool(p) and (e in p or p in e)


def candidate_matches(c: CarCandidate, make: str, model: str) -> bool:
    return make_matches(make, c.make) and model_matches(model, c.model)


@dataclass
class Row:
    filename: str
    provider: str
    expected_make: str
    expected_model: str
    is_car: bool | None = None
    top1: str = ""
    top1_confidence: float | None = None
    all_candidates: str = ""
    top1_correct: bool = False
    top3_correct: bool = False
    latency_ms: int | None = None
    error: str = ""


@dataclass
class Summary:
    total: int = 0
    top1: int = 0
    top3: int = 0
    errors: int = 0
    latencies: list[int] = field(default_factory=list)


def load_labels(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as f:
        rows = [
            {k.strip(): (v or "").strip() for k, v in row.items() if k}
            for row in csv.DictReader(f)
        ]
    # Skip blank lines and commented-out example rows.
    return [r for r in rows if r.get("filename") and not r["filename"].startswith("#")]


async def evaluate_one(provider: VisionProvider, image_path: Path, label: dict[str, str]) -> Row:
    row = Row(
        filename=label["filename"],
        provider=provider.name,
        expected_make=label["make"],
        expected_model=label["model"],
    )
    try:
        prepared = prepare_image(image_path.read_bytes())
        answer = await identify_with_provider(provider, prepared.data_url)
    except (OSError, InvalidImageError, ProviderError, InvalidModelOutputError) as exc:
        row.error = f"{type(exc).__name__}: {exc}"
        return row

    out = answer.output
    row.is_car = out.is_car
    row.latency_ms = answer.latency_ms
    row.all_candidates = " | ".join(
        f"{c.make} {c.model} ({c.confidence:.2f})" for c in out.candidates
    )
    if out.candidates:
        first = out.candidates[0]
        row.top1 = f"{first.make} {first.model}"
        row.top1_confidence = first.confidence
        row.top1_correct = candidate_matches(first, label["make"], label["model"])
        row.top3_correct = any(
            candidate_matches(c, label["make"], label["model"]) for c in out.candidates
        )
    return row


async def run(args: argparse.Namespace) -> int:
    labels = load_labels(args.labels)
    if args.limit:
        labels = labels[: args.limit]
    if not labels:
        print(f"No labelled images found in {args.labels}. Add rows like: my_car.jpg,Toyota,Corolla")
        return 1

    providers = build_providers(get_settings())
    if args.providers:
        providers = [p for p in providers if p.name in args.providers]
    if not providers:
        print("No providers configured. Set GROQ_API_KEY and/or NVIDIA_API_KEY in backend/.env.")
        return 1

    rows: list[Row] = []
    summaries = {p.name: Summary() for p in providers}
    for i, label in enumerate(labels, 1):
        image_path = args.images / label["filename"]
        for provider in providers:
            # Sequential on purpose: gentler on free-tier rate limits, and latency
            # numbers aren't skewed by requests running in parallel.
            row = await evaluate_one(provider, image_path, label)
            rows.append(row)
            s = summaries[provider.name]
            s.total += 1
            s.top1 += row.top1_correct
            s.top3 += row.top3_correct
            if row.error:
                s.errors += 1
            elif row.latency_ms is not None:
                s.latencies.append(row.latency_ms)
            mark = "ERR" if row.error else ("OK " if row.top1_correct else ("~3 " if row.top3_correct else "X  "))
            print(f"[{i}/{len(labels)}] {provider.name:<7} {mark} {label['filename']}: "
                  f"{row.top1 or row.error or 'no candidates'}")

    print("\nprovider  images  top-1    top-3    errors  avg latency")
    for name, s in summaries.items():
        avg = f"{sum(s.latencies) / len(s.latencies):.0f} ms" if s.latencies else "n/a"
        print(f"{name:<9} {s.total:<7} {s.top1 / s.total:>6.1%}   {s.top3 / s.total:>6.1%}   "
              f"{s.errors:<7} {avg}")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(asdict(rows[0]).keys()))
        writer.writeheader()
        writer.writerows(asdict(r) for r in rows)
    print(f"\nPer-image results saved to {args.out}")
    return 0


def main() -> None:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--labels", type=Path, default=EVAL_DIR / "labels.csv")
    parser.add_argument("--images", type=Path, default=EVAL_DIR / "images")
    parser.add_argument("--out", type=Path, default=EVAL_DIR / "results" / f"results_{stamp}.csv")
    parser.add_argument("--providers", nargs="+", choices=["groq", "nvidia"], help="Only run these.")
    parser.add_argument("--limit", type=int, default=0, help="Only use the first N images.")
    sys.exit(asyncio.run(run(parser.parse_args())))


if __name__ == "__main__":
    main()
