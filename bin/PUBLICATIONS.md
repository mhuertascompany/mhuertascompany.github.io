# Publication updates

The existing **Deploy site** GitHub Actions workflow refreshes publications on
the first of each month at **07:17 UTC**. It can also be run immediately from
**Actions → Deploy site → Run workflow** on the default branch.

The updater searches arXiv for Marc / M. Huertas-Company papers submitted since
January 2024, follows all result pages, and adds missing records to
`_bibliography/papers.bib`. It checks author names and deduplicates by arXiv ID,
DOI, and normalized title. Existing entries, journal metadata, and manually
selected papers are preserved verbatim. New entries include arXiv links and
journal references / DOIs when supplied by arXiv. Papers absent from arXiv and
later changes to existing entries still need manual curation.

After a successful site build, the workflow commits any bibliography changes
and deploys the site in the same run. This avoids relying on a bot commit to
trigger another workflow. It needs the existing `contents: write` permission;
no API key or additional secret is needed. Branch protection must permit the
workflow's bibliography commits. If fetching or validation fails, the job fails
without replacing the bibliography or deploying a partial update.

GitHub may disable scheduled workflows in public repositories after 60 days
without repository activity. If this happens, re-enable the workflow in Actions.
Scheduled execution times may be delayed by GitHub.

To run locally (Python 3 and `curl` are required):

```sh
python3 -m pip install -r bin/publications-requirements.txt
python3 bin/update_publications.py --dry-run
python3 bin/update_publications.py
python3 -m unittest discover -s bin -p 'test_publications.py'
```

`--feed path/to/feed.xml` uses a saved, complete arXiv API response for offline
verification. `--bibliography` can target a temporary copy for testing.
