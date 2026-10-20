"""Step 2: adaptive rating window + smoothed (Bayesian) average, one row per store.

Run from the project root:  python -m src.rating
"""
import pandas as pd

import config
from src.load import load_reviews


def build_ratings(reviews: pd.DataFrame, as_of=config.AS_OF_DATE, verbose=True) -> pd.DataFrame:
    steps = config.RATING_WINDOW_STEPS
    min_n = config.MIN_REVIEWS_FOR_RATING
    k = config.SMOOTHING_K

    # windows are counted back from the end of the AS_OF_DATE day
    window_end = pd.Timestamp(as_of) + pd.Timedelta(days=1)
    days_ago = (window_end - reviews["review_date"]).dt.total_seconds() / 86400

    by_store = reviews.groupby("store_id")
    out = by_store.agg(title=("title", "first"), alltime_avg=("rating", "mean"), alltime_n=("rating", "size"))

    # review count per store in each window step
    counts = pd.DataFrame(
        {d: (days_ago <= d).groupby(reviews["store_id"]).sum() for d in steps}
    ).reindex(out.index)

    # smallest window reaching min_n; stores that never reach it stay on the widest window
    out["window_days"] = steps[-1]
    for d in reversed(steps):
        out.loc[counts[d] >= min_n, "window_days"] = d

    in_window = days_ago <= reviews["store_id"].map(out["window_days"])
    win = reviews[in_window].groupby("store_id")["rating"].agg(n_reviews="size", rating_sum="sum")
    out = out.join(win)
    out["n_reviews"] = out["n_reviews"].fillna(0).astype(int)
    out["rating_sum"] = out["rating_sum"].fillna(0.0)

    brand_mean = reviews["rating"].mean()
    prior = out["alltime_avg"].fillna(brand_mean)
    out["avg_rating_raw"] = out["rating_sum"] / out["n_reviews"].where(out["n_reviews"] > 0)
    out["avg_rating_smoothed"] = (out["rating_sum"] + k * prior) / (out["n_reviews"] + k)
    out["below_min_reviews"] = out["n_reviews"] < min_n

    out["rating_label"] = (
        out["avg_rating_raw"].map("{:.1f}★".format)
        + " · " + out["n_reviews"].astype(str) + " reviews · "
        + out["window_days"].map(config.WINDOW_LABELS)
    )

    out = out.reset_index()[
        ["store_id", "title", "window_days", "n_reviews", "avg_rating_raw", "avg_rating_smoothed",
         "alltime_avg", "alltime_n", "below_min_reviews", "rating_label"]
    ]

    if verbose:
        share = out["window_days"].value_counts().reindex(steps, fill_value=0)
        print("\n=== rating: sanity summary ===")
        print(f"stores                  : {len(out):,}")
        print(f"as-of date              : {as_of}   min reviews: {min_n}   k: {k}")
        print("window split:")
        for d in steps:
            print(f"  {d:>3}d : {share[d]:>4} stores  ({share[d] / len(out):.1%})")
        print(f"still < {min_n} reviews at {steps[-1]}d : {int(out['below_min_reviews'].sum())} stores")
        print(f"brand mean rating       : {brand_mean:.2f}")
        print(f"mean |smoothed - raw|   : {(out['avg_rating_smoothed'] - out['avg_rating_raw']).abs().mean():.3f}")

    return out


if __name__ == "__main__":
    pd.set_option("display.width", 200, "display.max_columns", 20, "display.max_colwidth", 45)
    ratings = build_ratings(load_reviews())
    cols = ["store_id", "window_days", "n_reviews", "avg_rating_raw", "avg_rating_smoothed", "alltime_avg"]

    print("\n--- 10 sample stores ---")
    print(ratings.sample(10, random_state=0)[cols].round(2).to_string(index=False))

    print("\n--- 5 stores where smoothing moved the average most ---")
    shift = (ratings["avg_rating_smoothed"] - ratings["avg_rating_raw"]).rename("shift")
    top = ratings.assign(shift=shift).loc[shift.abs().sort_values(ascending=False).index[:5]]
    print(top[cols + ["shift", "alltime_n"]].round(2).to_string(index=False))
