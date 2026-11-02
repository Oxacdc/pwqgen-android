# French, Spanish, German, Russian and Latin word lists

`src/words/fr.txt`, `es.txt`, `de.txt`, `ru.txt` and `la.txt` are generated
by `build.sh` from
sources that are in the public domain or impose no conditions, so the lists
are released under the app's 0BSD license like everything else.

Each list follows passwdqc's rules for its English list, so all languages
give exactly the same entropy (12 bits per word, plus 1 bit for the case of
the first letter and 4 per separator):

- exactly 4096 words;
- 3 to 6 letters, ASCII only (accents removed: é → e, ñ → n, œ → oe;
  German ä → ae, ß → ss; Russian transliterated, see below), so
  passphrases can be typed on any keyboard;
- no two words equal when the case is ignored.

## Sources

| Source | Used for | Terms |
|---|---|---|
| [Mozilla Common Voice](https://github.com/common-voice/common-voice) sentence collections (`server/data/{fr,es,de,ru,en}`, commit `b24381c`) | modern word frequencies; English counts to detect foreign words | CC0 1.0 |
| [Project Gutenberg](https://www.gutenberg.org/) books listed in `gutenberg-{fr,es,de,la}.txt` | literary word frequencies | public domain texts |
| [Russian Wikisource](https://ru.wikisource.org/) prose, revisions listed in `wikisource-ru.txt` (pages in "Русская проза" marked PD-old-70, modern spelling) | Russian literary word frequencies (Project Gutenberg has only 5 Russian books) | public domain texts (authors dead for more than 70 years); typing in a public-domain text creates no new rights |
| William Whitaker's [WORDS](https://github.com/mk270/whitakers-words) (`DICTLINE.GEN`, `INFLECTS.LAT`, commit `b1b342c`) | Latin vocabulary, frequency codes and inflections | "Permission is hereby freely given for any and all use of program and data." |

Only counts and dictionary data are used: no text from these sources ends
up in the app, only the selected words.

## Method

**French and Spanish** (`count.py`, `select.py`):

1. Count word frequencies in a modern corpus (Common Voice) and a literary
   one (Gutenberg). Books with more than 0.2% foreign function words
   (bilingual editions, textbooks) are skipped.
2. Rank words by the geometric mean of the two frequencies, so a word must
   be common in both: encyclopedic jargon and modern anglicisms (absent
   from old books) drop out, and so do archaic words.
3. Drop proper nouns (mostly capitalized in mid-sentence), words at least
   4 times more frequent in English, Latin or the other Romance language,
   and the words in `fr.exclude` / `es.exclude` with their variants
   (function words, vulgar or offensive words, foreign words, abbreviations).
4. Keep one word per plural/gender family ("grand" but not "grande" or
   "grands"), then take the first 4096.

**German** (same scripts): German capitalizes every noun, so a capitalized
word right after an article or determiner ("der Baum", "im Haus") counts as
lowercase; names of people and places rarely follow one. A word must also
appear in at least 0.5% of the books (drops character names), and words are
only dropped as foreign when 20 times more frequent in English, French or
Latin (German shares many words with them: "Name", "Plan", "Moment").

**Russian** (same scripts): words are transliterated with a BGN/PCGN-style
scheme without diacritics (ж zh, х kh, ц ts, ч ch, ш sh, щ shch, ы y, й y,
ю yu, я ya, ё → e, ъ and ь dropped). Only words written in Cyrillic are
counted. The Common Voice Russian collection is small, so a word only needs
to be in Wikisource; its modern count, plus one, still weighs in the
ranking. Many forms of one word (дом, дома, домой) are listed, but one per
family is kept, and excluded words are excluded with all their forms.

**Latin** (`latin.py`):

1. Headwords (nominative, first person singular present...) of classical
   entries with Whitaker's frequency codes A-D, ranked by that code and by
   frequency in the Latin Gutenberg books. One headword per stem, one word
   per definition (Whitaker lists spelling variants such as
   "caelum"/"coelum" as separate entries).
2. Many common words have headwords longer than 6 letters (populus,
   dominus). The list is completed with their forms most frequent in the
   books (populi, domino), each checked against Whitaker's inflection
   table, at most two words per stem.

Project Gutenberg occasionally updates its files (Wikisource texts are
pinned by revision), so a rebuild can differ
slightly from the committed lists; the committed lists are the reference.

## Rebuilding

```sh
./tools/wordlists/build.sh        # WORK=/some/dir to choose the download folder
cargo test                        # checks the format of every list
```
