"""Step 5: write the data files the map UI (ui/index.html) reads.

ui/data/stores.js   — one light record per store (map + list)
ui/data/s/<i>.js    — per-store detail (star split, phrases, aspects, reviews), loaded on click

Plain .js files (not JSON + fetch) so the UI opens straight from disk without a server.
Run from the project root:  python -m src.build_ui   (uses the existing outputs/, no spaCy re-run)
"""
import json
import shutil

import pandas as pd

import config
from src.load import load_reviews

POLARITY_CODE = {"positive": 1, "negative": -1, "neutral": 0}


def _tier(avg, n) -> int:
    """Index into UI_RATING_TIERS, or -1 when there are too few reviews to judge."""
    if n < config.MIN_REVIEWS_FOR_RATING or pd.isna(avg):
        return -1
    for i, (floor, _) in enumerate(config.UI_RATING_TIERS):
        if avg >= floor:
            return i
    return len(config.UI_RATING_TIERS) - 1


def _top(ph: pd.DataFrame, polarity: str) -> list:
    counts = ph.loc[ph["polarity"] == polarity, "phrase"].value_counts()
    counts = counts.rename_axis("phrase").reset_index(name="n").sort_values(["n", "phrase"], ascending=[False, True])
    return counts.head(config.UI_TOP_N_PHRASES).values.tolist()


def _js(obj) -> str:
    return json.dumps(obj, ensure_ascii=True, separators=(",", ":"))


def build_ui(reviews, summary, phrases, as_of=config.AS_OF_DATE, verbose=True):
    data_dir = config.UI_DIR / "data"
    if data_dir.exists():
        shutil.rmtree(data_dir)  # generated folder; rebuilt from scratch every run
    (data_dir / "s").mkdir(parents=True)

    window_end = pd.Timestamp(as_of) + pd.Timedelta(days=1)
    reviews = reviews.assign(days_ago=(window_end - reviews["review_date"]).dt.total_seconds() / 86400)
    phrases = phrases.merge(reviews[["review_id", "days_ago"]], on="review_id")

    geo = reviews.groupby("store_id")[["lat", "long"]].first()
    reviews_by = dict(tuple(reviews.groupby("store_id")))
    phrases_by = dict(tuple(phrases.groupby("store_id")))
    empty_ph = phrases.iloc[0:0]

    stores = []
    for i, s in enumerate(summary.sort_values("store_id").itertuples(index=False)):
        rv = reviews_by[s.store_id]
        ph = phrases_by.get(s.store_id, empty_ph)
        ph_win = ph[ph["days_ago"] <= s.phrase_window_days]

        in_rating_window = rv[rv["days_ago"] <= s.window_days]
        stars = in_rating_window["rating"].round().astype(int).value_counts()
        aspects = (
            ph_win[ph_win["polarity"] != "neutral"]
            .groupby(["aspect", "polarity"])["review_id"].nunique().unstack(fill_value=0)
            .reindex(columns=["positive", "negative"], fill_value=0)
        )
        aspects = aspects.assign(total=aspects.sum(axis=1)).sort_values("total", ascending=False)

        review_phrases = {
            rid: g[["phrase", "polarity", "aspect"]].assign(polarity=g["polarity"].map(POLARITY_CODE)).values.tolist()
            for rid, g in ph.groupby("review_id")
        }
        text_rv = rv[rv["text"] != ""].sort_values("review_date", ascending=False)
        detail = {
            "stars": [int(stars.get(k, 0)) for k in (1, 2, 3, 4, 5)],
            "pos": _top(ph_win, "positive"),
            "neg": _top(ph_win, "negative"),
            "aspects": [[a, int(r.positive), int(r.negative)] for a, r in aspects.iterrows()],
            "reviews": [
                {
                    "d": r.review_date.strftime("%Y-%m-%d"), "r": int(round(r.rating)), "x": r.text,
                    "p": review_phrases.get(r.review_id, []),
                    "w": int(r.days_ago <= s.phrase_window_days),
                }
                for r in text_rv.itertuples(index=False)
            ],
        }
        (data_dir / "s" / f"{i}.js").write_text(f"window.__store({i},{_js(detail)});", encoding="utf-8")

        raw = None if pd.isna(s.avg_rating_raw) else round(float(s.avg_rating_raw), 2)
        stores.append({
            "i": i, "id": s.store_id, "t": s.title,
            "la": round(float(geo.at[s.store_id, "lat"]), 6), "lo": round(float(geo.at[s.store_id, "long"]), 6),
            "w": int(s.window_days), "n": int(s.n_reviews), "raw": raw,
            "sm": round(float(s.avg_rating_smoothed), 2), "all": round(float(s.alltime_avg), 2),
            "alln": len(rv), "tier": _tier(s.avg_rating_raw, s.n_reviews),
            "pw": int(s.phrase_window_days), "nt": int(s.n_text_reviews), "lc": bool(s.low_confidence),
            "np": int((ph_win["polarity"] == "positive").sum()), "nn": int((ph_win["polarity"] == "negative").sum()),
        })

    meta = {
        "asOf": as_of,
        "tiers": [{"min": m, "label": label} for m, label in config.UI_RATING_TIERS],
        "windowLabels": {str(k): v for k, v in config.WINDOW_LABELS.items()},
        "minReviews": config.MIN_REVIEWS_FOR_RATING,
        "minTextReviews": config.MIN_TEXT_REVIEWS,
        "scope": config.UI_SCOPE,
    }
    (data_dir / "stores.js").write_text(f"window.META={_js(meta)};\nwindow.STORES={_js(stores)};", encoding="utf-8")

    if verbose:
        tiers = pd.Series([s["tier"] for s in stores]).value_counts()
        size_mb = sum(f.stat().st_size for f in data_dir.rglob("*.js")) / 1e6
        print("\n=== ui: sanity summary ===")
        print(f"stores written          : {len(stores):,}  ({size_mb:.1f} MB in {data_dir})")
        for i, (floor, label) in enumerate(config.UI_RATING_TIERS):
            print(f"  {label:<9} (>= {floor:.1f})    : {tiers.get(i, 0)}")
        print(f"  too few reviews        : {tiers.get(-1, 0)}")
        print(f"open                    : {config.UI_DIR / 'index.html'}")


if __name__ == "__main__":
    summary = pd.read_csv(config.OUTPUT_DIR / "store_summary.csv")
    phrases = pd.read_parquet(config.OUTPUT_DIR / "review_phrases.parquet")
    build_ui(load_reviews(verbose=False), summary, phrases)
