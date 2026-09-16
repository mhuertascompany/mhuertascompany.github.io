#!/usr/bin/env python3
"""Append missing arXiv papers without rewriting curated BibTeX entries."""

import argparse
from datetime import date
from pathlib import Path
import re
import subprocess
import time
import unicodedata
from urllib.parse import urlencode
import xml.etree.ElementTree as ET

import bibtexparser
from bibtexparser.bparser import BibTexParser
from bibtexparser.latexenc import latex_to_unicode

ROOT = Path(__file__).resolve().parents[1]
NS = {"a": "http://www.w3.org/2005/Atom", "arxiv": "http://arxiv.org/schemas/atom",
      "os": "http://a9.com/-/spec/opensearch/1.1/"}
PAGE_SIZE = 500


def normalized(value):
    value = unicodedata.normalize("NFKD", latex_to_unicode(value)).casefold()
    return "".join(c for c in value if c.isalnum())


def arxiv_id(value):
    match = re.search(r"\d{4}\.\d{4,5}|[a-z-]+/\d{7}", value, re.I)
    return match.group(0).lower() if match else ""


def read_bib(text):
    parser = BibTexParser(common_strings=True)
    parser.ignore_nonstandard_types = False
    # ADS journal macros are intentionally retained by this site's bibliography.
    parser.interpolate_strings = False
    return bibtexparser.loads(text, parser=parser)


def parse_feed(data):
    root = ET.fromstring(data)
    if root.tag != "{" + NS["a"] + "}feed":
        raise ValueError("arXiv returned something other than an Atom feed")
    entries = root.findall("a:entry", NS)
    total = int(root.findtext("os:totalResults", namespaces=NS) or 0)
    if any("/api/errors" in e.findtext("a:id", "", NS) for e in entries):
        raise ValueError("arXiv returned an API error")
    if not entries or not total:
        raise ValueError("Empty arXiv response; leaving bibliography unchanged")
    return entries, total


def fetch_entries():
    entries = []
    while True:
        query = urlencode({
            "search_query": 'au:"Huertas-Company"',
            "start": len(entries), "max_results": PAGE_SIZE,
            "sortBy": "submittedDate", "sortOrder": "descending",
        }, safe=":")
        for attempt in range(3):
            try:
                response = subprocess.run(
                    ["curl", "--fail", "--silent", "--show-error", "--location",
                     "--max-time", "60", "https://arxiv.org/api/query?" + query],
                    check=True, capture_output=True,
                )
                page, total = parse_feed(response.stdout)
                break
            except (OSError, ValueError, ET.ParseError, subprocess.CalledProcessError):
                if attempt == 2:
                    raise
                time.sleep(5 * (attempt + 1))
        entries.extend(page)
        if len(entries) >= total:
            return entries
        time.sleep(3)


def bib_text(value):
    # Preserve arXiv's LaTeX, including math, while escaping bare BibTeX specials.
    value = " ".join(value.split())
    return re.sub(r"(?<!\\)([&%#])", r"\\\1", value)


def new_records(entries, existing, since):
    ids, dois, titles = set(), set(), set()
    for entry in existing.entries:
        for field in ("eprint", "arxiv", "url", "html", "doi"):
            identifier = arxiv_id(str(entry.get(field, "")))
            if identifier:
                ids.add(identifier)
        if entry.get("doi"):
            dois.add(str(entry["doi"]).lower())
        titles.add(normalized(str(entry.get("title", ""))))
    records = []
    for entry in entries:
        authors = [a.findtext("a:name", "", NS) for a in entry.findall("a:author", NS)]
        if not any(normalized(a) in ("marchuertascompany", "mhuertascompany", "huertascompanymarc", "huertascompanym") for a in authors):
            continue
        published = entry.findtext("a:published", "", NS)[:10]
        if not since <= published <= date.today().isoformat():
            continue
        identifier = arxiv_id(entry.findtext("a:id", "", NS))
        title = entry.findtext("a:title", "", NS)
        doi = entry.findtext("arxiv:doi", "", NS).strip()
        if not identifier or not title:
            raise ValueError("Incomplete arXiv paper metadata")
        if identifier in ids or (doi and doi.lower() in dois) or normalized(title) in titles:
            continue
        fields = {
            "author": " and ".join("{" + bib_text(a) + "}" if "collaboration" in a.lower() else bib_text(a) for a in authors),
            "title": "{" + bib_text(title) + "}",
            "journal": bib_text(entry.findtext("arxiv:journal_ref", "", NS) or "arXiv e-prints"),
            "year": published[:4],
            "month": published[5:7],
            "archivePrefix": "arXiv", "eprint": identifier, "arxiv": identifier,
            "html": "https://arxiv.org/abs/" + identifier,
            "bibtex_show": "true",
        }
        if doi:
            fields["doi"] = doi
        record = "@article{arxiv" + identifier.replace(".", "").replace("/", "") + ",\n"
        record += ",\n".join(f"  {key} = {{{value}}}" for key, value in fields.items()) + "\n}\n"
        records.append((published, record))
        ids.add(identifier)
        dois.add(doi.lower())
        titles.add(normalized(title))
    return [record for _, record in sorted(records, reverse=True)]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bibliography", type=Path, default=ROOT / "_bibliography/papers.bib")
    parser.add_argument("--since", default="2024-01-01", type=lambda s: date.fromisoformat(s).isoformat())
    parser.add_argument("--feed", type=Path, help="Use a complete, saved arXiv Atom feed (for offline verification)")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    original = args.bibliography.read_text()
    existing = read_bib(original)
    if not existing.entries:
        raise ValueError("Could not parse the existing bibliography")
    if args.feed:
        entries, total = parse_feed(args.feed.read_bytes())
        if len(entries) != total:
            raise ValueError("Saved feed is incomplete")
    else:
        entries = fetch_entries()
    records = new_records(entries, existing, args.since)
    updated = "\n".join(records) + "\n" + original if records else original
    parsed = read_bib(updated)
    if len(parsed.entries) != len(existing.entries) + len(records):
        raise ValueError("Generated bibliography failed validation")
    keys = [e["ID"] for e in parsed.entries]
    if len(keys) != len(set(keys)):
        raise ValueError("Duplicate BibTeX keys; leaving bibliography unchanged")
    if records and not args.dry_run:
        temporary = args.bibliography.with_suffix(".bib.tmp")
        temporary.write_text(updated)
        temporary.replace(args.bibliography)
    print(f'{"Would add" if args.dry_run else "Added"} {len(records)} papers; preserved {len(existing.entries)} existing entries.')


if __name__ == "__main__":
    main()
