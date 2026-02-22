from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd


@dataclass
class Bandit2Arm:
    probs: np.ndarray
    choices: np.ndarray
    rewards: np.ndarray
    session_ids: np.ndarray
    datetime: np.ndarray


def _load_dat_frames(folder: Path) -> pd.DataFrame:
    """Load and concatenate every .dat file within *folder*.

    Returns a single dataframe with rows ordered by filename and original file
    order. Raises FileNotFoundError when no .dat files are present."""

    files = sorted(folder.glob("*.dat"))
    if not files:
        raise FileNotFoundError(f"No .dat files found in {folder}")

    frames: list[pd.DataFrame] = []
    for path in files:
        frame = pd.read_csv(path, header=None, dtype=str, keep_default_na=False)
        frame["__source"] = path.name
        frames.append(frame)

    data = pd.concat(frames, ignore_index=True)
    return data


def _coerce_numeric(series: pd.Series) -> pd.Series:
    """Return a numeric version of *series* with invalid points as NaN."""

    coerced = pd.to_numeric(series, errors="coerce")
    return coerced


def dat2ArmIO(folder: Path) -> Bandit2Arm:
    """Convert AutoTrainer ``.dat`` logs into a Bandit2Arm structure.

    The function expects the folder to already contain one or more ``.dat``
    files written by the AutoTrainer Teensy code. All files are merged in
    filename order before extracting behaviour arrays.

    Raises
    ------
    FileNotFoundError
        When the folder does not include any ``.dat`` file.
    ValueError
        When no valid outcome rows (reward deliveries or misses) can be
        recovered after parsing the logs.
    """

    folder = Path(folder)
    data = _load_dat_frames(folder)

    # Drop rotation markers; they do not conform to the eight column schema.
    data = data[data[0] != "ROTATE"].reset_index(drop=True)

    if data.empty:
        raise ValueError(f"No ReportData rows found in {folder}")

    code = data[0].astype(str)
    arg = _coerce_numeric(data[1])
    prob = _coerce_numeric(data[2])
    datetime_col = _coerce_numeric(data[5])

    data["arg"] = arg
    data["prob"] = prob
    data["datetime"] = datetime_col

    # Probability updates: ReportData(83, port, probability)
    mask_prob = code == "83"
    data["p1_update"] = np.where(mask_prob & (arg == 1), prob, np.nan)
    data["p2_update"] = np.where(mask_prob & (arg == 2), prob, np.nan)
    data["p1"] = data["p1_update"].ffill()
    data["p2"] = data["p2_update"].ffill()

    # Session ID increments when a new port-1 probability is reported.
    session_increment = (mask_prob & (arg == 1)).astype(int)
    data["session_id"] = session_increment.cumsum()

    # Port updates: ReportData(81, port, timestamp)
    mask_port = code == "81"
    data["port_update"] = np.where(mask_port & arg.isin([1, 2]), arg, np.nan)
    data["port"] = data["port_update"].ffill()

    # Reward outcomes: 51=reward, -51=missed reward during lick, -52=no lick
    reward_map = {51: 1, -51: 0, -52: -1}
    code_numeric = _coerce_numeric(code)
    outcome_mask = code_numeric.isin(reward_map.keys())
    outcomes = data.loc[
        outcome_mask, ["port", "p1", "p2", "session_id", "datetime", 0]
    ].copy()

    outcomes = outcomes.dropna(subset=["port", "p1", "p2", "session_id"])

    if outcomes.empty:
        raise ValueError(f"No outcome rows with complete context found in {folder}")

    outcomes["port"] = outcomes["port"].astype(int)
    outcomes["session_id"] = outcomes["session_id"].astype(int)
    outcomes["p1"] = outcomes["p1"].astype(float)
    outcomes["p2"] = outcomes["p2"].astype(float)

    outcomes["reward"] = outcomes[0].astype(int).map(reward_map)

    behav = outcomes.loc[
        :, ["port", "reward", "p1", "p2", "session_id", "datetime"]
    ].reset_index(drop=True)

    # Omit missed trials (-1) unless caller explicitly wants them.
    behav = behav[behav["reward"].isin([0, 1])].reset_index(drop=True)

    if behav.empty:
        raise ValueError(f"No rewarded or attempted trials available in {folder}")

    probs = behav[["p1", "p2"]].to_numpy(dtype=float, copy=True)
    choices = behav["port"].to_numpy(dtype=int, copy=True)
    rewards = behav["reward"].to_numpy(dtype=int, copy=True)
    session_ids = behav["session_id"].to_numpy(dtype=int, copy=True)
    datetimes = behav["datetime"].to_numpy(copy=True)

    return Bandit2Arm(
        probs=probs,
        choices=choices,
        rewards=rewards,
        session_ids=session_ids,
        datetime=datetimes,
    )
