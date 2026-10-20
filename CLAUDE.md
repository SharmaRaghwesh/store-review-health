# Store Review Health Check — Subway (India)

## Goal
For each retail store, show (like the Google Maps "Reviews" tab):
1. **Recent average rating** over an adaptive time window, with the review count and window shown.
2. **Top opinion phrases** (aspect + opinion, e.g. "sour bread", "rude staff", "good service" — never bare
   words like "bread" or "service"), coloured by sentiment, with counts.
The point is a store health check: what customers praise, and what the store must fix now.

## Data
File: `Subway_reviews_text_updated.csv` (in this folder). ~56,000 rows, 947 stores, Oct 2024 – Aug 2026.

| column | notes |
|---|---|
| `store_id` | **Primary key.** Built from title + lat + long; human-readable. Always group by this. |
| `title` | Store name. NOT unique (32 different stores are titled just "Subway"). Never group by title. |
| `latitude`, `longitude` | Store location |
| `place_id` | Google place id. 1:1 with store_id. Keep as a backend column for mapping future re-pulls. |
| `user_review_date` | Real timestamp (mixed format, parse with `pd.to_datetime(..., format="mixed")`) |
| `user_review_date_str` | Same date as YYYY-MM-DD string |
| `user_review_text` | Review text. ~41% empty (rating-only reviews) |
| `rating` | 1–5 stars |

Known facts from profiling:
- 230 duplicate rows (same store_id, date, text, rating) → drop.
- August 2026 is incomplete (545 reviews vs ~2,500–3,100 in other months). Use **AS_OF_DATE = 2026-07-31**
  for all windows and ignore reviews after it, until a complete pull arrives. Keep this a config value.
- Reviews per store over 2 years: median 47, 10% of stores have ≤12, max 1,031.
- Text reviews average 3.51★ vs 4.42★ for rating-only reviews (people write when unhappy).
- Median text review is 10 words; ~8,000 are ≤3 words. Mostly English with emojis; very little Devanagari.

## Method decisions (already agreed)

### Rating
- **Adaptive window:** try 90 days; if the store has < 10 reviews, extend to 180, then 365, then 730 days.
  On current data (counted back from AS_OF_DATE) this puts ~30% of stores on 90d, 30% on 180d, 25% on 365d,
  15% on 730d.
- **Smoothed (Bayesian) average:** `(sum(r) + k * prior) / (n + k)`, k = 5, prior = store's all-time mean
  (fallback: brand mean). Report both raw and smoothed averages.
- Output always includes window length and review count, e.g. "3.2★ · 11 reviews · last 6 months".

### Phrases
- Use **text reviews in the last 365 days** (median store has only ~3 text reviews in 90 days — too few).
  Require ≥ 15 text reviews; otherwise extend to 730 days and flag low confidence.
- Only reviews with **at least two words** count as text reviews for phrases (single-word reviews like
  "Good" are skipped and do not count towards the 15). `MIN_WORDS_FOR_PHRASES` in config.
- Extraction with **spaCy** (`en_core_web_sm`) dependency parsing:
  - `amod`: adjective modifying a noun → "sour bread", "bad veggies"
  - `acomp` + `nsubj`: "the bread was sour" → "sour bread"
  - Negation: "not fresh bread" must not count as "fresh bread".
  - Lemmatise (veggies → veggie) and lowercase.
- **Fixed aspect list** (map synonyms → canonical aspect); drop phrases whose noun is not in it:
  food (food, sandwich, sub, meal, wrap), bread, veggies (veggie, vegetable, veg, salad), sauce, cheese, meat/chicken/paneer (protein), taste, quality,
  portion/quantity, price/value, staff (staff, employee, guy, people, crew, behaviour, team, manager, person, attitude), service, speed/wait (wait, time,
  delay), cleanliness/hygiene, ambience/seating/atmosphere, delivery/order accuracy.
  Generic nouns (place, experience, outlet, store, subway) are dropped — not actionable.
- Drop non-opinion adjectives: other, same, last, whole, first, next, many, few, more, much, such, own, online,
  overall, particular.
- Polarity per phrase: small positive/negative adjective lexicon; fall back to the review's star rating
  (≥4 positive, ≤2 negative, 3 neutral).
- Count each phrase **once per review**, not once per mention.
- Later (optional): an LLM pass to catch opinions without adjectives ("even helped us with rain" → helpful
  staff) and Hinglish. Return JSON `{aspect, opinion, polarity}` using the same fixed aspect list.

## Data model
Long/tidy tables, never lists inside cells for storage:
- `reviews`: review_id, store_id, place_id, title, lat, long, review_date, rating, text
- `review_phrases`: review_id, store_id, aspect, opinion, phrase, polarity (one row per phrase)
- `store_summary`: store_id, title, window_days, n_reviews, avg_rating_raw, avg_rating_smoothed,
  alltime_avg, phrase_window_days, n_text_reviews, top_positive (list), top_negative (list), low_confidence

## Project layout (target)
```
config.py            # AS_OF_DATE, window steps, min counts, k, aspect map, stop-adjectives
src/load.py          # read CSV, parse dates, dedupe, cut at AS_OF_DATE
src/rating.py        # adaptive window + smoothed average
src/phrases.py       # spaCy extraction, aspect mapping, polarity
src/summary.py       # build store_summary
run.py               # end-to-end: CSV → outputs/
outputs/             # store_summary.csv, review_phrases.parquet
```

## Conventions
- Python 3.10+, pandas, spaCy. Use a virtualenv (`.venv`). Keep `requirements.txt` updated.
- Run spaCy with `nlp.pipe(..., batch_size=256)` and disable unused components (ner) for speed.
- Every step prints a short sanity summary (row counts, stores, window split).
- Don't hard-code dates or thresholds outside `config.py`.
