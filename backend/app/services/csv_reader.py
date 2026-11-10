"""Read real-world CSVs: odd encodings, ; or tab separators, European decimals,
currency and percent values, codes with leading zeros, and Excel's blank rows.

Everything is read as text first, then each column is converted only when every
value in it clearly fits, so nothing is silently mangled.
"""
from __future__ import annotations

import csv
import io
import re

import pandas as pd

# Placeholders that mean "missing", on top of pandas' defaults ("", "NA", "N/A",
# "NULL", "NaN", "null", ...). Without these, one "?" turns a number column into text.
MISSING_MARKERS = ["?", "-", "--", "n/a", "na", "none", "None", "NONE", "missing", "MISSING"]

_ENCODINGS = ("utf-8-sig", "cp1252", "latin-1")  # latin-1 never fails, so it's the last resort
_DELIMITERS = ",;\t|"

_CURRENCY = r"[$€£¥₹]"
# -$1,234.50  |  1234  |  83%  |  (12.00) accounting negatives are left as text
_NUMBER_DOT = re.compile(rf"^[-+]?{_CURRENCY}?\s?-?(\d{{1,3}}(,\d{{3}})+|\d+)?(\.\d+)?\s?%?$")
# European style: 1.234,50 € | 12,5
_NUMBER_COMMA = re.compile(rf"^[-+]?{_CURRENCY}?\s?-?(\d{{1,3}}(\.\d{{3}})+|\d+)?(,\d+)?\s?{_CURRENCY}?\s?%?$")
_LEADING_ZERO = re.compile(r"^0\d+$")


class CsvReadError(Exception):
    pass


def decode(content: bytes) -> str:
    for encoding in _ENCODINGS:
        try:
            return content.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise CsvReadError("Could not work out the file's text encoding.")


def detect_delimiter(text: str) -> str:
    sample = "\n".join(text.splitlines()[:50])
    try:
        return csv.Sniffer().sniff(sample, delimiters=_DELIMITERS).delimiter
    except csv.Error:
        # Fall back to whichever candidate appears most on the header line.
        header = text.splitlines()[0] if text else ""
        return max(_DELIMITERS, key=header.count)


def _to_number(values: pd.Series, decimal_comma: bool) -> pd.Series | None:
    """Convert a column of strings to numbers if *every* value is a number
    (allowing currency symbols, thousands separators and a trailing %)."""
    pattern = _NUMBER_COMMA if decimal_comma else _NUMBER_DOT
    present = values.dropna()
    if present.empty or not present.map(lambda s: bool(pattern.match(s)) and any(ch.isdigit() for ch in s)).all():
        return None
    # Codes like zip "01234" or ID "007" must stay text, or the leading zero is lost.
    if present.map(lambda s: bool(_LEADING_ZERO.match(s))).any():
        return None

    cleaned = values.str.replace(_CURRENCY, "", regex=True).str.replace("%", "", regex=False).str.replace(" ", "", regex=False)
    if decimal_comma:
        cleaned = cleaned.str.replace(".", "", regex=False).str.replace(",", ".", regex=False)
    else:
        cleaned = cleaned.str.replace(",", "", regex=False)
    numbers = pd.to_numeric(cleaned, errors="coerce")
    # Whole numbers stay integers when nothing is missing.
    if numbers.notna().all() and (numbers % 1 == 0).all():
        return numbers.astype("int64")
    return numbers


def read_csv(content: bytes) -> pd.DataFrame:
    text = decode(content)
    delimiter = detect_delimiter(text)

    df = pd.read_csv(
        io.StringIO(text),
        sep=delimiter,
        dtype=str,
        na_values=MISSING_MARKERS,
        skipinitialspace=True,
    )

    # Excel often leaves fully blank rows and columns at the edges.
    df = df.dropna(how="all")
    df = df.loc[:, ~(df.columns.str.startswith("Unnamed:") & df.isna().all())]
    df = df.reset_index(drop=True)

    # Semicolon files are almost always European: "12,5" means 12.5.
    decimal_comma = delimiter == ";"
    for col in df.columns:
        values = df[col].str.strip()
        number = _to_number(values, decimal_comma)
        df[col] = number if number is not None else values

    return df
