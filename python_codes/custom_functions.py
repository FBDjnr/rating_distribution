"""Reusable helpers for text sentiment analysis."""

import platform
import subprocess

import pandas as pd
import torch
from tqdm import tqdm
from transformers import AutoTokenizer


DEFAULT_LABEL_MAP = {
    "positive": "positive",
    "negative": "negative",
    "neutral": "neutral",
    "label_0": "negative",
    "label_1": "neutral",
    "label_2": "positive",
}

SENTIMENT_PROBABILITY_LABELS = ("negative", "neutral", "positive")

SENTIMENT_COMPOUND_VALUES = {
    "negative": -1.0,
    "neutral": 0.0,
    "positive": 1.0,
}

TRANSFORMER_SENTIMENT_OUTPUTS = [
    ("TWRB_SENT", "TWRB_SCORE", "TWRB_neg", "TWRB_neu", "TWRB_pos", "TWRB_CS"),
    ("SRB_SENT", "SRB_SCORE", "SRB_neg", "SRB_neu", "SRB_pos", "SRB_CS"),
    ("RVRB_SENT", "RVRB_SCORE", "RVRB_neg", "RVRB_neu", "RVRB_pos", "RVRB_CS"),
]


# Device Detection
# Select the best available compute backend for PyTorch/Hugging Face inference.
def get_device() -> str:
    """Return the best available torch device name: mps, cuda, or cpu."""
    if torch.backends.mps.is_available():
        try:
            chip = subprocess.check_output(
                ["sysctl", "-n", "machdep.cpu.brand_string"],
                stderr=subprocess.DEVNULL,
            ).decode().strip()
        except Exception:
            chip = "Apple Silicon"
        print(f"Using Apple MPS ({chip})")
        return "mps"

    if torch.cuda.is_available():
        print(f"Using CUDA GPU: {torch.cuda.get_device_name(0)}")
        return "cuda"

    print(f"Using CPU ({platform.processor() or platform.machine()})")
    return "cpu"


# Pipeline Device Mapping
# Convert a torch backend name into the device id expected by transformers.pipeline.
def get_pipeline_device_id(device: str) -> int:
    """Translate a torch device name to the device id expected by HF pipeline."""
    if device == "cuda":
        return 0
    if device == "mps":
        return 0
    return -1


# Label Normalization
# Standardize model-specific labels into negative, neutral, or positive.
def normalize_label(label: str, label_map: dict[str, str] | None = None) -> str:
    """Normalize model labels to positive, neutral, or negative where possible."""
    mapping = label_map or DEFAULT_LABEL_MAP
    cleaned = str(label).lower()
    return mapping.get(cleaned, cleaned)


# Empty Sentiment Probabilities
# Initialize the three sentiment probability slots used in final outputs.
def empty_sentiment_probabilities() -> dict[str, float]:
    """Return zero-filled negative/neutral/positive probability slots."""
    return {label: 0.0 for label in SENTIMENT_PROBABILITY_LABELS}


# Compound Score From Probabilities
# Collapse negative, neutral, and positive probabilities into a signed score.
def compound_score_from_probabilities(probabilities: dict[str, float]) -> float:
    """Return a signed compound score from sentiment probabilities."""
    return round(
        sum(
            probabilities.get(label, 0.0) * value
            for label, value in SENTIMENT_COMPOUND_VALUES.items()
        ),
        4,
    )


# Run Pipeline With All Scores
# Ask a Hugging Face sentiment pipeline for all class probabilities when possible.
def _run_pipeline_all_scores(sentiment_pipeline, texts):
    """Run a HF sentiment pipeline and request all class scores when supported."""
    try:
        return sentiment_pipeline(texts, top_k=None)
    except TypeError:
        try:
            return sentiment_pipeline(texts, return_all_scores=True)
        except TypeError:
            return sentiment_pipeline(texts)


# Single-Text Score Normalization
# Convert the many possible pipeline output shapes into one list of score records.
def _coerce_single_score_results(results) -> list[dict]:
    """Normalize pipeline output for one text into a list of score dictionaries."""
    if isinstance(results, dict):
        return [results]

    if not isinstance(results, list) or not results:
        return []

    if all(isinstance(result, dict) for result in results):
        return results

    if len(results) == 1 and isinstance(results[0], list):
        return _coerce_single_score_results(results[0])

    return []


# Batch Score Normalization
# Convert batched pipeline output into one list of score records per input text.
def _coerce_batch_score_results(results, expected_count: int) -> list[list[dict]]:
    """Normalize pipeline output for a text batch into per-text score lists."""
    if expected_count == 1:
        return [_coerce_single_score_results(results)]

    if not isinstance(results, list):
        return [_coerce_single_score_results(results)]

    if isinstance(results, list) and len(results) == expected_count:
        if all(isinstance(result, list) for result in results):
            return [_coerce_single_score_results(result) for result in results]

        if all(isinstance(result, dict) for result in results):
            return [[result] for result in results]

    return [_coerce_single_score_results(result) for result in results]


# Sentiment Score Summary
# Summarize raw class scores into label, confidence, probabilities, and compound score.
def summarize_sentiment_scores(
    score_results: list[dict],
    label_map: dict[str, str] | None = None,
) -> tuple[object, object, dict[str, float], object]:
    """Summarize class-level model scores into label, top score, probabilities, and compound score."""
    probabilities = empty_sentiment_probabilities()
    normalized_results = []

    for result in score_results:
        label = normalize_label(result.get("label"), label_map)
        score = float(result.get("score", 0.0))
        normalized_results.append((label, score))
        if label in probabilities:
            probabilities[label] += score

    probabilities = {
        label: round(probability, 4)
        for label, probability in probabilities.items()
    }

    known_results = [
        (label, score)
        for label, score in normalized_results
        if label in probabilities
    ]
    if not known_results:
        return pd.NA, pd.NA, probabilities, pd.NA

    sentiment, score = max(known_results, key=lambda item: item[1])
    compound_score = compound_score_from_probabilities(probabilities)

    return sentiment, round(score, 4), probabilities, compound_score


# Add Sentiment Score Columns
# Backfill probability and compound columns from existing sentiment labels and scores.
def add_sentiment_score_columns(
    df: pd.DataFrame,
    sentiment_col: str,
    score_col: str,
    neg_col: str,
    neu_col: str,
    pos_col: str,
    compound_col: str,
) -> pd.DataFrame:
    """Create probability and compound columns from existing top-label scores."""
    df = df.copy()
    sentiment_values = (
        df[sentiment_col]
        .astype("string")
        .str.strip()
        .str.lower()
    )
    scores = pd.to_numeric(df[score_col], errors="coerce")

    df[neg_col] = 0.0
    df[neu_col] = 0.0
    df[pos_col] = 0.0

    df.loc[sentiment_values == "negative", neg_col] = scores
    df.loc[sentiment_values == "neutral", neu_col] = scores
    df.loc[sentiment_values == "positive", pos_col] = scores

    invalid_rows = scores.isna() | sentiment_values.isna()
    df.loc[invalid_rows, [neg_col, neu_col, pos_col]] = pd.NA

    df[compound_col] = (
        pd.to_numeric(df[pos_col], errors="coerce")
        - pd.to_numeric(df[neg_col], errors="coerce")
    ).round(4)

    return df


# Text Cleaning
# Remove missing, too-short, or non-alphanumeric text before sentiment inference.
def clean_text(text, min_chars: int = 3, require_alnum: bool = True):
    """Return cleaned text, or None for missing/too-short/non-text values."""
    if pd.isna(text):
        return None

    text = str(text).strip()
    if len(text) < min_chars:
        return None

    if require_alnum and not any(char.isalnum() for char in text):
        return None

    return text


# Tokenizer Resolution
# Reuse the pipeline tokenizer or load one by model name for chunking long text.
def _resolve_tokenizer(sentiment_pipeline, tokenizer=None, model_name: str | None = None):
    if tokenizer is not None:
        return tokenizer

    pipeline_tokenizer = getattr(sentiment_pipeline, "tokenizer", None)
    if pipeline_tokenizer is not None:
        return pipeline_tokenizer

    if model_name is not None:
        return AutoTokenizer.from_pretrained(model_name)

    raise ValueError("Pass a tokenizer or model_name so long text can be chunked.")


# Long-Text Sentiment
# Analyze a single text and preserve the original label/score/chunked return shape.
def analyze_long_text(
    text: str,
    sentiment_pipeline,
    tokenizer=None,
    model_name: str | None = None,
    label_map: dict[str, str] | None = None,
    max_tokens: int = 500,
    overlap: int = 50,
) -> tuple[str, float, bool]:
    """Analyze one text value, chunking and averaging if it exceeds the token limit."""
    label, score, _, _, chunked = analyze_long_text_with_probabilities(
        text,
        sentiment_pipeline=sentiment_pipeline,
        tokenizer=tokenizer,
        model_name=model_name,
        label_map=label_map,
        max_tokens=max_tokens,
        overlap=overlap,
    )
    return label, score, chunked


# Long-Text Sentiment With Probabilities
# Analyze a single text and return label, score, probabilities, compound score, and chunk flag.
def analyze_long_text_with_probabilities(
    text: str,
    sentiment_pipeline,
    tokenizer=None,
    model_name: str | None = None,
    label_map: dict[str, str] | None = None,
    max_tokens: int = 500,
    overlap: int = 50,
) -> tuple[object, object, dict[str, float], object, bool]:
    """Analyze one text value and return label, score, probabilities, compound score, and chunk flag."""
    tokenizer = _resolve_tokenizer(sentiment_pipeline, tokenizer, model_name)
    tokens = tokenizer.encode(text, add_special_tokens=False)

    if len(tokens) <= max_tokens:
        results = _coerce_single_score_results(
            _run_pipeline_all_scores(sentiment_pipeline, text)
        )
        label, score, probabilities, compound_score = summarize_sentiment_scores(
            results,
            label_map=label_map,
        )
        return label, score, probabilities, compound_score, False

    chunks = []
    step = max_tokens - overlap
    for i in range(0, len(tokens), step):
        chunk_tokens = tokens[i : i + max_tokens]
        chunk_text = tokenizer.decode(chunk_tokens, skip_special_tokens=True)
        chunks.append(chunk_text)

    chunk_results = _coerce_batch_score_results(
        _run_pipeline_all_scores(sentiment_pipeline, chunks),
        expected_count=len(chunks),
    )
    chunk_summaries = [
        summarize_sentiment_scores(results, label_map=label_map)
        for results in chunk_results
    ]
    chunk_probabilities = [summary[2] for summary in chunk_summaries]

    probabilities = empty_sentiment_probabilities()
    for label in probabilities:
        probabilities[label] = round(
            sum(chunk_probs[label] for chunk_probs in chunk_probabilities)
            / len(chunk_probabilities),
            4,
        )

    sentiment = max(probabilities, key=probabilities.get)
    score = probabilities[sentiment]
    compound_score = compound_score_from_probabilities(probabilities)

    return sentiment, score, probabilities, compound_score, True


# Batch Sentiment Analysis
# Process a dataframe of reviews and write sentiment, probabilities, compound score, and chunk flags.
def analyze_sentiment(
    df: pd.DataFrame,
    sentiment_pipeline,
    text_col: str = "text",
    tokenizer=None,
    model_name: str | None = None,
    label_map: dict[str, str] | None = None,
    batch_size: int = 32,
    max_tokens: int = 500,
    overlap: int = 50,
    sentiment_col: str = "SENTIMENT",
    score_col: str = "SENTIMENT_SCORE",
    neg_col: str = "SENTIMENT_neg",
    neu_col: str = "SENTIMENT_neu",
    pos_col: str = "SENTIMENT_pos",
    compound_col: str = "SENTIMENT_CS",
    chunked_col: str = "CHUNKED",
    clean_kwargs: dict | None = None,
) -> pd.DataFrame:
    """Batch-process sentiment and return label, confidence, probabilities, and compound score."""
    df = df.copy()
    if text_col not in df.columns:
        raise KeyError(f"Column '{text_col}' was not found in the DataFrame.")

    if overlap >= max_tokens:
        raise ValueError("overlap must be smaller than max_tokens.")

    clean_kwargs = clean_kwargs or {}
    tokenizer = _resolve_tokenizer(sentiment_pipeline, tokenizer, model_name)
    cleaned = [clean_text(text, **clean_kwargs) for text in df[text_col].tolist()]

    valid_pairs = [
        (idx, text)
        for idx, text in zip(df.index, cleaned)
        if text is not None
    ]
    valid_indices = [idx for idx, _ in valid_pairs]
    valid_texts = [text for _, text in valid_pairs]
    skipped = len(cleaned) - len(valid_texts)

    print(f"Analyzing {len(valid_texts)} texts (skipping {skipped} empty/invalid)...\n")

    df[sentiment_col] = pd.NA
    df[score_col] = pd.NA
    df[neg_col] = pd.NA
    df[neu_col] = pd.NA
    df[pos_col] = pd.NA
    df[compound_col] = pd.NA
    df[chunked_col] = False

    short_indices, short_texts = [], []
    long_indices, long_texts = [], []

    for idx, text in zip(valid_indices, valid_texts):
        tokens = tokenizer.encode(text, add_special_tokens=False)
        if len(tokens) <= max_tokens:
            short_indices.append(idx)
            short_texts.append(text)
        else:
            long_indices.append(idx)
            long_texts.append(text)

    print(f"Short texts (direct batch): {len(short_texts)}")
    print(f"Long texts (chunking + averaging): {len(long_texts)}\n")

    if short_texts:
        results = []
        for i in tqdm(range(0, len(short_texts), batch_size), desc="Short texts"):
            batch = short_texts[i : i + batch_size]
            batch_results = _coerce_batch_score_results(
                _run_pipeline_all_scores(sentiment_pipeline, batch),
                expected_count=len(batch),
            )
            results.extend(batch_results)

        for idx, result in zip(short_indices, results):
            label, score, probabilities, compound_score = summarize_sentiment_scores(
                result,
                label_map=label_map,
            )
            df.at[idx, sentiment_col] = label
            df.at[idx, score_col] = score
            df.at[idx, neg_col] = probabilities["negative"]
            df.at[idx, neu_col] = probabilities["neutral"]
            df.at[idx, pos_col] = probabilities["positive"]
            df.at[idx, compound_col] = compound_score
            df.at[idx, chunked_col] = False

    if long_texts:
        for idx, text in tqdm(
            zip(long_indices, long_texts),
            total=len(long_texts),
            desc="Long texts",
        ):
            label, score, probabilities, compound_score, chunked = (
                analyze_long_text_with_probabilities(
                    text,
                    sentiment_pipeline=sentiment_pipeline,
                    tokenizer=tokenizer,
                    label_map=label_map,
                    max_tokens=max_tokens,
                    overlap=overlap,
                )
            )
            df.at[idx, sentiment_col] = label
            df.at[idx, score_col] = score
            df.at[idx, neg_col] = probabilities["negative"]
            df.at[idx, neu_col] = probabilities["neutral"]
            df.at[idx, pos_col] = probabilities["positive"]
            df.at[idx, compound_col] = compound_score
            df.at[idx, chunked_col] = chunked

    print(f"\nDone. {len(long_texts)} text(s) used chunking + averaging.")
    return df


# Prior Mean
# Compute each product's prior mean rating before the current review row.
def _prior_mean(group):
    cs = group["RSR"].astype(float).cumsum().shift(1)
    cc = pd.Series(range(len(group)), index=group.index, dtype=float)
    return cs / cc
