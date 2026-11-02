#!/bin/sh
# Rebuilds src/words/fr.txt, es.txt, de.txt, ru.txt and la.txt from their
# sources.  See README.md in this directory.  Needs curl and python3;
# downloads about 1.4 GB into $WORK (default: ./wordlists-work).
set -eu

here=$(cd "$(dirname "$0")" && pwd)
words=$here/../../src/words
work=${WORK:-$PWD/wordlists-work}
py="python3 -I"

CV=https://raw.githubusercontent.com/common-voice/common-voice/b24381ce7136f2524a1128cb605b49111f79dbea/server/data
WORDS=https://raw.githubusercontent.com/mk270/whitakers-words/b1b342c6df67dd47e103bac687d1765072f1931c
GUTENBERG=${GUTENBERG:-https://aleph.pglaf.org/cache/epub}

mkdir -p "$work/cv" "$work/pg/fr" "$work/pg/es" "$work/pg/de" "$work/pg/la" "$work/counts"

fetch() {  # url file
    [ -s "$2" ] || curl -sfL --retry 3 -m 600 -o "$2" "$1"
}

echo "Downloading Common Voice sentences (CC0)..."
for f in fr/wiki-1.fr.txt fr/wiki-2.fr.txt fr/sentence-collector.txt \
         es/wiki.es.txt es/sentence-collector.txt \
         de/wiki.de.txt de/wiki.de.rerun-2022-01.txt de/wiki.de.rerun-2022-08.txt \
         de/sentence-collector.txt de/europarl-v7-de.txt \
         ru/sentence-collector.txt ru/bakwc1.txt \
         en/wiki.en.rerun-2021-11.txt en/sentence-collector.txt; do
    fetch "$CV/$f" "$work/cv/$(echo "$f" | tr / _)"
done

echo "Downloading Whitaker's WORDS..."
fetch "$WORDS/DICTLINE.GEN" "$work/DICTLINE.GEN"
fetch "$WORDS/INFLECTS.LAT" "$work/INFLECTS.LAT"

echo "Downloading Project Gutenberg books (public domain)..."
for lang in fr es de la; do
    while read -r id; do
        fetch "$GUTENBERG/$id/pg$id.txt" "$work/pg/$lang/$id.txt" || echo "  missing: $id"
    done < "$here/gutenberg-$lang.txt"
done

echo "Downloading Russian Wikisource prose (public domain)..."
$py "$here/wikisource.py" fetch "$here/wikisource-ru.txt" "$work/wikisource-ru"

echo "Counting words..."
c=$work/counts
$py "$here/count.py" fr "$work"/cv/fr_*.txt > "$c/fr_modern.tsv"
$py "$here/count.py" es "$work"/cv/es_*.txt > "$c/es_modern.tsv"
$py "$here/count.py" en "$work"/cv/en_*.txt > "$c/en_modern.tsv"
$py "$here/count.py" de "$work"/cv/de_*.txt > "$c/de_modern.tsv"
$py "$here/count.py" ru "$work"/cv/ru_*.txt > "$c/ru_modern.tsv"
$py "$here/count.py" ru "$work"/wikisource-ru/*.txt > "$c/ru_books.tsv" 2>"$c/ru_books.log"
for lang in fr es de la; do
    $py "$here/count.py" $lang "$work"/pg/$lang/*.txt > "$c/${lang}_books.tsv" 2>"$c/${lang}_books.log"
done

echo "Selecting words..."
$py "$here/select.py" fr "$c/fr_modern.tsv" "$c/fr_books.tsv" "$here/fr.exclude" \
    "$c/en_modern.tsv" "$c/es_modern.tsv" "$c/la_books.tsv" > "$words/fr.txt"
$py "$here/select.py" es "$c/es_modern.tsv" "$c/es_books.tsv" "$here/es.exclude" \
    "$c/en_modern.tsv" "$c/fr_modern.tsv" "$c/la_books.tsv" > "$words/es.txt"
$py "$here/select.py" de "$c/de_modern.tsv" "$c/de_books.tsv" "$here/de.exclude" \
    "$c/en_modern.tsv" "$c/fr_modern.tsv" "$c/la_books.tsv" > "$words/de.txt"
$py "$here/select.py" ru "$c/ru_modern.tsv" "$c/ru_books.tsv" "$here/ru.exclude" > "$words/ru.txt"
$py "$here/latin.py" "$work/DICTLINE.GEN" "$work/INFLECTS.LAT" "$c/la_books.tsv" \
    "$here/la.exclude" "$c/en_modern.tsv" > "$words/la.txt"

echo "Done: $(cd "$words" && wc -l fr.txt es.txt de.txt ru.txt la.txt | tr '\n' ' ')"
