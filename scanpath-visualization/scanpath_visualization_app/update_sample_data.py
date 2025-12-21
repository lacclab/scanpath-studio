"""Build trimmed sample CSV tables from the OneStop exports."""

from pathlib import Path

import pandas as pd


DATA_DIR = Path(__file__).parent
SOURCE_DIR = DATA_DIR / "OneStop"
OUTPUT_DIR = DATA_DIR / "sample_data"

MAX_ROWS = 10_000


def load_head(source_csv: Path) -> pd.DataFrame:
    """Load only the first MAX_ROWS rows with pandas."""
    return pd.read_csv(source_csv, nrows=MAX_ROWS, low_memory=False)


def choose_participants(df: pd.DataFrame, count: int = 2) -> list[str]:
    unique = df["participant_id"].dropna().astype(str).unique().tolist()
    if len(unique) < count:
        raise RuntimeError(f"Found only {len(unique)} participants in head of data: {unique}")
    return unique[:count]


def choose_trials(df: pd.DataFrame, count: int = 2) -> list[str]:
    if "TRIAL_INDEX" not in df.columns:
        raise RuntimeError("Expected TRIAL_INDEX column in data.")
    unique = df["TRIAL_INDEX"].dropna().astype(str).unique().tolist()
    if len(unique) < count:
        raise RuntimeError(f"Found only {len(unique)} trials in head of data: {unique}")
    return unique[:count]


def filter_and_save(
    df: pd.DataFrame, participants: list[str], trials: list[str], output_csv: Path
) -> int:
    if "TRIAL_INDEX" not in df.columns:
        raise RuntimeError("Expected TRIAL_INDEX column in data.")
    if "repeated_reading_trial" not in df.columns:
        raise RuntimeError("Expected repeated_reading_trial column in data.")

    filtered = df[
        df["participant_id"].isin(participants)
        & df["TRIAL_INDEX"].astype(str).isin(trials)
        & (df["repeated_reading_trial"] == False)  # noqa: E712
    ]

    if filtered.empty:
        raise RuntimeError(
            f"No rows matched participants {participants} and paragraphs "
            f"{paragraphs} in provided slice."
        )

    output_csv.parent.mkdir(parents=True, exist_ok=True)
    filtered.to_csv(output_csv, index=False)
    return len(filtered)


def main() -> None:
    ia_df = load_head(SOURCE_DIR / "ia_Paragraph.csv")
    participants = choose_participants(ia_df)
    trials = choose_trials(ia_df)
    ia_rows = filter_and_save(ia_df, participants, trials, OUTPUT_DIR / "ia.csv")
    print(
        f"Wrote {ia_rows} IA rows for participants {participants} and trials {trials} "
        f"to {OUTPUT_DIR / 'ia.csv'}"
    )

    fix_df = load_head(SOURCE_DIR / "fixations_Paragraph.csv")
    fixation_rows = filter_and_save(fix_df, participants, trials, OUTPUT_DIR / "fixations.csv")
    print(
        f"Wrote {fixation_rows} fixation rows for participants {participants} and trials {trials} "
        f"to {OUTPUT_DIR / 'fixations.csv'}"
    )


if __name__ == "__main__":
    main()
