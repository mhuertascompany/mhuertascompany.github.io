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

## CV bibliometrics (NASA ADS)

The deploy workflow also runs `bin/update_ads_metrics.py` on every non-PR
deployment, including the monthly schedule and manual runs. It queries all
refereed astronomy records matching `author:"Huertas-Company, M"`, paginates
through the complete result, and calculates paper count, total citations,
h-index, and the number of papers with at least 100 citations. All four metrics
refer to the same refereed-paper set and include self-citations. These values
are calculated from ADS citation counts, not from the site's arXiv bibliography.

The snapshot in `_data/ads_metrics.json` includes the source query and retrieval
date. It is rendered in the online CV, committed after a successful build, and
preserved on API errors. A failed API request stops that deployment; no partial
or zero-valued replacement is published. If the secret is absent, the workflow
warns and leaves the last snapshot unchanged; no statistics are shown until
the first successful fetch.

One-time setup:

1. Sign in at https://ui.adsabs.harvard.edu/user/settings/token and copy your API token.
2. Go to https://github.com/mhuertascompany/mhuertascompany.github.io/settings/secrets/actions/new.
3. Set the secret name to `ADS_API_TOKEN`, paste the token as its value, and save.
4. Run **Actions → Deploy site → Run workflow** to populate the initial metrics.

The token is supplied through the environment and is never written to the site
or printed in logs. The downloadable PDF CV remains a separately maintained
document; automatic metrics update the online CV only.

To run locally (Python 3 and `curl` are required):

```sh
python3 -m pip install -r bin/publications-requirements.txt
python3 bin/update_publications.py --dry-run
python3 bin/update_publications.py
python3 -m unittest discover -s bin -p 'test_publications.py'
```

`--feed path/to/feed.xml` uses a saved, complete arXiv API response for offline
verification. `--bibliography` can target a temporary copy for testing.
