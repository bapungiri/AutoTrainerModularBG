#!/usr/bin/env python3
"""Convert AutoTrainer .dat session logs into CSV files.

Usage examples:
    python3 dat_to_csv.py /path/to/session.dat
    python3 dat_to_csv.py /home/pi/ExpData/ --recursive --force

The converter understands the standard eight-field .dat format produced by
MainCode.py and writes a CSV with the same base name ("*.csv").  Rotation
markers ("ROTATE,epoch,dataCount,trialCount") are preserved with empty
columns in the remaining fields so the output stays rectangular.
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path
from typing import Dict, Iterable, List

# Column names mirror the payload pushed via ReportData in GeneralFunctions.h
CSV_HEADER = [
    "eventType",
    "value",
    "currentStateMachine",
    "currentTrainingProtocol",
    "stateMachineElapsedMs",
    "unixEpochSec",
    "dailyIntake",
    "weeklyIntake",
]


TRIAL_HEADER = [
    "eventCode",
    "port1Prob",
    "port2Prob",
    "chosenPort",
    "rewarded",
    "trialId",
    "blockId",
    "unstructuredProb",
    "sessionStartEpochMs",
    "blockStartRelMs",
    "trialStartRelMs",
    "trialEndRelMs",
]


def iter_dat_lines(path: Path) -> Iterable[List[str]]:
    """Yield tokenized lines from a .dat file, skipping blanks."""

    with path.open("r", encoding="utf-8", errors="ignore") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if not line:
                continue
            fields = [part.strip() for part in line.split(",")]
            if not fields:
                continue
            yield fields


def convert_dat_file(
    path: Path,
    output_dir: Path | None,
    force: bool,
    trial: bool,
) -> List[Path]:
    """Convert a single .dat file to CSV (and optional trial CSV)."""

    if not path.is_file():
        raise FileNotFoundError(f"{path} is not a file")

    target_dir = output_dir if output_dir is not None else path.parent
    target_dir.mkdir(parents=True, exist_ok=True)
    main_out = target_dir / f"{path.stem}.csv"
    trial_out = target_dir / f"{path.stem}.trial.csv"

    if main_out.exists() and not force:
        raise FileExistsError(
            f"Refusing to overwrite existing file {main_out}. Use --force to replace it."
        )
    if trial and trial_out.exists() and not force:
        raise FileExistsError(
            f"Refusing to overwrite existing file {trial_out}. Use --force to replace it."
        )

    if trial:
        with main_out.open(
            "w", newline="", encoding="utf-8"
        ) as csv_file, trial_out.open("w", newline="", encoding="utf-8") as trial_file:
            writer = csv.writer(csv_file)
            writer.writerow(CSV_HEADER)
            trial_writer = csv.writer(trial_file)
            trial_writer.writerow(TRIAL_HEADER)
            parse_dat_stream(path, writer, trial_writer)
    else:
        with main_out.open("w", newline="", encoding="utf-8") as csv_file:
            writer = csv.writer(csv_file)
            writer.writerow(CSV_HEADER)
            parse_dat_stream(path, writer, None)

    generated = [main_out]
    if trial:
        generated.append(trial_out)
    return generated


def convert_dat_directory(
    directory: Path,
    output_dir: Path | None,
    force: bool,
    trial: bool,
    recursive: bool = False,
) -> List[Path]:
    """Collect .dat files in a directory and emit combined CSV outputs."""

    dat_files = list(find_dat_files(directory, recursive))
    if not dat_files:
        return []

    target_dir = output_dir if output_dir is not None else directory
    target_dir.mkdir(parents=True, exist_ok=True)

    base_name = directory.name or "session"
    main_out = target_dir / f"{base_name}.csv"
    trial_out = target_dir / f"{base_name}.trial.csv"

    if main_out.exists() and not force:
        raise FileExistsError(
            f"Refusing to overwrite existing file {main_out}. Use --force to replace it."
        )
    if trial and trial_out.exists() and not force:
        raise FileExistsError(
            f"Refusing to overwrite existing file {trial_out}. Use --force to replace it."
        )

    sorted_files = sorted(dat_files)

    if trial:
        with main_out.open(
            "w", newline="", encoding="utf-8"
        ) as csv_file, trial_out.open("w", newline="", encoding="utf-8") as trial_file:
            writer = csv.writer(csv_file)
            writer.writerow(CSV_HEADER)
            trial_writer = csv.writer(trial_file)
            trial_writer.writerow(TRIAL_HEADER)
            for dat_path in sorted_files:
                parse_dat_stream(dat_path, writer, trial_writer)
    else:
        with main_out.open("w", newline="", encoding="utf-8") as csv_file:
            writer = csv.writer(csv_file)
            writer.writerow(CSV_HEADER)
            for dat_path in sorted_files:
                parse_dat_stream(dat_path, writer, None)

    generated = [main_out]
    if trial:
        generated.append(trial_out)
    return generated


def parse_dat_stream(
    path: Path, writer: csv.writer | None, trial_writer: csv.writer | None
) -> None:
    """Process the .dat lines, writing main rows and optionally trial rows."""

    block_probs: Dict[int, int | None] = {1: None, 2: None}
    session_start: int | None = None
    block_start_rel: int | None = None
    current_block = 0

    last_port: int | None = None
    pending_trial = False
    last_reward: int | None = None
    trial_start_rel: int | None = None
    trial_end_rel: int | None = None
    lick_trial_id = 0

    def finalize_trial(event_time: int | None = None) -> None:
        nonlocal pending_trial, last_port, last_reward, trial_start_rel, trial_end_rel, lick_trial_id

        if not pending_trial or last_port is None or trial_start_rel is None:
            return

        if event_time is not None:
            end_time = event_time
        elif trial_end_rel is not None:
            end_time = trial_end_rel
        else:
            end_time = trial_start_rel

        reward_value = last_reward if last_reward is not None else 0
        event_code = 201 if reward_value == -1 else 200

        if reward_value in (0, 1):
            lick_trial_id += 1
            trial_id_field = lick_trial_id
        else:
            trial_id_field = lick_trial_id

        port1_prob = block_probs.get(1)
        port2_prob = block_probs.get(2)

        row = [
            event_code,
            port1_prob if port1_prob is not None else "",
            port2_prob if port2_prob is not None else "",
            last_port,
            reward_value,
            trial_id_field,
            current_block,
            "",  # unstructuredProb not recoverable from log
            session_start if session_start is not None else "",
            block_start_rel if block_start_rel is not None else "",
            trial_start_rel,
            end_time,
        ]
        if trial_writer:
            trial_writer.writerow(row)

        pending_trial = False
        last_port = None
        last_reward = None
        trial_start_rel = None
        trial_end_rel = None

    for fields in iter_dat_lines(path):
        if writer:
            emit_main_row(fields, writer)

        code = fields[0]

        if code == "ROTATE":
            finalize_trial()
            block_probs = {1: None, 2: None}
            session_start = None
            block_start_rel = None
            current_block = 0
            last_port = None
            last_reward = None
            trial_start_rel = None
            trial_end_rel = None
            pending_trial = False
            lick_trial_id = 0
            continue

        try:
            code_int = int(code)
        except ValueError:
            continue

        value = int(fields[1]) if len(fields) > 1 else None
        session_time = int(fields[4]) if len(fields) > 4 else 0

        if code_int == 61:
            finalize_trial()
            session_start = int(fields[5]) if len(fields) > 5 else session_start
            pending_trial = False
            continue

        if code_int == 83 and value in (1, 2) and len(fields) > 2:
            block_probs[value] = int(fields[2])
            continue

        if code_int == 121:
            finalize_trial()
            current_block = int(fields[1])
            block_start_rel = session_time
            continue

        if code_int == 81:
            finalize_trial()
            last_port = value
            trial_start_rel = session_time
            pending_trial = True
            last_reward = None
            trial_end_rel = None
            continue

        if not pending_trial:
            continue

        if code_int == 51:
            last_reward = 1
            trial_end_rel = session_time
            finalize_trial(session_time)
            continue

        if code_int == -51:
            last_reward = 0
            trial_end_rel = session_time
            finalize_trial(session_time)
            continue

        if code_int == -52:
            last_reward = -1
            trial_end_rel = session_time
            finalize_trial(session_time)
            continue

        if code_int == 86 and last_reward is None:
            last_reward = 0
            trial_end_rel = session_time
            finalize_trial(session_time)
            continue

        # No additional handling for other codes when reconstructing trials

    finalize_trial()


def emit_main_row(fields: List[str], writer: csv.writer) -> None:
    if fields[0] == "ROTATE":
        row = [fields[0]] + fields[1:]
        while len(row) < len(CSV_HEADER):
            row.append("")
        writer.writerow(row)
        return

    if len(fields) != len(CSV_HEADER):
        print(
            f"WARNING: Skipping unexpected line: {fields}",
            file=sys.stderr,
        )
        return

    writer.writerow(fields)


def find_dat_files(root: Path, recursive: bool) -> Iterable[Path]:
    """Yield .dat files under root (optionally recursive)."""

    if root.is_file() and root.suffix.lower() == ".dat":
        yield root
        return

    pattern = "**/*.dat" if recursive else "*.dat"
    for candidate in root.glob(pattern):
        if candidate.is_file():
            yield candidate


def parse_args(argv: Iterable[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "path",
        type=Path,
        help="A .dat file or a directory containing .dat files",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Optional directory for converted CSV files. Defaults to alongside each .dat file.",
    )
    parser.add_argument(
        "--recursive",
        action="store_true",
        help="When 'path' is a directory, search recursively for .dat files.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing CSV files if they already exist.",
    )
    parser.add_argument(
        "--reconstruct-trials",
        action="store_true",
        help=(
            "Also build <file>.trial.csv by reconstructing trial summaries from the "
            "raw ReportData stream (best-effort). Missing fields such as "
            "unstructuredProb are left blank."
        ),
    )
    return parser.parse_args(list(argv))


def main(argv: Iterable[str] | None = None) -> int:
    ns = parse_args(argv if argv is not None else sys.argv[1:])

    if ns.path.is_dir():
        try:
            generated = convert_dat_directory(
                ns.path,
                ns.output,
                ns.force,
                ns.reconstruct_trials,
                ns.recursive,
            )
            for out_path in generated:
                print(f"Converted {ns.path} -> {out_path}")
        except Exception as exc:  # pylint: disable=broad-except
            print(f"ERROR converting {ns.path}: {exc}", file=sys.stderr)
            return 1

        return 0

    try:
        generated = convert_dat_file(
            ns.path,
            ns.output,
            ns.force,
            ns.reconstruct_trials,
        )
        for out_path in generated:
            print(f"Converted {ns.path} -> {out_path}")
    except Exception as exc:  # pylint: disable=broad-except
        print(f"ERROR converting {ns.path}: {exc}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
