#!/usr/bin/env python3
"""Pick 4096 Latin words from William Whitaker's WORDS dictionary.

Usage: latin.py DICTLINE.GEN INFLECTS.LAT CORPUS_COUNTS.tsv EXCLUDE.txt ENGLISH_COUNTS.tsv  >  words.txt

1. Headwords: each dictionary entry is turned into its dictionary form
   (nominative singular for nouns, masculine nominative for adjectives,
   first person singular present for verbs).  Classical entries (age X, B
   or C) with Whitaker's frequency codes A-D are taken first, most frequent
   first, ties broken by frequency in public-domain Latin texts
   (CORPUS_COUNTS.tsv, from count.py).
2. Inflected forms: many common words have headwords longer than 6 letters
   (populus, dominus, imperium).  For these, the form found most often in
   the texts is used instead (populi, domino), provided Whitaker's
   inflection table (INFLECTS.LAT) confirms it is a regular form of the
   entry (with a non-empty ending), it occurs at least MIN_FORM_COUNT times
   and it is not more frequent in English (ENGLISH_COUNTS.tsv) than in the
   Latin texts.
3. Remaining slots, if any, are filled with rarer headwords (codes E, F).

Only one word per dictionary entry and per definition is kept, one
headword per stem and at most two words per stem, and spelling variants
are collapsed, so the list has no "bonus"/"bonum" pairs and no
"adfigo"/"affigo" or "coelum"/"caelum" duplicates.
"""
import collections
import re
import sys

N = 4096
COMMON = "ABCD"
RARE = "EF"
AGES = "XBC"
MIN_FORM_COUNT = 2

dictline_path, inflects_path, counts_path, exclude_path, english_path = sys.argv[1:6]

corpus = collections.Counter()
for line in open(counts_path, encoding="utf-8"):
    w, n, *_ = line.split("\t")
    corpus[w] = int(n)

english_counts = collections.Counter()
for line in open(english_path, encoding="utf-8"):
    w, n, *_ = line.split("\t")
    english_counts[w] = int(n)
corpus_total = sum(corpus.values())
english_total = sum(english_counts.values()) or 1


def english(word):
    """True if the word is more frequent in English than in the Latin texts
    (English notes and introductions in the Latin books: "circle", "office")."""
    return english_counts[word] / english_total > corpus[word] / corpus_total


exclude = set()
for line in open(exclude_path, encoding="utf-8"):
    exclude.update(line.split("#", 1)[0].split())


def acceptable(word):
    return (3 <= len(word) <= 6 and word.isascii() and word.isalpha()
            and "k" not in word and word not in exclude)


# --- Inflection table: (POS, declension, variant) -> [(stem number, ending)]
inflections = collections.defaultdict(list)
for line in open(inflects_path, encoding="latin-1"):
    line = line.split("--", 1)[0].split()
    if len(line) < 6 or line[0] not in ("N", "ADJ", "V", "VPAR"):
        continue
    age, freq = line[-2], line[-1]
    if age not in AGES or freq not in "AB":
        continue
    if line[-3].isdigit():          # zero-length ending
        stem_no, ending = int(line[-4]), ""
    else:
        stem_no, ending = int(line[-5]), line[-3]
    pos = "V" if line[0] == "VPAR" else line[0]
    inflections[(pos, line[1], line[2])].append((stem_no, ending))


def forms(pos, key, stems):
    which, variant = key
    for k in ((pos, which, variant), (pos, which, "0")):
        for stem_no, ending in inflections.get(k, ()):
            if ending and stem_no <= len(stems) and stems[stem_no - 1] not in ("", "zzz"):
                yield stems[stem_no - 1] + ending


# --- Dictionary entries
NOUN = {("1", "1"): "a", ("2", "1"): "us", ("2", "2"): "um", ("2", "3"): "",
        ("4", "1"): "us", ("4", "2"): "u", ("5", "1"): "es"}
ADJ = {("1", "1"): "us", ("1", "2"): "", ("3", "1"): "", ("3", "2"): "is", ("3", "3"): ""}
VERB = {("1", "1"): "o", ("2", "1"): "eo", ("3", "1"): "o", ("3", "4"): "io",
        ("5", "1"): "um", ("6", "1"): "o"}   # also compounds of sum and eo
TAIL = re.compile(r"^(\S+)\s*(.*?)\s+([A-Z]) ([A-Z]) ([A-Z]) ([A-Z]) ([A-Z]) (.*)$")


def headword_ending(pos, rest, key):
    if pos == "N":
        if key == ("2", "4"):       # stem ends in -i: filius, ingenium
            return "us" if rest.split()[2:3] == ["M"] else "um"
        return "" if key[0] == "3" else NOUN.get(key)
    if pos == "ADJ":
        return ADJ.get(key)
    if pos == "V":
        end = VERB.get(key)
        if end is not None and "DEP" in rest.split():
            end = end[:-1] + "or"   # deponent: hortor
        return end
    if pos in ("ADV", "PREP", "CONJ", "INTERJ"):
        return ""
    return None


entries = []   # (freq index, headword, stem, definition, [inflected forms])
for line in open(dictline_path, encoding="latin-1"):
    stems = [line[i * 19:(i + 1) * 19].strip() for i in range(4)]
    m = TAIL.match(line[76:].rstrip("\n"))
    stem = stems[0]
    if not m or not stem.isalpha() or not stem.islower() or stem == "zzz":
        continue
    pos, rest, age, _area, _geo, freq, _source, meaning = m.groups()
    if age not in AGES or freq not in COMMON + RARE:
        continue
    key = tuple(rest.split()[:2])
    end = headword_ending(pos, rest, key)
    if end is None:
        continue
    head = (stem + end).replace("iio", "io")   # stems already ending in -i
    infl = sorted(set(forms(pos, key, stems))) if pos in ("N", "ADJ", "V") else []
    entries.append(((COMMON + RARE).index(freq), head, stem, (pos, meaning.strip()), infl))

chosen = []
seen_words, seen_meanings = set(), set()
seen_stems = collections.Counter()   # words per stem
STEM_MAX = 2   # e.g. "dico" plus one inflected form from another entry


ASSIMILATION = [("adl", "all"), ("ads", "ass"), ("adq", "atq"), ("adt", "att"),
                ("adp", "app"), ("adc", "acc"), ("adf", "aff"), ("adg", "agg"),
                ("adr", "arr"), ("adn", "ann"), ("conp", "comp"), ("conl", "coll"),
                ("conr", "corr"), ("inp", "imp"), ("inm", "imm"), ("inl", "ill"),
                ("inr", "irr"), ("aps", "abs"), ("supt", "subt")]


def spelling_key(word):
    """Collapses spelling variants (adlego/allego, coelum/caelum, tophus/tofus)."""
    for a, b in ASSIMILATION:
        if word.startswith(a):
            word = b + word[len(a):]
    for a, b in (("oe", "ae"), ("ph", "f")):
        word = word.replace(a, b)
    return word


def take(word, stem, meaning, same_stem_ok=False):
    key = spelling_key(word)
    if key in seen_words or meaning in seen_meanings:
        return False
    if seen_stems[stem] >= (STEM_MAX if same_stem_ok else 1):
        return False
    seen_words.add(key)
    seen_stems[stem] += 1
    seen_meanings.add(meaning)
    chosen.append(word)
    return True


def by_rank(e):
    return (e[0], -corpus[e[1]], e[1])


# 1. Common headwords.
for f, head, stem, meaning, _ in sorted(entries, key=by_rank):
    if f < len(COMMON) and acceptable(head) and len(chosen) < N:
        take(head, stem, meaning)

phase1 = len(chosen)

# 2. Most frequent regular forms of common entries not represented yet.
candidates = []
for f, head, stem, meaning, infl in entries:
    if f >= len(COMMON) or meaning in seen_meanings:
        continue
    for w in infl:
        if acceptable(w) and corpus[w] >= MIN_FORM_COUNT and not english(w):
            candidates.append((-corpus[w], w, stem, meaning))
for _, w, stem, meaning in sorted(candidates):
    if len(chosen) < N:
        take(w, stem, meaning, same_stem_ok=True)

phase2 = len(chosen) - phase1

# 3. Rarer headwords.
for f, head, stem, meaning, _ in sorted(entries, key=by_rank):
    if f >= len(COMMON) and acceptable(head) and len(chosen) < N:
        take(head, stem, meaning)

if len(chosen) < N:
    sys.exit(f"only {len(chosen)} words found")
print(f"la: {phase1} headwords, {phase2} inflected forms, "
      f"{len(chosen) - phase1 - phase2} rare headwords", file=sys.stderr)
for w in chosen:
    print(w)
