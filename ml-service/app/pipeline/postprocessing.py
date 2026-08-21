"""
Stage 10 – OCR Error Correction

Lightweight, conservative correction using SymSpell.

Rules (from spec):
  ✔ Remove duplicate spaces
  ✔ Remove OCR garbage characters
  ✔ Repair common OCR character confusions
  ✔ Merge accidentally split words (heuristic)
  ✔ SymSpell correction only for low-confidence words
  ✗ Never modify:
       • numbers / dates / times
       • ALL-CAPS acronyms
       • technical abbreviations (Dr., Mr., etc.)
       • compound words (snake_case, kebab-case)
       • URLs / emails
  ✗ Do NOT rewrite sentences
"""

import re
import os
import inspect
from typing import List, Optional, Tuple

from symspellpy import SymSpell, Verbosity

# ── Patterns that should NEVER be spell-corrected ────────────────────────────
_PRESERVE_RE = [
    re.compile(r'^\d+([.,:/\-]\d+)*$'),         # numbers, dates, times
    re.compile(r'^[A-Z]{2,}$'),                   # ALL-CAPS acronyms (NASA, UK)
    re.compile(r'^[A-Za-z]{1,4}\.$'),             # abbreviations ending in dot
    re.compile(r'^[A-Za-z]+[_\-][A-Za-z]+'),     # snake_case / kebab-case
    re.compile(r'^https?://'),                     # URLs
    re.compile(r'^[A-Za-z0-9._%+\-]+@'),          # email addresses
    re.compile(r'^\W+$'),                          # punctuation-only tokens
]

# ── OCR character confusion fixes (conservative — only very obvious ones) ────
_OCR_CHAR_FIXES = [
    (re.compile(r'(?<=[0-9])O(?=[0-9])'), '0'),   # digit O between digits → 0
    (re.compile(r'(?<=[0-9])l(?=[0-9])'), '1'),   # lowercase l between digits → 1
]

_sym_spell: Optional[SymSpell] = None


# ── Initialisation ────────────────────────────────────────────────────────────

def _init_sym_spell() -> Optional[SymSpell]:
    global _sym_spell
    if _sym_spell is not None:
        return _sym_spell

    _sym_spell = SymSpell(max_dictionary_edit_distance=2, prefix_length=7)
    try:
        import symspellpy
        pkg_dir    = os.path.dirname(inspect.getfile(symspellpy))
        dict_path  = os.path.join(pkg_dir, "frequency_dictionary_en_82_765.txt")
        if os.path.exists(dict_path):
            _sym_spell.load_dictionary(dict_path, term_index=0, count_index=1)
            print(f"SymSpell loaded english dictionary from {dict_path}")
        else:
            print(f"SymSpell dictionary not found at {dict_path}. Spellcheck bypassed.")
            _sym_spell = None
    except Exception as exc:
        print(f"SymSpell init error: {exc}. Spellcheck bypassed.")
        _sym_spell = None
    return _sym_spell


# ── Public API ────────────────────────────────────────────────────────────────

def correct_text(
    text: str,
    word_confidences: Optional[List[float]] = None,
    word_conf_threshold: float = 0.85,
) -> str:
    """
    Stage 10 OCR error correction.

    Args:
        text:                 Raw OCR output string.
        word_confidences:     Per-word confidence scores (same length as words).
                              If provided, only words below word_conf_threshold
                              are spell-corrected.
        word_conf_threshold:  Skip correction for words with confidence ≥ this.

    Returns:
        Corrected text string.
    """
    if not text.strip():
        return text

    # ── 1. OCR character fixes (very conservative) ────────────────────────────
    for pattern, replacement in _OCR_CHAR_FIXES:
        text = pattern.sub(replacement, text)

    # ── 2. Remove OCR garbage ─────────────────────────────────────────────────
    text = _remove_garbage(text)

    # ── 3. Collapse multiple spaces ───────────────────────────────────────────
    text = re.sub(r' {2,}', ' ', text).strip()

    # ── 4. Word-level SymSpell correction ────────────────────────────────────
    sym = _init_sym_spell()
    if sym is None:
        return text

    words          = text.split()
    corrected: List[str] = []

    for i, word in enumerate(words):
        # Skip high-confidence words if per-word confidence is available
        if word_confidences is not None and i < len(word_confidences):
            if word_confidences[i] >= word_conf_threshold:
                corrected.append(word)
                continue

        left_punc, clean, right_punc = _split_punctuation(word)

        if not clean or _should_preserve(clean):
            corrected.append(word)
            continue

        fixed = _sym_correct(sym, clean)
        corrected.append(left_punc + fixed + right_punc)

    result = " ".join(corrected)

    # ── 5. Merge accidentally split words (e.g. "be cause" → "because") ──────
    result = _merge_split_words(result, sym)

    return result


def correct_spelling(text: str) -> str:
    """Backward-compatible alias (used by main.py legacy path)."""
    return correct_text(text, word_confidences=None)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _remove_garbage(text: str) -> str:
    """Remove common OCR artifacts that are clearly not real text."""
    # Sequences of 3+ non-alphanumeric chars (excluding allowed punctuation)
    text = re.sub(r'[^\w\s.,!?;:\'"()\-]{3,}', ' ', text)
    # Isolated pipe/backslash/slash characters
    text = re.sub(r'(?<!\S)[|\\/_]{1,2}(?!\S)', ' ', text)
    return text


def _should_preserve(word: str) -> bool:
    """Return True if the word must not be spell-corrected."""
    return any(p.match(word) for p in _PRESERVE_RE)


def _split_punctuation(word: str) -> Tuple[str, str, str]:
    """Split a word token into (leading_punct, core_word, trailing_punct)."""
    left = ""
    i    = 0
    while i < len(word) and not word[i].isalnum():
        left += word[i];  i += 1

    right = ""
    j     = len(word) - 1
    while j >= i and not word[j].isalnum():
        right = word[j] + right;  j -= 1

    return left, word[i:j + 1], right


def _sym_correct(sym: SymSpell, clean: str) -> str:
    """Apply SymSpell to a clean (no punctuation) word, preserving case."""
    # Skip very short or mixed-case words (likely proper nouns)
    if len(clean) <= 2:
        return clean
    if clean[0].isupper() and any(c.isupper() for c in clean[1:]):
        return clean

    suggestions = sym.lookup(clean.lower(), Verbosity.CLOSEST, max_edit_distance=2)
    if not suggestions:
        return clean

    corrected = suggestions[0].term
    if clean.isupper():
        return corrected.upper()
    if clean[0].isupper():
        return corrected.capitalize()
    return corrected


def _merge_split_words(text: str, sym: SymSpell) -> str:
    """
    Heuristic: if two consecutive short tokens merged form a valid dictionary word
    and neither alone is in the dictionary, merge them.
    (e.g. "be cause" → "because", "hand writ ing" → keep as-is)
    """
    words  = text.split()
    result: List[str] = []
    i = 0
    while i < len(words):
        if i < len(words) - 1:
            w1 = words[i]
            w2 = words[i + 1]
            # Only try merging short alpha-only tokens
            if (len(w1) <= 4 and len(w2) <= 4 and
                    w1.isalpha() and w2.isalpha()):
                merged = w1 + w2
                merged_sugg = sym.lookup(merged.lower(), Verbosity.TOP, max_edit_distance=0)
                w1_sugg     = sym.lookup(w1.lower(),     Verbosity.TOP, max_edit_distance=0)
                w2_sugg     = sym.lookup(w2.lower(),     Verbosity.TOP, max_edit_distance=0)
                if merged_sugg and not (w1_sugg and w2_sugg):
                    result.append(merged)
                    i += 2
                    continue
        result.append(words[i])
        i += 1
    return " ".join(result)
