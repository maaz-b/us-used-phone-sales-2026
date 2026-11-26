"""
merge_sales_and_specs.py
------------------------
Simple, robust pipeline to join smartphone secondary market sales transactions
with canonical hardware specifications using normalized exact and fuzzy matching.
"""

import re

import pandas as pd
from rapidfuzz import fuzz, process


def clean_model_key(text: str) -> str:
    """
    Normalizes model names for deterministic key matching.
    Strips regional tags, carrier/network tokens, punctuation, and excess spaces.
    """
    if not isinstance(text, str):
        return ""
    text = text.lower()
    text = re.sub(r"\(.*?\)", "", text)
    text = re.sub(r"\b(5g|4g|lte)\b", "", text)
    text = re.sub(r"[\-_\/]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def merge_datasets(
    sales_path: str = "../data/raw_dataset.csv",
    specs_path: str = "../data/device_specs_reference.csv",
    output_path: str = "../data/us_used_phone_sales_augmented_2026.csv",
    fuzzy_cutoff: float = 85.0,
):
    print(f"Loading sales data from: {sales_path}")
    df_sales = pd.read_csv(sales_path)

    print(f"Loading specifications from: {specs_path}")
    df_specs = pd.read_csv(specs_path)

    for col in ["Unnamed: 0", "index"]:
        if col in df_sales.columns:
            df_sales = df_sales.drop(columns=[col])

    print("Normalizing model names...")
    df_sales["clean_key"] = df_sales["model"].apply(clean_model_key)
    df_specs["clean_key"] = df_specs["model_name"].apply(clean_model_key)

    df_specs_unique = df_specs.drop_duplicates(subset=["clean_key"]).copy()

    sales_unique_keys = df_sales["clean_key"].unique()
    specs_candidate_keys = df_specs_unique["clean_key"].tolist()

    print(
        f"Unique models in sales: {len(sales_unique_keys)} | Unique specs cataloged: {len(specs_candidate_keys)}"
    )

    key_mapping = {}
    matched_exact = 0
    matched_fuzzy = 0
    unmatched = 0

    for s_key in sales_unique_keys:
        if not s_key:
            key_mapping[s_key] = None
            unmatched += 1
            continue

        if s_key in specs_candidate_keys:
            key_mapping[s_key] = s_key
            matched_exact += 1
        elif process is not None:
            match = process.extractOne(
                s_key,
                specs_candidate_keys,
                scorer=fuzz.token_sort_ratio,
                score_cutoff=fuzzy_cutoff,
            )
            if match:
                best_match, score, _ = match
                key_mapping[s_key] = best_match
                matched_fuzzy += 1
            else:
                key_mapping[s_key] = None
                unmatched += 1
        else:
            key_mapping[s_key] = None
            unmatched += 1

    print(
        f"Model Key Resolution: {matched_exact} exact, {matched_fuzzy} fuzzy (cutoff >={fuzzy_cutoff}), {unmatched} unmatched."
    )

    df_sales["spec_matched_key"] = df_sales["clean_key"].map(key_mapping)

    df_merged = df_sales.merge(
        df_specs_unique,
        left_on="spec_matched_key",
        right_on="clean_key",
        how="left",
        suffixes=("", "_specs"),
    )

    temp_cols = ["clean_key", "spec_matched_key", "clean_key_specs"]
    df_merged = df_merged.drop(columns=[c for c in temp_cols if c in df_merged.columns])

    total_rows = len(df_merged)
    spec_matched_rows = df_merged["chipset"].notna().sum()
    match_pct = (spec_matched_rows / total_rows * 100) if total_rows > 0 else 0.0

    print(
        f"Dataset Merged Successfully: {spec_matched_rows}/{total_rows} ({match_pct:.2f}%) listings augmented with specs."
    )

    df_merged.to_csv(output_path, index=False)
    print(f"Saved merged dataset to: {output_path}")


if __name__ == "__main__":
    merge_datasets()
