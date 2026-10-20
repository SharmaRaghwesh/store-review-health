"""All dates, thresholds and vocabularies live here. Nothing below is hard-coded elsewhere."""
from pathlib import Path

# ---- paths ----
ROOT = Path(__file__).resolve().parent
RAW_CSV = ROOT / "Subway_reviews_text_updated.csv"
OUTPUT_DIR = ROOT / "outputs"
UI_DIR = ROOT / "ui"

# ---- load ----
# August 2026 is an incomplete pull; ignore everything after this date until a full pull arrives.
AS_OF_DATE = "2026-07-31"
DEDUPE_KEYS = ["store_id", "user_review_date", "user_review_text", "rating"]

# ---- rating ----
RATING_WINDOW_STEPS = [90, 180, 365, 730]  # days; extend until MIN_REVIEWS_FOR_RATING is met
MIN_REVIEWS_FOR_RATING = 10
SMOOTHING_K = 5  # (sum(r) + k * prior) / (n + k), prior = store all-time mean
WINDOW_LABELS = {90: "last 3 months", 180: "last 6 months", 365: "last 12 months", 730: "last 2 years"}

# ---- phrases ----
PHRASE_WINDOW_DAYS = 365
PHRASE_WINDOW_FALLBACK_DAYS = 730  # used (and flagged low confidence) below MIN_TEXT_REVIEWS
MIN_TEXT_REVIEWS = 15
TOP_N_PHRASES = 5  # per store, per polarity
MIN_WORDS_FOR_PHRASES = 2  # single-word reviews ("Good", "Nice") have no aspect; skip them
SPACY_MODEL = "en_core_web_sm"
SPACY_BATCH_SIZE = 256
SPACY_DISABLE = ["ner"]
N_PROCESS_RESERVED_CORES = 4  # leave this many cores free
SPACY_MULTIPROCESS_MIN_ROWS = 5000  # below this, a single process is faster

# canonical aspect -> nouns (lemmas) that map to it
ASPECT_MAP = {
    "food": ["food", "sandwich", "sub", "meal", "wrap"],
    "bread": ["bread", "bun"],
    "veggies": ["veggie", "vegetable", "veg", "salad"],
    "sauce": ["sauce"],
    "cheese": ["cheese"],
    "protein": ["meat", "chicken", "paneer"],
    "taste": ["taste", "flavour", "flavor"],
    "quality": ["quality"],
    "portion": ["portion", "quantity"],
    "price": ["price", "value"],
    "staff": ["staff", "employee", "guy", "people", "crew", "behaviour", "behavior", "team", "manager", "person",
              "attitude"],
    "service": ["service"],
    "speed": ["speed", "wait", "time", "delay"],
    "cleanliness": ["cleanliness", "hygiene"],
    "ambience": ["ambience", "ambiance", "atmosphere", "seating"],
    "delivery": ["delivery", "order"],
}
NOUN_TO_ASPECT = {noun: aspect for aspect, nouns in ASPECT_MAP.items() for noun in nouns}

# generic nouns — not actionable, dropped
GENERIC_NOUNS = {"place", "experience", "outlet", "store", "subway"}

# adjectives that carry no opinion
STOP_ADJECTIVES = {
    "other", "same", "last", "whole", "first", "next",
    "many", "few", "more", "much", "such", "own",
    "online", "overall", "particular",
    # counting / menu words, not opinions
    "second", "third", "fourth", "double", "single", "multiple", "several", "most", "only",
    "classic", "regular", "extra", "main", "total", "co",
}

# star-rating fallback for phrase polarity
POSITIVE_MIN_RATING = 4
NEGATIVE_MAX_RATING = 2

# words that negate an opinion ("not fresh bread" must not count as "fresh bread")
NEGATION_WORDS = {"not", "n't", "no", "never", "neither", "nor", "hardly", "barely"}

# small adjective lexicon (lemmas); anything not listed falls back to the star rating
POSITIVE_ADJECTIVES = {
    "good", "great", "nice", "fresh", "tasty", "delicious", "yummy", "excellent", "amazing", "awesome",
    "friendly", "polite", "helpful", "courteous", "quick", "fast", "clean", "hygienic", "neat", "soft",
    "healthy", "perfect", "wonderful", "fantastic", "superb", "lovely", "cool", "decent", "fine",
    "reasonable", "affordable", "cheap", "generous", "prompt", "efficient", "attentive", "kind", "humble",
    "sweet", "happy", "warm", "comfortable", "cozy", "pleasant", "super", "outstanding", "brilliant",
    "professional", "well", "crispy", "juicy", "hot", "satisfied", "cooperative", "supportive",
}
NEGATIVE_ADJECTIVES = {
    "bad", "poor", "terrible", "horrible", "awful", "pathetic", "rude", "slow", "stale", "sour", "cold",
    "dirty", "unhygienic", "rotten", "soggy", "dry", "hard", "bland", "tasteless", "expensive", "costly",
    "overpriced", "pricey", "small", "less", "little", "late", "wrong", "arrogant", "unprofessional",
    "lazy", "careless", "disappointing", "disgusting", "unfriendly", "impolite", "raw", "smelly", "old",
    "long", "untrained", "useless", "ridiculous", "unacceptable", "average", "mediocre", "filthy",
    "unclean", "burnt", "incomplete", "missing", "low", "high", "limited", "uncooked", "spoiled",
    "ill", "disrespectful", "irresponsible", "worthless", "unhealthy", "sad", "unhappy",
}

# ---- UI ----
# store health tiers on the recent raw average: (minimum rating, label), best first
UI_RATING_TIERS = [(4.3, "Healthy"), (3.7, "Watch"), (3.0, "At risk"), (0.0, "Critical")]
UI_TOP_N_PHRASES = 8  # chips per polarity in the store panel

UI_PORT = 8765  # local port for serve_ui.py
UI_SCOPE = "India"  # shown in the UI header

# ---- deploy (public demo) ----
# small, shareable copy of the UI with one city only; no city column, so a lat/long box
DEPLOY_DIR = ROOT / "deploy"
DEPLOY_SCOPE = "Bengaluru"
DEPLOY_BBOX = {"lat": (12.75, 13.25), "lon": (77.35, 77.85)}
