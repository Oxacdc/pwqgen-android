#!/usr/bin/env python3
"""Public-domain Russian prose from Russian Wikisource.

Usage:
    wikisource.py list  >  wikisource-ru.txt     # pick pages (revision ids)
    wikisource.py fetch wikisource-ru.txt DIR    # download them as plain text

"list" takes the pages of "Категория:Русская проза" (Russian prose) and
its subcategories that
are also in "Категория:PD-old-70" (authors dead for more than 70 years,
public domain worldwide) and are written in modern spelling (texts in the
pre-1918 orthography, with ѣ or і, are left out).  It prints one revision
id per line, so "fetch" always downloads exactly the same text.

Typing in a public-domain text creates no new rights, so these texts are
public domain like Project Gutenberg's; only word counts are taken from
them.
"""
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request

API = "https://ru.wikisource.org/w/api.php"
CATEGORY = "Категория:Русская проза"
LICENSE = "Категория:PD-old-70"
OLD_SPELLING = re.compile("[ѣѢіІѳѲѵѴ]")
HEADERS = {"User-Agent": "pwqgen-android word list builder (https://github.com/Oxacdc/pwqgen-android)"}


def api(**params):
    params.update(format="json", formatversion="2")
    data = urllib.parse.urlencode(params).encode()   # POST: long title lists
    for attempt in range(5):
        try:
            req = urllib.request.Request(API, data=data, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=120) as r:
                return json.load(r)
        except OSError:
            time.sleep(5 * (attempt + 1))
    raise SystemExit(f"cannot fetch {params}")


def list_pages():
    """Pages of CATEGORY and of all its subcategories."""
    titles, todo, seen = [], [CATEGORY], {CATEGORY}
    while todo:
        cat, cont = todo.pop(), {}
        while True:
            r = api(action="query", list="categorymembers", cmtitle=cat,
                    cmnamespace="0|14", cmlimit=500, **cont)
            for m in r["query"]["categorymembers"]:
                if m["ns"] == 0:
                    titles.append(m["title"])
                elif m["title"] not in seen:
                    seen.add(m["title"])
                    todo.append(m["title"])
            if "continue" not in r:
                break
            cont = {"cmcontinue": r["continue"]["cmcontinue"]}
    return sorted(set(titles))


def pages(**which):
    r = api(action="query", prop="revisions|categories", rvprop="ids|content",
            rvslots="main", clcategories=LICENSE, cllimit="max", **which)
    for p in r["query"]["pages"]:
        if "revisions" in p:
            rev = p["revisions"][0]
            yield p, rev["revid"], rev["slots"]["main"]["content"]


def strip(wikitext):
    """Wikitext -> plain prose."""
    t = re.sub(r"<ref[^>]*/>|<ref.*?</ref>|<!--.*?-->", " ", wikitext, flags=re.S)
    while True:   # templates, innermost first
        t, n = re.subn(r"\{\{[^{}]*\}\}|\{\|[^{}]*?\|\}", " ", t)
        if not n:
            break
    t = re.sub(r"\[\[(?:[^|\]]*\|)?([^\]]*)\]\]", r"\1", t)   # [[link|text]]
    t = re.sub(r"\[https?://\S+ ?([^\]]*)\]", r"\1", t)
    t = re.sub(r"<[^>]+>|'{2,}|&nbsp;", " ", t)
    t = re.sub(r"^[=*#:;].*$", "", t, flags=re.M)              # headings, lists
    return t.replace("́", "")                             # stress marks


def main():
    if sys.argv[1] == "list":
        titles = list_pages()
        for i in range(0, len(titles), 50):
            for p, revid, text in pages(titles="|".join(titles[i:i + 50])):
                if p.get("categories") and not OLD_SPELLING.search(text):
                    print(revid)
            print(f"{min(i + 50, len(titles))}/{len(titles)}", file=sys.stderr)
    elif sys.argv[1] == "fetch":
        out = sys.argv[3]
        os.makedirs(out, exist_ok=True)
        revids = open(sys.argv[2]).read().split()
        for i in range(0, len(revids), 50):
            batch = [r for r in revids[i:i + 50] if not os.path.exists(f"{out}/{r}.txt")]
            if batch:
                for _, revid, text in pages(revids="|".join(batch)):
                    with open(f"{out}/{revid}.txt", "w", encoding="utf-8") as f:
                        f.write(strip(text))
    else:
        sys.exit(__doc__)


main()
