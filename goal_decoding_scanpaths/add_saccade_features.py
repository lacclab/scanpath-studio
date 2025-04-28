import pandas as pd


def get_fixation_patch_idx(cnf, fixation_x, fixation_y, IA_ID):
    if fixation_x < 0 or fixation_y < 0 or IA_ID < 0:
        return -1
    offset_x = cnf["paragraph_offset_width"]
    offset_y = cnf["paragraph_offset_height"] - (cnf["spacing_height"] // 2)

    patch_width = cnf["font_width"] * cnf["num_chars_in_patch"]
    patch_height = cnf["font_height"] + cnf["spacing_height"]

    x = fixation_x - offset_x
    y = fixation_y - offset_y
    patch = (x // patch_width) + (
        (y // patch_height) * (cnf["text_area_width"] // patch_width)
    )
    if patch < 0:
        return -1
    return patch


SACCADE_TYPES_TOKENS = {
    "forward_saccade": "<fs>",
    "regression": "<rg>",
    "skip": "<sk>",
    "refixation": "<rf>",
    "return_sweep": "<rs>",
    "out_of_bounds": "<oob>",
}


def add_features(df: pd.DataFrame, add_skip_distance: bool = False) -> pd.DataFrame:
    required_columns = [
        "CURRENT_FIX_X",
        "CURRENT_FIX_Y",
        "CURRENT_FIX_INTEREST_AREA_INDEX",
        "NEXT_FIX_INTEREST_AREA_INDEX",
    ]

    for col in required_columns:
        if col not in df.columns:
            raise ValueError(f"Missing required column: {col}")
    # Initialize saccade_type as None
    cnf = {
        "font_height": 38,
        "font_width": 19,
        "num_chars_in_patch": 1824 / 19,  # One per line
        "paragraph_offset_height": 186,
        "paragraph_offset_width": 300,
        "text_area_width": 1824,
        "spacing_height": 76,
    }
    df["current_fixation_patch_idx"] = df.apply(
        lambda x: get_fixation_patch_idx(
            cnf,
            x["CURRENT_FIX_X"],
            x["CURRENT_FIX_Y"],
            x["CURRENT_FIX_INTEREST_AREA_INDEX"],
        ),
        axis=1,
    ).astype(int)

    # use shift
    df["next_fixation_patch_idx"] = (
        df["current_fixation_patch_idx"].shift(-1).fillna(-1).astype(int)
    )

    df["saccade_type"] = None

    # Out of bounds
    df.loc[
        df["CURRENT_FIX_INTEREST_AREA_INDEX"] == -1,
        "saccade_type",
    ] = SACCADE_TYPES_TOKENS["out_of_bounds"]

    # Forward saccade
    df.loc[
        df["NEXT_FIX_INTEREST_AREA_INDEX"] == df["CURRENT_FIX_INTEREST_AREA_INDEX"] + 1,
        "saccade_type",
    ] = SACCADE_TYPES_TOKENS["forward_saccade"]

    # Regression
    df.loc[
        df["NEXT_FIX_INTEREST_AREA_INDEX"] < df["CURRENT_FIX_INTEREST_AREA_INDEX"],
        "saccade_type",
    ] = SACCADE_TYPES_TOKENS["regression"]

    # Skip (jumping over one or more areas)
    if add_skip_distance:
        df.loc[
            df["NEXT_FIX_INTEREST_AREA_INDEX"]
            > df["CURRENT_FIX_INTEREST_AREA_INDEX"] + 1,
            "saccade_type",
        ] = SACCADE_TYPES_TOKENS["skip"] + (
            df["NEXT_FIX_INTEREST_AREA_INDEX"].astype(int)
            - df["CURRENT_FIX_INTEREST_AREA_INDEX"].astype(int)
        ).astype(str)
    else:
        df.loc[
            df["NEXT_FIX_INTEREST_AREA_INDEX"]
            > df["CURRENT_FIX_INTEREST_AREA_INDEX"] + 1,
            "saccade_type",
        ] = SACCADE_TYPES_TOKENS["skip"]

    # Refixation (fixating on the same area again)
    df.loc[
        df["NEXT_FIX_INTEREST_AREA_INDEX"] == df["CURRENT_FIX_INTEREST_AREA_INDEX"],
        "saccade_type",
    ] = SACCADE_TYPES_TOKENS["refixation"]

    # Return sweep (specific rule: returning to a lower line)
    df.loc[
        (df["next_fixation_patch_idx"] > df["current_fixation_patch_idx"]),
        "saccade_type",
    ] = SACCADE_TYPES_TOKENS["return_sweep"]

    return df
