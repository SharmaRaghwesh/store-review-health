"""Step 3: spaCy aspect + opinion extraction -> tidy `review_phrases` (one row per phrase per review).

Run from the project root:  python -m src.phrases --sample 200
"""
import argparse
import os
import re

import pandas as pd
import spacy
from tqdm import tqdm

import config
from src.load import load_reviews

# "different.staff is slow" -> "different. staff is slow" so the tokenizer splits the sentences
MISSING_SPACE = re.compile(r"([A-Za-z]{2,})([.!?,]+)(?=[A-Za-z]{2,})")

PHRASE_COLS = ["review_id", "store_id", "aspect", "opinion", "phrase", "polarity"]


def load_nlp():
    return spacy.load(config.SPACY_MODEL, disable=config.SPACY_DISABLE)


def _is_neg(tok) -> bool:
    return tok.dep_ == "neg" or tok.lower_ in config.NEGATION_WORDS


def _with_conj_adjs(adj):
    """The adjective plus any coordinated adjectives ("fresh and tasty")."""
    return [adj] + [c for c in adj.conjuncts if c.pos_ == "ADJ"]


def extract_pairs(doc) -> list[dict]:
    """All (noun, adjective, negated) pairs in a doc, before any aspect / stop-word filtering."""
    pairs = []

    def add(noun, adj, negated):
        # punctuation, emojis and numbers ("-", "3rd") are not opinions or aspects
        if not (adj.lemma_.isalpha() and noun.lemma_.isalpha()):
            return
        pairs.append({"noun": noun.lemma_.lower(), "adj": adj.lemma_.lower(), "negated": bool(negated)})

    for tok in doc:
        if tok.pos_ != "ADJ":
            continue

        # amod: "sour bread", "not fresh bread", "no fresh veggies"
        if tok.dep_ == "amod" and tok.head.pos_ in ("NOUN", "PROPN"):
            noun = tok.head
            noun_neg = any(_is_neg(c) for c in noun.children if c.i < noun.i)
            for adj in _with_conj_adjs(tok):
                add(noun, adj, noun_neg or any(_is_neg(c) for c in adj.children))

        # acomp + nsubj: "the bread was sour", "staff were not polite"
        elif tok.dep_ == "acomp":
            verb = tok.head
            verb_neg = any(_is_neg(c) for c in verb.children)
            subjects = [c for c in verb.children if c.dep_ in ("nsubj", "nsubjpass")]
            subjects += [n for s in subjects for n in s.conjuncts]
            for subj in subjects:
                if subj.pos_ not in ("NOUN", "PROPN"):
                    continue
                for adj in _with_conj_adjs(tok):
                    add(subj, adj, verb_neg or any(_is_neg(c) for c in adj.children))

    return pairs


def _polarity(adj: str, negated: bool, rating: float) -> str:
    if adj in config.POSITIVE_ADJECTIVES:
        return "negative" if negated else "positive"
    if adj in config.NEGATIVE_ADJECTIVES:
        return "positive" if negated else "negative"
    if rating >= config.POSITIVE_MIN_RATING:
        return "positive"
    if rating <= config.NEGATIVE_MAX_RATING:
        return "negative"
    return "neutral"


def extract_candidates(reviews: pd.DataFrame, nlp=None) -> pd.DataFrame:
    """Every adjective-noun pair found, with `drop_reason` (None = kept). Useful for auditing."""
    nlp = nlp or load_nlp()
    text_reviews = reviews[reviews["text"].str.split().str.len() >= config.MIN_WORDS_FOR_PHRASES]

    n_process = 1
    if len(text_reviews) >= config.SPACY_MULTIPROCESS_MIN_ROWS:
        n_process = max(1, (os.cpu_count() or 1) - config.N_PROCESS_RESERVED_CORES)

    texts = text_reviews["text"].str.replace(MISSING_SPACE, r"\1\2 ", regex=True)
    docs = nlp.pipe(texts, batch_size=config.SPACY_BATCH_SIZE, n_process=n_process)
    rows = []
    meta = zip(text_reviews["review_id"], text_reviews["store_id"], text_reviews["rating"])
    for (review_id, store_id, rating), doc in tqdm(
        zip(meta, docs), total=len(text_reviews), desc="spaCy", disable=True if len(text_reviews) < 1000 else None
    ):
        for p in extract_pairs(doc):
            aspect = config.NOUN_TO_ASPECT.get(p["noun"])
            if p["adj"] in config.STOP_ADJECTIVES:
                reason = "stop_adjective"
            elif p["noun"] in config.GENERIC_NOUNS:
                reason = "generic_noun"
            elif aspect is None:
                reason = "noun_not_in_aspect_list"
            else:
                reason = None
            opinion = f"not {p['adj']}" if p["negated"] else p["adj"]
            rows.append({
                "review_id": review_id, "store_id": store_id, "aspect": aspect, "noun": p["noun"],
                "opinion": opinion, "phrase": f"{opinion} {p['noun']}",
                "polarity": _polarity(p["adj"], p["negated"], rating), "drop_reason": reason,
            })

    return pd.DataFrame(rows, columns=PHRASE_COLS[:3] + ["noun"] + PHRASE_COLS[3:] + ["drop_reason"])


def build_phrases(reviews: pd.DataFrame, nlp=None, verbose=True) -> pd.DataFrame:
    cand = extract_candidates(reviews, nlp)
    kept = cand[cand["drop_reason"].isna()]
    # count each phrase once per review, not once per mention
    phrases = kept.drop_duplicates(["review_id", "phrase"])[PHRASE_COLS].reset_index(drop=True)

    if verbose:
        n_words = reviews["text"].str.split().str.len()
        n_text = int((n_words >= config.MIN_WORDS_FOR_PHRASES).sum())
        n_skipped = int(((n_words > 0) & (n_words < config.MIN_WORDS_FOR_PHRASES)).sum())
        n_hit = phrases["review_id"].nunique()
        print("\n=== phrases: sanity summary ===")
        print(f"text reviews parsed     : {n_text:,}  (skipped {n_skipped:,} with < {config.MIN_WORDS_FOR_PHRASES} words)")
        print(f"adj-noun pairs found    : {len(cand):,}")
        for reason, n in cand["drop_reason"].value_counts().items():
            print(f"  dropped {reason:<24}: {n:,}")
        print(f"phrases kept            : {len(phrases):,}  (after once-per-review dedupe)")
        print(f"reviews with >=1 phrase : {n_hit:,}  ({n_hit / max(n_text, 1):.1%})")
        print(f"polarity split          : {phrases['polarity'].value_counts().to_dict()}")
        top_dropped = cand.loc[cand["drop_reason"] == "noun_not_in_aspect_list", "noun"].value_counts().head(10)
        print(f"top nouns outside aspect list: {top_dropped.to_dict()}")

    return phrases


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--sample", type=int, default=200, help="number of random text reviews to run on")
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    reviews = load_reviews(verbose=False)
    sample = reviews[reviews["text"] != ""].sample(args.sample, random_state=args.seed)
    phrases = build_phrases(sample)

    print("\n--- top 20 phrases ---")
    top = (
        phrases.groupby(["phrase", "aspect"])
        .agg(count=("review_id", "nunique"), polarity=("polarity", lambda s: s.mode().iat[0]))
        .sort_values("count", ascending=False).head(20).reset_index()
    )
    print(top.to_string(index=False))
