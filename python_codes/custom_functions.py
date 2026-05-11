"""Reusable helpers for text sentiment analysis."""

from collections import Counter
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


def get_pipeline_device_id(device: str) -> int:
    """Translate a torch device name to the device id expected by HF pipeline."""
    if device == "cuda":
        return 0
    if device == "mps":
        return 0
    return -1


def normalize_label(label: str, label_map: dict[str, str] | None = None) -> str:
    """Normalize model labels to positive, neutral, or negative where possible."""
    mapping = label_map or DEFAULT_LABEL_MAP
    cleaned = str(label).lower()
    return mapping.get(cleaned, cleaned)


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


def _resolve_tokenizer(sentiment_pipeline, tokenizer=None, model_name: str | None = None):
    if tokenizer is not None:
        return tokenizer

    pipeline_tokenizer = getattr(sentiment_pipeline, "tokenizer", None)
    if pipeline_tokenizer is not None:
        return pipeline_tokenizer

    if model_name is not None:
        return AutoTokenizer.from_pretrained(model_name)

    raise ValueError("Pass a tokenizer or model_name so long text can be chunked.")


def analyze_long_text(
    text: str,
    sentiment_pipeline,
    tokenizer=None,
    model_name: str | None = None,
    label_map: dict[str, str] | None = None,
    max_tokens: int = 500,
    overlap: int = 50,
) -> tuple[str, float, bool]:
    """Analyze one text value, chunking and voting if it exceeds the token limit."""
    tokenizer = _resolve_tokenizer(sentiment_pipeline, tokenizer, model_name)
    tokens = tokenizer.encode(text, add_special_tokens=False)

    if len(tokens) <= max_tokens:
        result = sentiment_pipeline(text)[0]
        return normalize_label(result["label"], label_map), round(result["score"], 4), False

    chunks = []
    step = max_tokens - overlap
    for i in range(0, len(tokens), step):
        chunk_tokens = tokens[i : i + max_tokens]
        chunk_text = tokenizer.decode(chunk_tokens, skip_special_tokens=True)
        chunks.append(chunk_text)

    results = sentiment_pipeline(chunks)
    labels = [normalize_label(result["label"], label_map) for result in results]
    scores = [result["score"] for result in results]

    majority_label = Counter(labels).most_common(1)[0][0]
    avg_score = round(sum(scores) / len(scores), 4)

    return majority_label, avg_score, True


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
    chunked_col: str = "CHUNKED",
    clean_kwargs: dict | None = None,
) -> pd.DataFrame:
    """Batch-process text sentiment, chunking texts that exceed max_tokens."""
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
    print(f"Long texts (chunking + voting): {len(long_texts)}\n")

    if short_texts:
        results = []
        for i in tqdm(range(0, len(short_texts), batch_size), desc="Short texts"):
            batch = short_texts[i : i + batch_size]
            results.extend(sentiment_pipeline(batch))

        for idx, result in zip(short_indices, results):
            df.at[idx, sentiment_col] = normalize_label(result["label"], label_map)
            df.at[idx, score_col] = round(result["score"], 4)
            df.at[idx, chunked_col] = False

    if long_texts:
        for idx, text in tqdm(
            zip(long_indices, long_texts),
            total=len(long_texts),
            desc="Long texts",
        ):
            label, score, chunked = analyze_long_text(
                text,
                sentiment_pipeline=sentiment_pipeline,
                tokenizer=tokenizer,
                label_map=label_map,
                max_tokens=max_tokens,
                overlap=overlap,
            )
            df.at[idx, sentiment_col] = label
            df.at[idx, score_col] = score
            df.at[idx, chunked_col] = chunked

    print(f"\nDone. {len(long_texts)} text(s) used chunking + voting.")
    return df
