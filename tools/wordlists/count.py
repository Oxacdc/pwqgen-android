#!/usr/bin/env python3
"""Count word frequencies in plain-text corpora.

Usage: count.py LANG FILE...  >  counts.tsv

Output, most frequent first:
    ascii_word <TAB> count <TAB> lowercase_ratio <TAB> most_common_spelling <TAB> files

- Words are folded to ASCII (é -> e, ñ -> n, œ -> oe; German ä -> ae,
  ß -> ss; Russian is transliterated, see TRANSLIT) and lowercased; only
  3-6 letter results are kept.
- files is the number of input files containing the word: character names
  are frequent but appear in few books.
- lowercase_ratio is the share of non-sentence-initial occurrences written in
  lowercase; proper nouns score low.  German capitalizes every noun, so
  there a capitalized word right after an article or determiner ("der
  Baum", "im Haus") counts as lowercase: common nouns often follow one,
  names of people and places almost never.
- French elisions are handled: "jusqu'", "aujourd'hui" fragments are dropped.
- Project Gutenberg header/footer boilerplate is skipped, and so are whole
  files where another language is common (bilingual editions, textbooks):
  more than 0.2% of their words are function words of another language
  (2% for Latin).
"""
import collections
import re
import sys
import unicodedata

WORD = re.compile(r"[^\W\d_]+", re.U)
APOS = "'’ʼ`"
SENTENCE_END = set(".!?:;«»\"“”—–-(")


MARKERS = {
    "en": {"the", "and", "of", "with", "that", "which", "was", "his"},
    "fr": {"les", "des", "une", "dans", "pour", "avec", "sont"},
    "es": {"los", "las", "del", "por", "para", "pero", "muy"},
    "la": {"atque", "enim", "autem", "quod", "esse", "sunt", "sed"},
    "de": {"und", "der", "nicht", "ist", "sich", "auch", "das"},
}
# Languages whose marker words are looked for in each language's files.
COMPARE = {"de": ("en", "fr", "es", "la"), "ru": ("en", "fr", "de")}
DEFAULT_COMPARE = ("en", "fr", "es", "la")
# Marker words that are also common words of the language itself.
OWN_WORDS = {"de": {"was", "des"}}
# Latin words are checked against a dictionary anyway (latin.py), so Latin
# books with English notes or introductions are still useful.
FOREIGN_MAX = {"la": 0.02}


def foreign(lang, text):
    """Largest share of another language's marker words, and that language."""
    words = collections.Counter(WORD.findall(text.lower()))
    n = sum(words.values()) or 1
    return max((sum(words[w] for w in m - OWN_WORDS.get(lang, set())) / n, other)
               for other, m in MARKERS.items()
               if other != lang and other in COMPARE.get(lang, DEFAULT_COMPARE))


# Russian: BGN/PCGN-style romanization without diacritics (ё -> e).
TRANSLIT = dict(zip("абвгдеёжзийклмнопрстуфхцчшщъыьэюя", (
    "a b v g d e e zh z i y k l m n o p r s t u f kh ts ch sh shch _ y _ e yu ya"
).split()))
TRANSLIT["ъ"] = TRANSLIT["ь"] = ""
DETERMINERS = set("""der die das den dem des ein eine einen einem einer eines kein
keine keinen keinem keiner mein meine meinen meinem meiner dein deine deinen
deinem deiner sein seine seinen seinem seiner ihr ihre ihren ihrem ihrer unser
unsere unseren unserem unserer euer eure jeder jede jedes jeden jedem dieser
diese dieses diesen diesem jener jene jenes jenen jenem welcher welche welches
manche manchen alle allen viele vielen einige einigen im am zum zur vom beim
ins ans aufs""".split())
GERMAN = (("ä", "ae"), ("ö", "oe"), ("ü", "ue"), ("Ä", "Ae"), ("Ö", "Oe"), ("Ü", "Ue"), ("ß", "ss"))


def fold(w):
    if lang == "ru":   # Russian words only: Latin-script words are foreign
        w = w.lower()
        return "".join(TRANSLIT[c] for c in w) if all(c in TRANSLIT for c in w) else ""
    for a, b in (("œ", "oe"), ("æ", "ae"), ("Œ", "Oe"), ("Æ", "Ae")) + (GERMAN if lang == "de" else ()):
        w = w.replace(a, b)
    return "".join(c for c in unicodedata.normalize("NFD", w) if not unicodedata.combining(c))


def body(path):
    text = open(path, encoding="utf-8", errors="replace").read()
    start = re.search(r"\*\*\* ?START OF (THE|THIS) PROJECT GUTENBERG.*\n", text)
    end = re.search(r"\*\*\* ?END OF (THE|THIS) PROJECT GUTENBERG", text)
    if start:
        text = text[start.end():end.start() if end else None]
    return text


total = collections.Counter()
lower = collections.Counter()
upper = collections.Counter()
spell = collections.defaultdict(collections.Counter)
files = collections.Counter()

lang = sys.argv[1]
used = skipped = 0
for path in sys.argv[2:]:
    text = body(path)
    share, other = foreign(lang, text)
    if share > FOREIGN_MAX.get(lang, 0.002):
        skipped += 1
        print(f"skip {path}: {other} {share:.2%}", file=sys.stderr)
        continue
    used += 1
    in_file = set()
    for line in text.splitlines():
        prev_end = 0
        initial = True
        prev_word = ""
        for m in WORD.finditer(line):
            t = m.group()
            gap = line[prev_end:m.start()]
            prev_end = m.end()
            before = line[m.start() - 1] if m.start() else ""
            after = line[m.end()] if m.end() < len(line) else ""
            if any(c in SENTENCE_END for c in gap):
                initial = True
            sentence_initial, initial = initial, False
            after_determiner = prev_word in DETERMINERS and not any(c in SENTENCE_END for c in gap)
            prev_word = t.lower()
            # Elided fragment ("jusqu'", "aujourd'") or what follows an
            # elision we do not want ("aujourd'hui" -> "hui").
            if after in APOS:
                continue
            if before in APOS and line[max(0, m.start() - 8):m.start() - 1].lower().endswith("aujourd"):
                continue
            f = fold(t).lower()
            if not (3 <= len(f) <= 6 and f.isascii() and f.isalpha()):
                continue
            total[f] += 1
            in_file.add(f)
            spell[f][t.lower()] += 1
            if sentence_initial:
                continue
            if t.islower() or (lang == "de" and after_determiner):
                lower[f] += 1
            elif t[0].isupper():
                upper[f] += 1
    files.update(in_file)

print(f"{used} files used, {skipped} skipped", file=sys.stderr)
for f, n in total.most_common():
    if n < 3:
        break
    seen = lower[f] + upper[f]
    ratio = lower[f] / seen if seen else 0.0
    print(f, n, f"{ratio:.3f}", spell[f].most_common(1)[0][0], files[f], sep="\t")
