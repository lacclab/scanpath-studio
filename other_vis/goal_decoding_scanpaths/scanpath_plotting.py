# %%
from multiprocessing import Pool
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from tqdm import tqdm

from goal_decoding_scanpaths.add_saccade_features import add_features

###############################################################################
# 1) Plotting functions
###############################################################################


def plot_scanpaths_1d(df, x_col, duration_col):
    """
    Create a single 1D scanpath plot for a trial:
      - X-axis: word index (or interest area index)
      - Y-axis: cumulative time (sum of durations up to that point)
    """
    df = df.copy()
    df["cumulative_time"] = df[duration_col].cumsum()

    plt.figure(figsize=(2.24, 2.24), dpi=100)
    plt.plot(
        df[x_col],
        df["cumulative_time"],
        marker="o",
        linewidth=1,
        color="black",
        alpha=0.8,
    )
    plt.scatter(
        df[x_col],
        df["cumulative_time"],
        s=df[duration_col] * 0.05,
        color="blue",
        alpha=0.6,
    )
    plt.xlabel("Word Index")
    plt.ylabel("Cumulative Time (ms)")
    plt.title("Scanpath Plot")


def plot_scanpaths_2d(df, x_col, y_col, duration_col, x_limits, y_limits):
    """
    Create a single 2D scanpath plot for a trial:
      - X-axis: CURRENT_FIX_X
      - Y-axis: CURRENT_FIX_Y
    """
    plt.figure(figsize=(2.24, 2.24), dpi=100)
    plt.plot(df[x_col], df[y_col], marker="o", linewidth=1, color="black", alpha=0.8)
    plt.scatter(
        df[x_col], df[y_col], s=df[duration_col] * 0.05, color="blue", alpha=0.6
    )
    plt.xlim(*x_limits)
    plt.ylim(y_limits[1], y_limits[0])  # Invert Y-axis for top-down view
    plt.xlabel("X")
    plt.ylabel("Y")
    plt.title("Scanpath Plot")
    plt.tight_layout()


def plot_scanpaths_2d_single_trial(
    df, x_col, y_col, duration_col, x_limits=None, y_limits=None
):
    """
    Create a 2D scanpath plot for a single trial.

    Parameters:
    - df: DataFrame containing the data.
    - x_col: Column for the X-axis values.
    - y_col: Column for the Y-axis values.
    - duration_col: Column for the point sizes based on duration.
    - x_limits: Tuple specifying (min, max) limits for the X-axis.
    - y_limits: Tuple specifying (min, max) limits for the Y-axis.
    """

    # Apply the categorization
    # df["size_category"] = df[duration_col].apply(categorize_fixation_duration)

    # Assign distinct markers based on the binned category
    markers = {1: "o", 2: "s", 3: "D", 4: "X", 5: "^"}  # Example markers

    # Normalize the sequence order for color mapping
    df["sequence_order"] = np.arange(len(df))
    # Clip durations to the range [80, 500]
    df[duration_col] = df[duration_col].clip(lower=80, upper=500)

    plt.figure(figsize=(8, 6))
    _ = sns.scatterplot(
        x=x_col,
        y=y_col,
        size="CURRENT_FIX_DURATION",
        hue="sequence_order",
        # style="size_category",
        markers=markers,
        data=df,
        alpha=0.9,
        sizes=(80, 650),  # Adjust size range
        palette=sns.color_palette("gray", as_cmap=True),
        legend=False,
    )

    for i in range(len(df) - 1):
        color_map = {
            "<fs>": "#1f77b4",  # Blue
            "<rg>": "#ff7f0e",  # Orange
            "<sk>": "#2ca02c",  # Green
            "<rf>": "#d62728",  # Red
            "<rs>": "#9467bd",  # Purple
            "<oob>": "#8c564b",  # Brown
        }
        plt.arrow(
            df.iloc[i][x_col],
            df.iloc[i][y_col],
            df.iloc[i + 1][x_col] - df.iloc[i][x_col],
            df.iloc[i + 1][y_col] - df.iloc[i][y_col],
            head_width=15,
            head_length=20,
            fc=color_map.get(df.iloc[i]["saccade_type"], "black"),
            ec=color_map.get(df.iloc[i]["saccade_type"], "black"),
            linewidth=1,
            alpha=0.9,
            length_includes_head=True,
        )

    # Set axis limits if provided
    if x_limits:
        plt.xlim(x_limits)
    if y_limits:
        plt.ylim(y_limits)

    # Customize plot
    plt.gca().invert_yaxis()  # Invert Y-axis for top-down view
    plt.xticks([])
    plt.yticks([])
    plt.xlabel("")
    plt.ylabel("")
    # plt.title("Scanpath Plot")
    plt.tight_layout()


###############################################################################
# 2) Function to process a single subject
###############################################################################


def process_subject(args):
    """
    Filters data for one subject, iterates over unique trials, and saves plots.
    """
    participant_id, fixations, x_is_word_index, base_path, x_limits, y_limits, debug = (
        args
    )
    sub = fixations[fixations["participant_id"] == participant_id]

    for i, (unique_paragraph_id, trial_df) in enumerate(
        sub.groupby("unique_paragraph_id")
    ):
        # Generate plot
        if x_is_word_index:
            plot_scanpaths_1d(
                trial_df,
                x_col="CURRENT_FIX_INTEREST_AREA_INDEX",
                duration_col="CURRENT_FIX_DURATION",
            )
        else:
            plot_scanpaths_2d_single_trial(
                trial_df,
                x_col="CURRENT_FIX_X",
                y_col="CURRENT_FIX_Y",
                duration_col="CURRENT_FIX_DURATION",
                x_limits=x_limits,
                y_limits=y_limits,
            )

        preview_condition = trial_df["question_preview"].iloc[0]
        # Save plot
        filename = (
            base_path
            / str(preview_condition)
            / f"{preview_condition}_{participant_id}_{unique_paragraph_id}.png"
        )

        plt.savefig(filename, bbox_inches="tight")
        plt.close()
        if debug:
            print(f"Saved: {filename}")
            if i > 5:
                break


###############################################################################
# 3) Main script
###############################################################################


def main():
    # --------------------
    # Configuration flags
    # --------------------
    x_is_word_index = False
    debug = False
    current_time = pd.Timestamp.now().strftime("%Y%m%d_%H%M")
    base_path = (
        Path("ln_shared_data")
        / "onestop"
        / "OneStop_v1_20250126"
        / "lacclab_processed"
        / f"trial_plots/condition_prediction/{'flat' if x_is_word_index else 'screen'}_{current_time}"
    )
    n_parallel = 60  # Adjust based on system resources

    # X/Y plotting limits
    margin = 100
    min_x, max_x = 300, 300 + 1824
    min_y, max_y = 165, 1440 - 1 * 165
    x_limits = (min_x - margin, max_x + margin)
    y_limits = (min_y - margin, max_y + margin)

    # ---------------
    # Load fixations
    # ---------------
    feather_path = (
        "ln_shared_data/onestop/OneStop_v1_20250126/"
        "lacclab_processed/fixations_Paragraph_col_subset_for_plotting.feather"
    )
    csv_path = (
        "ln_shared_data/onestop/OneStop_v1_20250126/"
        "lacclab_processed/fixations_Paragraph.csv"
    )

    if Path(feather_path).exists():
        print(f"Loading fixations from: {feather_path}")
        fixations = pd.read_feather(feather_path)
    else:
        print(f"Loading fixations from: {csv_path}")
        fixations = pd.read_csv(csv_path, engine="pyarrow")
        fixations.NEXT_FIX_INTEREST_AREA_INDEX = (
            fixations.NEXT_FIX_INTEREST_AREA_INDEX.astype(int)
        )
        fixations = add_features(fixations)
        relevant_columns = [
            "participant_id",
            "unique_paragraph_id",
            "CURRENT_FIX_X",
            "CURRENT_FIX_Y",
            "CURRENT_FIX_DURATION",
            "CURRENT_FIX_INTEREST_AREA_INDEX",
            "NEXT_FIX_INTEREST_AREA_INDEX",
            "question_preview",
            "repeated_reading_trial",
            "practice_trial",
            "saccade_type",
        ]
        fixations = fixations[relevant_columns]
        fixations.to_feather(feather_path)

    # Filter data
    fixations = fixations[
        (~fixations["repeated_reading_trial"].astype(bool))
        & (~fixations["practice_trial"].astype(bool))
    ]
    # Print summaries
    print(f"Total rows: {len(fixations)}")
    print(f"Participants: {fixations['participant_id'].nunique()}")
    print(f"Unique paragraphs: {fixations['unique_paragraph_id'].nunique()}")
    trials_summary = (
        fixations.drop_duplicates(subset=["participant_id", "unique_paragraph_id"])
        .groupby("question_preview")
        .size()
    )
    print(f"Trials per condition:\n{trials_summary}")

    # Ensure directories exist for each condition
    for condition in fixations["question_preview"].unique():
        (base_path / str(condition)).mkdir(parents=True, exist_ok=True)
    print(f"Saving plots to: {base_path}")

    # Prepare data for parallel processing
    participants = fixations["participant_id"].unique()
    tasks = [
        (
            participant_id,
            fixations,
            x_is_word_index,
            base_path,
            x_limits,
            y_limits,
            debug,
        )
        for participant_id in participants
    ]

    # Process data in parallel
    if not debug:
        with Pool(processes=n_parallel) as pool:
            for _ in tqdm(
                pool.imap_unordered(process_subject, tasks),
                total=len(tasks),
                desc="Processing participants",
            ):
                pass
        print("All subjects processed.")
    else:
        # Debug mode: process the first participant only
        process_subject(tasks[0])
        print("Debug mode: first subject processed.")


if __name__ == "__main__":
    main()

# %%
