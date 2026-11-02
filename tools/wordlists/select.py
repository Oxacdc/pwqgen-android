#!/usr/bin/env python3
"""Pick the 4096 words of a list from two count files (see count.py).

Usage: select.py LANG MODERN.tsv LITERARY.tsv EXCLUDE.txt [FOREIGN.tsv...]  >  words.txt

LANG is fr, es, de or ru.

A word must be common in both corpora: words are ranked by the geometric
mean of their per-million frequencies, so encyclopedic jargon and modern
loanwords (absent from old books) and archaic words (absent from modern
text) both drop out.  Then:
- proper nouns are skipped: mostly capitalized in mid-sentence (in German,
  capitalized and not after an article, see count.py);
- German and Russian words must appear in at least 3% of the literary
  files, which drops character names;
- words much more frequent (4x) in another language (FOREIGN.tsv: English, Latin, the
  other Romance language) than in this one are skipped, which drops
  quotations, titles and loanwords ("and", "for", "von", "della");
- words listed in EXCLUDE.txt are skipped, with their plural/gender
  variants (function words, vulgar or offensive words, foreign words,
  abbreviations);
- a word whose plural/gender variant is already chosen is skipped, so the
  list does not waste entries on "grand"/"grande"/"grands".
"""
import math
import sys

N = 4096
MIN_COUNT = {"fr": 5, "es": 3, "de": 3, "ru": 3}  # occurrences in each corpus
# The Russian modern corpus is small: there a word only needs to be in the
# literary one, and SMOOTH is added to its modern count (so words absent
# from modern text rank lower instead of being dropped).
SMOOTH = {"ru": 1}
MIN_LOWER = {"de": 0.2}  # share of lowercase mid-sentence occurrences
MIN_LOWER_DEFAULT = 0.85
MIN_SPREAD = {"de": 0.005, "ru": 0.005}  # share of literary files containing the word
FOREIGN_FACTOR = {"de": 20}  # skip words this many times more frequent abroad
FOREIGN_FACTOR_DEFAULT = 4   # (German shares many words with English and French)

lang, modern_path, literary_path, exclude_path = sys.argv[1:5]
foreign_paths = sys.argv[5:]

SUFFIXES = {
    "fr": ("s", "x", "e", "es"),
    "es": ("s", "es", "a", "as", "o", "os"),
    "de": ("e", "en", "er", "es", "em", "n", "s", "r"),
    # Russian noun, adjective and verb endings, transliterated.
    "ru": ("a", "y", "u", "e", "i", "o", "ya", "yu", "oy", "om", "am", "ami", "akh",
           "ov", "ey", "em", "yy", "iy", "aya", "yaya", "oe", "ee", "ye", "ie", "ogo",
           "ego", "omu", "emu", "ym", "im", "uyu", "yuyu", "ykh", "ikh", "ymi", "imi",
           "t", "l", "la", "lo", "li", "et", "it", "ut", "at", "yat", "yut"),
}[lang]
REGROW = {"fr": ("e",), "es": ("o", "a"), "de": ("e",), "ru": ()}[lang]


def load(path):
    rows = {}
    total = 0
    for line in open(path, encoding="utf-8"):
        w, n, ratio, _, files = (line.rstrip("\n").split("\t") + ["0"])[:5]
        rows[w] = (int(n), float(ratio), int(files))
        total += int(n)
    return rows, total


def load_exclude(path):
    words = set()
    for line in open(path, encoding="utf-8"):
        line = line.split("#", 1)[0]
        words.update(line.split())
    return words


modern, modern_total = load(modern_path)
literary, literary_total = load(literary_path)
exclude = load_exclude(exclude_path)
foreign = [load(p) for p in foreign_paths]
literary_files = max((r[2] for r in literary.values()), default=0)


scored = []
smooth = SMOOTH.get(lang, 0)
for w, (n2, r2, files) in literary.items():
    n1, r1, _ = modern.get(w, (0, 1.0, 0))
    if (n1 < MIN_COUNT[lang] and not smooth) or n2 < MIN_COUNT[lang]:
        continue
    if files < MIN_SPREAD.get(lang, 0) * literary_files:
        continue
    if (r1 * n1 + r2 * n2) / (n1 + n2) < MIN_LOWER.get(lang, MIN_LOWER_DEFAULT):
        continue
    score = math.sqrt((n1 + smooth) / modern_total * n2 / literary_total) * 1e6
    if any(w in rows and rows[w][0] / total * 1e6 > FOREIGN_FACTOR.get(lang, FOREIGN_FACTOR_DEFAULT) * score for rows, total in foreign):
        continue
    scored.append((score, w))
scored.sort(key=lambda x: (-x[0], x[1]))


def stems(w):
    """The word and what is left after removing a plural/gender ending."""
    out = {w}
    for s in SUFFIXES:
        if w.endswith(s) and len(w) - len(s) >= 3:
            out.add(w[: -len(s)])
    return out


def family(w):
    """Spellings that count as the same word for the plural/gender rule."""
    st = stems(w)
    return st | {stem + e for stem in st for e in REGROW}


# Russian has many inflected forms: exclude whole families ("devka" also
# excludes "devki", "devke"...).
if lang == "ru":
    exclude = set().union(*(stems(x) for x in exclude))

chosen = []
taken = set()
for score, w in scored:
    f = family(w)
    if stems(w) & exclude:  # "culs" goes with "cul"
        continue
    if f & taken:
        continue
    taken |= f
    chosen.append(w)
    if len(chosen) == N:
        break

if len(chosen) < N:
    sys.exit(f"only {len(chosen)} words found")
print(f"{lang}: last word {chosen[-1]!r}, score {score:.2f} per million", file=sys.stderr)
for w in chosen:
    print(w)
