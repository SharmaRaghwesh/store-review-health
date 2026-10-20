"""Step 4: one row per store — rating block + top opinion phrases in the phrase window."""
import pandas as pd

import config

SUMMARY_COLS = [
    "store_id", "title", "window_days", "n_reviews", "avg_rating_raw", "avg_rating_smoothed", "alltime_avg",
    "rating_label", "phrase_window_days", "n_text_reviews", "top_positive", "top_negative", "low_confidence",
]


def _top_phrases(phrases: pd.DataFrame, polarity: str) -> pd.Series:
    """Per store: list of "phrase (count)" for the TOP_N_PHRASES most frequent phrases."""
    counts = (
        phrases[phrases["polarity"] == polarity]
        .groupby(["store_id", "phrase"]).size().rename("n").reset_index()
        .sort_values(["store_id", "n", "phrase"], ascending=[True, False, True])
    )
    top = counts.groupby("store_id").head(config.TOP_N_PHRASES)
    return (top["phrase"] + " (" + top["n"].astype(str) + ")").groupby(top["store_id"]).agg(list)


def build_summary(reviews, ratings, phrases, as_of=config.AS_OF_DATE, verbose=True) -> pd.DataFrame:
    window_end = pd.Timestamp(as_of) + pd.Timedelta(days=1)
    days_ago = (window_end - reviews["review_date"]).dt.total_seconds() / 86400

    # only reviews with enough words count as text reviews for phrases
    is_text = reviews["text"].str.split().str.len() >= config.MIN_WORDS_FOR_PHRASES
    n_short = (is_text & (days_ago <= config.PHRASE_WINDOW_DAYS)).groupby(reviews["store_id"]).sum()
    n_long = (is_text & (days_ago <= config.PHRASE_WINDOW_FALLBACK_DAYS)).groupby(reviews["store_id"]).sum()

    out = ratings.set_index("store_id")
    enough = n_short.reindex(out.index, fill_value=0) >= config.MIN_TEXT_REVIEWS
    out["phrase_window_days"] = enough.map({True: config.PHRASE_WINDOW_DAYS, False: config.PHRASE_WINDOW_FALLBACK_DAYS})
    out["n_text_reviews"] = n_short.where(enough, n_long).reindex(out.index, fill_value=0).astype(int)
    out["low_confidence"] = ~enough

    # keep only phrases from reviews inside each store's phrase window
    review_days = pd.Series(days_ago.values, index=reviews["review_id"])
    in_window = phrases["review_id"].map(review_days) <= phrases["store_id"].map(out["phrase_window_days"])
    windowed = phrases[in_window.values]

    for col, polarity in (("top_positive", "positive"), ("top_negative", "negative")):
        out[col] = _top_phrases(windowed, polarity).reindex(out.index)
        out[col] = out[col].map(lambda v: v if isinstance(v, list) else [])

    out = out.reset_index()[SUMMARY_COLS]

    if verbose:
        n = len(out)
        split = out["phrase_window_days"].value_counts()
        print("\n=== summary: sanity summary ===")
        print(f"stores                       : {n:,}")
        for d in (config.PHRASE_WINDOW_DAYS, config.PHRASE_WINDOW_FALLBACK_DAYS):
            print(f"phrase window {d:>3}d           : {split.get(d, 0):>4} stores  ({split.get(d, 0) / n:.1%})")
        print(f"low confidence               : {int(out['low_confidence'].sum())} stores")
        print(f"median text reviews in window: {out['n_text_reviews'].median():.0f}")
        print(f"phrases inside windows       : {len(windowed):,} of {len(phrases):,}")
        print(f"stores with no positive phrase: {int((out['top_positive'].str.len() == 0).sum())}")
        print(f"stores with no negative phrase: {int((out['top_negative'].str.len() == 0).sum())}")

    return out
