"""Step 1: read the raw CSV, parse dates, dedupe, cut at AS_OF_DATE -> tidy `reviews` table.

Run from the project root:  python -m src.load
"""
import hashlib

import pandas as pd

import config


def _review_id(df: pd.DataFrame) -> pd.Series:
    """Stable id from the dedupe key, so ids survive a re-pull of the same reviews."""
    key = (
        df["store_id"].astype(str)
        + "|" + df["review_date"].dt.strftime("%Y-%m-%dT%H:%M:%S.%f")
        + "|" + df["text"]
        + "|" + df["rating"].astype(str)
    )
    return key.map(lambda s: hashlib.sha1(s.encode("utf-8")).hexdigest()[:16])


def load_reviews(path=config.RAW_CSV, as_of=config.AS_OF_DATE, verbose=True) -> pd.DataFrame:
    raw = pd.read_csv(path)
    n_raw, stores_raw = len(raw), raw["store_id"].nunique()

    raw["user_review_date"] = pd.to_datetime(raw["user_review_date"], format="mixed")
    raw["rating"] = raw["rating"].astype(float)
    n_bad_date = int(raw["user_review_date"].isna().sum())
    n_bad_rating = int((~raw["rating"].between(1, 5)).sum())

    deduped = raw.drop_duplicates(subset=config.DEDUPE_KEYS)
    n_dedup = len(deduped)

    # as-of cut is inclusive of the whole AS_OF_DATE day
    as_of_ts = pd.Timestamp(as_of)
    cut = deduped[deduped["user_review_date"] < as_of_ts + pd.Timedelta(days=1)]
    n_cut, stores_cut = len(cut), cut["store_id"].nunique()

    reviews = cut.rename(
        columns={
            "latitude": "lat",
            "longitude": "long",
            "user_review_date": "review_date",
            "user_review_text": "text",
        }
    )
    reviews["text"] = reviews["text"].fillna("").str.strip()
    reviews["review_id"] = _review_id(reviews)
    reviews = reviews[
        ["review_id", "store_id", "place_id", "title", "lat", "long", "review_date", "rating", "text"]
    ].sort_values(["store_id", "review_date"], ignore_index=True)

    if verbose:
        n_text = int((reviews["text"] != "").sum())
        print("=== load: sanity summary ===")
        print(f"file                    : {path.name}")
        print(f"rows read               : {n_raw:,}")
        print(f"rows after dedupe       : {n_dedup:,}  (dropped {n_raw - n_dedup:,} duplicates)")
        print(f"rows after as-of cut    : {n_cut:,}  (dropped {n_dedup - n_cut:,} after {as_of})")
        print(f"stores                  : {stores_cut:,}  (in raw file: {stores_raw:,})")
        print(f"date range kept         : {reviews['review_date'].min():%Y-%m-%d} -> {reviews['review_date'].max():%Y-%m-%d}")
        print(f"reviews with text       : {n_text:,}  ({n_text / n_cut:.1%})")
        print(f"mean rating             : {reviews['rating'].mean():.2f}")
        print(f"unparseable dates       : {n_bad_date:,}")
        print(f"ratings outside 1-5     : {n_bad_rating:,}")
        print(f"review_id unique        : {reviews['review_id'].is_unique}")
        print(f"place_id 1:1 store_id   : {bool((reviews.groupby('store_id')['place_id'].nunique() == 1).all() and (reviews.groupby('place_id')['store_id'].nunique() == 1).all())}")

    return reviews


if __name__ == "__main__":
    load_reviews()
