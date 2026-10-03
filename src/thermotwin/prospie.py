"""Loader for the PROSPIE heat-trial dataset (Loughborough University, CC BY-NC 4.0).

Source: figshare article 26076577, "Dataset for 'Prediction of Core Body Temperature
from Multiple Variables'". Download with `uv run python -m thermotwin.prospie --download`.
Raw data is not committed to this repository.
"""

import argparse
import urllib.request
from pathlib import Path

import numpy as np
import pandas as pd

from thermotwin import paths

DOWNLOAD_URL = "https://ndownloader.figshare.com/files/47227096"
RAW_PATH = paths.DATA_DIR / "raw" / "prospie.xlsx"
MISSING = 9999
HEADER_ROWS = 2
MIN_TRIAL_MINUTES = 30

COLUMNS = {
    0: "condition",
    1: "time",
    3: "participant",
    5: "age",
    6: "mass_kg",
    7: "height_cm",
    13: "ambient_rh",
    14: "ambient_temp_c",
    20: "work_rest",
    29: "core_temp_c",
    45: "heart_rate",
}
SKIN_SITE_COLUMNS = range(31, 42)


def download(path: Path = RAW_PATH) -> Path:
    """Download the dataset file if it is not already present."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        urllib.request.urlretrieve(DOWNLOAD_URL, path)
    return path


def load_trials(path: Path = RAW_PATH) -> pd.DataFrame:
    """Load minute-level trials with core, mean skin temperature and heart rate.

    Returns:
        DataFrame with one row per minute and a `trial_id` per participant x condition,
        keeping only minutes where core, skin and heart rate are all present.

    Raises:
        FileNotFoundError: If the raw file has not been downloaded.
    """
    if not path.exists():
        raise FileNotFoundError(f"{path} missing; run `python -m thermotwin.prospie --download`")
    raw = pd.read_excel(path, sheet_name="Data", header=None, skiprows=HEADER_ROWS)
    raw = raw.replace(MISSING, np.nan)

    df = raw[list(COLUMNS)].rename(columns=COLUMNS)
    df["skin_temp_c"] = (
        raw[list(SKIN_SITE_COLUMNS)].apply(pd.to_numeric, errors="coerce").mean(axis=1)
    )
    numeric = [c for c in df.columns if c != "time"]
    df[numeric] = df[numeric].apply(pd.to_numeric, errors="coerce")
    df = df.dropna(subset=["participant", "condition", "core_temp_c", "skin_temp_c", "heart_rate"])

    df["trial_id"] = (
        df["participant"].astype(int).astype(str) + "_c" + df["condition"].astype(int).astype(str)
    )
    df["minute"] = df.groupby("trial_id").cumcount()
    sizes = df.groupby("trial_id")["minute"].transform("size")
    return df[sizes >= MIN_TRIAL_MINUTES].reset_index(drop=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="PROSPIE dataset utilities")
    parser.add_argument("--download", action="store_true")
    args = parser.parse_args()
    if args.download:
        print(f"saved to {download()}")
    trials = load_trials()
    print(f"{trials['trial_id'].nunique()} trials, {len(trials)} minutes")
    print(trials[["core_temp_c", "skin_temp_c", "heart_rate"]].describe().round(2))


if __name__ == "__main__":
    main()
