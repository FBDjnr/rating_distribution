"""Brand extraction helpers for Amazon-style product titles."""

from __future__ import annotations

import re
import unicodedata
from urllib.parse import unquote

import pandas as pd


# Brand Alias Dictionary
# Keys are the canonical brand names to keep in the data; values are title aliases
# observed in the toaster data or common punctuation/casing variants.
BRAND_ALIASES = {
    "Aigostar": ["Aigostar"],
    "Amaste": ["Amaste"],
    "Amazon Basics": ["Amazon Basics", "AmazonBasic"],
    "Anfilank": ["Anfilank"],
    "Aunt Yuan": ["Aunt Yuan", "Aunt yuan"],
    "BELLA": ["BELLA", "Bella"],
    "BLACK+DECKER": ["BLACK+DECKER", "Black and Decker", "Black Decker"],
    "BUYDEEM": ["BUYDEEM"],
    "BergHOFF": ["BergHOFF", "Berghoff"],
    "Better Chef": ["Better Chef"],
    "Betty Crocker": ["Betty Crocker"],
    "Bob Ross": ["Bob Ross"],
    "Brentwood": ["Brentwood", "Brentwood Appliances"],
    "Breville": ["Breville"],
    "CE North America": ["CE North America"],
    "CUSIMAX": ["CUSIMAX"],
    "CUSINAID": ["CUSINAID"],
    "CYETUS": ["CYETUS"],
    "CROWNFUL": ["CROWNFUL"],
    "Cafe": ["Cafe", "Café"],
    "Chefman": ["Chefman"],
    "Clixane": ["Clixane"],
    "Cotomier": ["Cotomier"],
    "Courant": ["Courant"],
    "Crux": ["Crux"],
    "Cuisinart": ["Cuisinart"],
    "DASH": ["DASH", "Dash"],
    "DECAKILA": ["DECAKILA"],
    "Dear Morning": ["Dear Morning"],
    "Disney": ["Disney", "Mickey Mouse"],
    "Displav": ["Displav"],
    "Dominion": ["Dominion"],
    "Dualit": ["Dualit"],
    "DyBaxa": ["DyBaxa"],
    "Elite Gourmet": ["Elite Gourmet", "Elite Cuisine"],
    "Evening": ["Evening"],
    "Evoloop": ["Evoloop", "evoloop"],
    "Frigidaire": ["Frigidaire"],
    "GE": ["GE"],
    "Generic": ["Generic"],
    "Geek Chef": ["Geek Chef"],
    "George Foreman": ["George Foreman"],
    "Gevi": ["Gevi"],
    "Gohyo": ["Gohyo"],
    "Gourmia": ["Gourmia"],
    "Haden": ["Haden"],
    "Hamilton Beach": ["Hamilton Beach"],
    "Holstein Housewares": ["Holstein Housewares"],
    "Homeart": ["Homeart"],
    "Hommater": ["Hommater"],
    "Horloy": ["Horloy"],
    "JEWJIO": ["JEWJIO"],
    "KEEMO": ["KEEMO"],
    "KETIAN": ["KETIAN"],
    "KRUPS": ["KRUPS"],
    "Kate Spade": ["Kate Spade"],
    "Keenstone": ["Keenstone"],
    "Kenmore": ["Kenmore"],
    "Kikiwell": ["Kikiwell"],
    "KitchMix": ["KitchMix"],
    "KitchenAid": ["KitchenAid", "Kitchen Aid"],
    "Lainsten": ["Lainsten"],
    "LauKingdom": ["LauKingdom", "Lau Kingdom"],
    "Lenox": ["Lenox"],
    "LOFTER": ["LOFTER"],
    "MEISON": ["MEISON"],
    "Mecity": ["Mecity"],
    "Moss & Stone": ["Moss & Stone", "Moss and Stone"],
    "Mueller": ["Mueller"],
    "Ninja": ["Ninja"],
    "Nostalgia": ["Nostalgia"],
    "OIMIS": ["OIMIS"],
    "Oscar Mayer": ["Oscar Mayer"],
    "Oster": ["Oster"],
    "Ovente": ["Ovente"],
    "Pateyney": ["Pateyney"],
    "Peach Street": ["Peach Street"],
    "Proctor Silex": ["Proctor Silex"],
    "Pukomc": ["Pukomc"],
    "REDMOND": ["REDMOND", "Redmond"],
    "ROCKURWOK": ["ROCKURWOK"],
    "Rae Dunn": ["Rae Dunn"],
    "Revolution": ["Revolution", "Revolution InstaGLO", "Revolution InstaGLO R180B", "Revolution InstaGLO R270"],
    "Rocita": ["Rocita"],
    "Russell Hobbs": ["Russell Hobbs"],
    "SEEDEEM": ["SEEDEEM"],
    "Salton": ["Salton"],
    "Schloss": ["Schloss", "Schloß"],
    "Sencor": ["Sencor"],
    "Smeg": ["Smeg"],
    "Springhall": ["Springhall"],
    "Star Wars": ["Star Wars"],
    "Sunbeam": ["Sunbeam"],
    "The Pioneer Woman": ["The Pioneer Woman", "Pioneer Woman"],
    "TOBEFORT": ["TOBEFORT"],
    "TONZE": ["TONZE"],
    "TWINBIRD": ["TWINBIRD", "Twin bird", "Twinbird"],
    "Toastmaster": ["Toastmaster"],
    "Ultrean": ["Ultrean"],
    "Ulticore": ["Ulticore"],
    "Uncanny Brands": ["Uncanny Brands"],
    "VIMUKUN": ["VIMUKUN"],
    "Waring": ["Waring"],
    "West Bend": ["West Bend"],
    "Willz": ["Willz"],
    "YIOU": ["YIOU"],
    "YBSVO": ["YBSVO"],
    "Yabano": ["Yabano"],
    "ZWILLING": ["ZWILLING", "Zwilling"],
    "iFedio": ["iFedio"],
    "iSiLER": ["iSiLER", "Isiler"],
    "prepAmeal": ["prepAmeal", "PrepAmeal"],
    "whall": ["whall", "Whall"],
}

DEFAULT_BRAND_SOURCE_COLS = ("P_TITLE", "P_URL", "SELLER_LINK")


def normalize_brand_text(text) -> str:
    """Normalize title/alias text so matching is robust to case and punctuation."""
    if pd.isna(text):
        return ""

    text = unicodedata.normalize("NFKD", unquote(str(text)))
    text = "".join(char for char in text if not unicodedata.combining(char))
    text = text.lower()
    text = text.replace("&", " and ")
    text = text.replace("+", " plus ")
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _build_normalized_alias_lookup(brand_aliases: dict[str, list[str]]) -> list[tuple[str, str]]:
    """Create longest-first normalized alias pairs for deterministic matching."""
    alias_pairs = []
    for canonical_brand, aliases in brand_aliases.items():
        aliases_with_canonical = [canonical_brand, *aliases]
        for alias in aliases_with_canonical:
            normalized_alias = normalize_brand_text(alias)
            if normalized_alias:
                alias_pairs.append((normalized_alias, canonical_brand))

    return sorted(set(alias_pairs), key=lambda item: len(item[0]), reverse=True)


NORMALIZED_BRAND_ALIASES = _build_normalized_alias_lookup(BRAND_ALIASES)


def extract_brand(title, brand_aliases: dict[str, list[str]] | None = None):
    """Extract the first longest matching brand alias from a text field."""
    normalized_title = normalize_brand_text(title)
    if not normalized_title:
        return pd.NA

    alias_lookup = (
        NORMALIZED_BRAND_ALIASES
        if brand_aliases is None
        else _build_normalized_alias_lookup(brand_aliases)
    )

    for normalized_alias, canonical_brand in alias_lookup:
        if re.search(rf"\b{re.escape(normalized_alias)}\b", normalized_title):
            return canonical_brand

    return pd.NA


def extract_brand_from_sources(
    row: pd.Series,
    source_cols: list[str] | tuple[str, ...] = DEFAULT_BRAND_SOURCE_COLS,
    brand_aliases: dict[str, list[str]] | None = None,
):
    """Extract a brand from the first source column containing a known alias."""
    for source_col in source_cols:
        if source_col not in row.index:
            continue

        brand = extract_brand(row[source_col], brand_aliases=brand_aliases)
        if not pd.isna(brand):
            return brand

    return pd.NA


def add_brand_column(
    df: pd.DataFrame,
    title_col: str = "P_TITLE",
    brand_col: str = "BRAND",
    source_cols: list[str] | tuple[str, ...] | None = None,
    brand_aliases: dict[str, list[str]] | None = None,
) -> pd.DataFrame:
    """Return a dataframe copy with a brand column extracted from metadata fields."""
    source_cols = tuple(source_cols or (title_col,))
    available_source_cols = [col for col in source_cols if col in df.columns]
    if not available_source_cols:
        raise KeyError(
            "None of the requested brand source columns were found: "
            f"{', '.join(source_cols)}"
        )

    df = df.copy()
    df[brand_col] = df.apply(
        lambda row: extract_brand_from_sources(
            row,
            source_cols=available_source_cols,
            brand_aliases=brand_aliases,
        ),
        axis=1,
    )
    return df


def unmatched_brand_titles(
    df: pd.DataFrame,
    title_col: str = "P_TITLE",
    brand_col: str = "BRAND",
) -> pd.Series:
    """List unique titles that did not receive a brand match."""
    if brand_col not in df.columns:
        df = add_brand_column(
            df,
            title_col=title_col,
            brand_col=brand_col,
            source_cols=DEFAULT_BRAND_SOURCE_COLS,
        )

    return (
        df.loc[df[brand_col].isna(), title_col]
        .dropna()
        .drop_duplicates()
        .sort_values()
    )
