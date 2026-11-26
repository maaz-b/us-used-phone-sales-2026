"""sample_swappa_scraper.py
------------------------
DISCLAIMER:
Automated requests must comply with platform policies, terms of service, and rate limits.
This sample collector is provided strictly for academic reproducibility and methodological
transparency. It uses an automated browser driver with natural request throttling to extract
completed secondary market smartphone sales transactions.
"""

import os
import re
import sys
import time
from pathlib import Path

import pandas as pd
from bs4 import BeautifulSoup

try:
    import undetected_chromedriver as uc
except ImportError:
    uc = None
    print(
        "Notice: 'undetected-chromedriver' is not installed. Install via: pip"
        " install undetected-chromedriver"
    )

# Default paths aligned with repository architecture
DEFAULT_INPUT_MODELS = "data/phone_list.csv"
DEFAULT_OUTPUT_CSV = "data/raw/swappa_sales_sample.csv"


def extract_sales_from_price_page(html_text: str, model_slug: str):
    """Parses Swappa price history DOM markup to extract completed transactions.

    Handles both 5-column (Date, Condition, Carrier, Storage, Price) and
    4-column (unlocked default) tabular variants.
    """
    soup = BeautifulSoup(html_text, "html.parser")
    records = []
    tables = soup.find_all("table")

    for table in tables:
        caption = table.find("caption")
        caption_text = caption.get_text(strip=True).lower() if caption else ""

        if "sales" in caption_text or any(
            "condition" in th.get_text().lower() for th in table.find_all("th")
        ):
            rows = (
                table.find("tbody").find_all("tr")
                if table.find("tbody")
                else table.find_all("tr")
            )
            for row in rows:
                cols = [td.get_text(strip=True) for td in row.find_all("td")]
                if len(cols) == 5:
                    date, condition, carrier, storage, price = cols
                elif len(cols) == 4:
                    date, condition, storage, price = cols
                    carrier = "Unlocked"
                else:
                    continue

                clean_price = (
                    float(re.sub(r"[^\d.]", "", price))
                    if re.search(r"\d", price)
                    else None
                )
                clean_storage = (
                    int(re.search(r"\d+", storage).group())
                    if re.search(r"\d+", storage)
                    else None
                )

                if clean_price is not None:
                    records.append(
                        {
                            "model": model_slug,
                            "sale_date": date,
                            "condition": condition,
                            "carrier": carrier,
                            "storage_gb": (
                                float(clean_storage)
                                if clean_storage is not None
                                else None
                            ),
                            "price_usd": clean_price,
                        }
                    )
    return records


def run_sample_collector(
    target_models_path: str = DEFAULT_INPUT_MODELS,
    output_csv_path: str = DEFAULT_OUTPUT_CSV,
    max_models: int = None,
):
    if uc is None:
        raise SystemExit(
            "Missing dependency: Run 'pip install undetected-chromedriver' to use"
            " this script."
        )

    if not os.path.exists(target_models_path):
        print(
            f"Target models file '{target_models_path}' not found. Creating minimal"
            " sample list..."
        )
        Path(target_models_path).parent.mkdir(parents=True, exist_ok=True)
        sample_df = pd.DataFrame(
            {
                "0": [
                    "google-pixel-8a",
                    "apple-iphone-14-pro",
                    "samsung-galaxy-s23-ultra",
                ]
            }
        )
        sample_df.to_csv(target_models_path)

    target_models_df = pd.read_csv(target_models_path, index_col=0)
    target_models = target_models_df["0"].astype(str).tolist()

    if max_models is not None:
        target_models = target_models[:max_models]

    scraped_already = set()
    if os.path.exists(output_csv_path):
        existing_df = pd.read_csv(output_csv_path)
        if "model" in existing_df.columns:
            scraped_already = set(existing_df["model"].unique())
            print(
                f"Resuming run: {len(scraped_already)} models already in"
                f" {output_csv_path}."
            )

    Path(output_csv_path).parent.mkdir(parents=True, exist_ok=True)

    options = uc.ChromeOptions()
    driver = uc.Chrome(options=options)

    try:
        total = len(target_models)
        for idx, model in enumerate(target_models, 1):
            if model in scraped_already:
                continue

            # This url was used at the time of data collection, use your / updated url
            url = f"https://swappa.com/prices/{model}"

            driver.get(url)
            time.sleep(2.5)

            # Allow time if verification challenge appears
            if "Just a moment..." in driver.title:
                print(
                    f"[{idx}/{total}] Challenge detected on {model}, waiting for"
                    " resolution..."
                )
                time.sleep(6.0)

            records = extract_sales_from_price_page(driver.page_source, model)

            if records:
                df_batch = pd.DataFrame(records)
                header_needed = (
                    not os.path.exists(output_csv_path)
                    or os.path.getsize(output_csv_path) == 0
                )
                df_batch.to_csv(
                    output_csv_path, mode="a", index=False, header=header_needed
                )
                print(f"[{idx}/{total}] {model}: +{len(records)} sales recorded.")
            else:
                print(f"[{idx}/{total}] {model}: 0 sales found (or unindexed).")

            # Dynamic jitter delay (2.5 to 4.5 seconds) to respect platform load
            time.sleep(2.5 + (idx % 3))

    finally:
        driver.quit()


if __name__ == "__main__":
    in_path = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_INPUT_MODELS
    out_path = sys.argv[2] if len(sys.argv) > 2 else DEFAULT_OUTPUT_CSV
    limit = int(sys.argv[3]) if len(sys.argv) > 3 else None

    run_sample_collector(
        target_models_path=in_path, output_csv_path=out_path, max_models=limit
    )
