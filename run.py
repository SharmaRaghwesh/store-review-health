"""End to end: CSV -> outputs/store_summary.csv + outputs/review_phrases.parquet.

Run from the project root:  python run.py
"""
import config
from src.load import load_reviews
from src.phrases import build_phrases
from src.rating import build_ratings
from src.summary import build_summary
from src.build_ui import build_ui


def main():
    config.OUTPUT_DIR.mkdir(exist_ok=True)

    reviews = load_reviews()
    ratings = build_ratings(reviews)
    phrases = build_phrases(reviews)
    summary = build_summary(reviews, ratings, phrases)

    phrases.to_parquet(config.OUTPUT_DIR / "review_phrases.parquet", index=False)
    # lists are flattened to "a (3); b (2)" for the CSV
    flat = summary.assign(**{c: summary[c].str.join("; ") for c in ("top_positive", "top_negative")})
    flat.to_csv(config.OUTPUT_DIR / "store_summary.csv", index=False)

    build_ui(reviews, summary, phrases)

    print(f"\nwrote {config.OUTPUT_DIR / 'review_phrases.parquet'}  ({len(phrases):,} rows)")
    print(f"wrote {config.OUTPUT_DIR / 'store_summary.csv'}  ({len(summary):,} rows)")


if __name__ == "__main__":
    main()
