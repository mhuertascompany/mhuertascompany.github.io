#!/usr/bin/env python3
"""Refresh CV bibliometrics from the NASA ADS search API."""

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, quote
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
QUERY = 'author:"Huertas-Company, M" database:astronomy property:refereed'
SOURCE_URL = 'https://ui.adsabs.harvard.edu/search/q=' + quote(QUERY, safe='')


def fetch_papers(token):
    papers = []
    total = None
    while total is None or len(papers) < total:
        query = urlencode({'q': QUERY, 'fl': 'bibcode,citation_count',
                           'rows': 2000, 'start': len(papers), 'sort': 'bibcode asc'})
        request = Request('https://api.adsabs.harvard.edu/v1/search/query?' + query,
                          headers={'Authorization': 'Bearer ' + token,
                                   'Accept': 'application/json'})
        for attempt in range(3):
            try:
                with urlopen(request, timeout=45) as response:
                    payload = json.load(response)
                break
            except HTTPError as error:
                if error.code not in (429, 500, 502, 503, 504) or attempt == 2:
                    raise RuntimeError(f'NASA ADS request failed (HTTP {error.code})') from None
                time.sleep(5 * (attempt + 1))
            except (URLError, TimeoutError):
                if attempt == 2:
                    raise RuntimeError('NASA ADS could not be reached') from None
                time.sleep(5 * (attempt + 1))
        result = payload['response']
        if type(result['numFound']) is not int or result['numFound'] <= 0:
            raise ValueError('ADS returned no papers; retaining the previous statistics')
        if total is not None and result['numFound'] != total:
            raise ValueError('ADS results changed during pagination; retry later')
        total = result['numFound']
        if not result['docs']:
            raise ValueError('Incomplete ADS result; retaining the previous statistics')
        papers.extend(result['docs'])
    if len(papers) != total:
        raise ValueError('ADS result count does not match the retrieved papers')
    return papers


def calculate_metrics(papers):
    if not papers:
        raise ValueError('Cannot calculate metrics for an empty result')
    ids = [p['bibcode'] for p in papers]
    if len(set(ids)) != len(ids):
        raise ValueError('Duplicate ADS records')
    citations = [p.get('citation_count', 0) for p in papers]
    if any(type(c) is not int or c < 0 for c in citations):
        raise ValueError('Invalid ADS citation count')
    citations.sort(reverse=True)
    return {
        'papers': len(papers),
        'citations': sum(citations),
        'h_index': sum(c >= rank for rank, c in enumerate(citations, 1)),
        'i100': sum(c >= 100 for c in citations),
        'query': QUERY,
        'source_url': SOURCE_URL,
        'updated': datetime.now(timezone.utc).date().isoformat(),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--if-configured', action='store_true')
    parser.add_argument('--output', type=Path, default=ROOT / '_data/ads_metrics.json')
    args = parser.parse_args()
    token = os.environ.get('ADS_API_TOKEN', '').strip()
    if not token:
        if args.if_configured:
            print('::warning::ADS_API_TOKEN is not configured; ADS statistics were not refreshed.')
            return
        raise SystemExit('Set ADS_API_TOKEN before requesting NASA ADS statistics.')
    metrics = calculate_metrics(fetch_papers(token))
    content = json.dumps(metrics, ensure_ascii=False, indent=2) + '\n'
    if not args.output.exists() or args.output.read_text() != content:
        temporary = args.output.with_suffix('.json.tmp')
        temporary.write_text(content)
        temporary.replace(args.output)
    print(f"Updated ADS metrics: {metrics['papers']} refereed papers, "
          f"{metrics['citations']} citations, h-index {metrics['h_index']}.")


if __name__ == '__main__':
    main()
