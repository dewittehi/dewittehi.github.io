#!/usr/bin/env python3
"""
update_publications.py
Fetches the 5 most recent PubMed publications for JJ Sikkens,
generates a short plain-English snippet for each using Claude,
and writes the result to publications.json.

Required environment variable:
  ANTHROPIC_API_KEY  — your Anthropic API key (stored as a GitHub secret)

Run locally:
  pip install requests anthropic
  ANTHROPIC_API_KEY=sk-ant-... python update_publications.py

Run via GitHub Actions: see .github/workflows/update-publications.yml
"""

import json
import os
import sys
import time
import datetime
import requests
import anthropic

# ── Config ────────────────────────────────────────────────────────────────────
PUBMED_AUTHOR    = "Sikkens JJ"
PUBMED_MAX       = 5
OUTPUT_FILE      = "publications.json"
ANTHROPIC_MODEL  = "claude-haiku-4-5-20251001"   # fast & cheap for snippets
SNIPPET_MAX_TOKENS = 180

PUBMED_ESEARCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
PUBMED_EFETCH  = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
PUBMED_ESUM    = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"

# ── Helpers ───────────────────────────────────────────────────────────────────

def search_pubmed(author: str, max_results: int) -> list[str]:
    """Return the top N PubMed IDs for the given author, sorted by pub date."""
    params = {
        "db": "pubmed",
        "term": f"{author}[Author]",
        "sort": "pub date",
        "retmax": max_results,
        "retmode": "json",
    }
    r = requests.get(PUBMED_ESEARCH, params=params, timeout=15)
    r.raise_for_status()
    return r.json()["esearchresult"]["idlist"]


def fetch_summaries(pmids: list[str]) -> list[dict]:
    """Fetch eSummary records for a list of PMIDs."""
    params = {
        "db": "pubmed",
        "id": ",".join(pmids),
        "retmode": "json",
    }
    r = requests.get(PUBMED_ESUM, params=params, timeout=15)
    r.raise_for_status()
    result = r.json()["result"]
    return [result[pmid] for pmid in pmids if pmid in result]


def fetch_abstracts(pmids: list[str]) -> dict[str, str]:
    """Fetch abstracts via eFetch (text/plain). Returns {pmid: abstract}."""
    params = {
        "db": "pubmed",
        "id": ",".join(pmids),
        "rettype": "abstract",
        "retmode": "text",
    }
    r = requests.get(PUBMED_EFETCH, params=params, timeout=20)
    r.raise_for_status()
    raw = r.text

    abstracts: dict[str, str] = {}
    # Split on "PMID: XXXXXXXX" markers to associate abstracts with PMIDs
    for pmid in pmids:
        marker = f"PMID: {pmid}"
        if marker in raw:
            block_start = raw.rfind("\n\n", 0, raw.index(marker))
            block_end   = raw.find("\n\n\n", raw.index(marker))
            block = raw[block_start:block_end if block_end != -1 else None].strip()
            # Find the "AB  -" line in the block
            ab_idx = block.find("\nAB  -")
            if ab_idx != -1:
                ab_text = block[ab_idx + 6:].split("\n\n")[0]
                # Flatten continuation lines
                ab_text = " ".join(
                    line.lstrip() for line in ab_text.splitlines()
                ).strip()
                abstracts[pmid] = ab_text
    return abstracts


def generate_snippet(client: anthropic.Anthropic, title: str, abstract: str) -> str:
    """Ask Claude for a short, accessible snippet about the paper."""
    prompt = (
        f"Write a 2-3 sentence plain-English summary of the following medical research paper "
        f"for a personal academic website. Be engaging and accessible to a non-specialist. "
        f"Do not start with 'This paper' or 'This study'. Write in third person.\n\n"
        f"Title: {title}\n\n"
        f"Abstract: {abstract}"
    )
    message = client.messages.create(
        model=ANTHROPIC_MODEL,
        max_tokens=SNIPPET_MAX_TOKENS,
        messages=[{"role": "user", "content": prompt}],
    )
    return message.content[0].text.strip()


def authors_string(summary: dict) -> str:
    """Build a short author string from the eSummary record."""
    authors = summary.get("authors", [])
    names = [a.get("name", "") for a in authors]
    if len(names) > 6:
        return ", ".join(names[:6]) + " et al."
    return ", ".join(names)


def doi_from_summary(summary: dict) -> str:
    """Extract DOI from articleids list."""
    for aid in summary.get("articleids", []):
        if aid.get("idtype") == "doi":
            return aid["value"]
    return ""


def pub_year(summary: dict) -> int:
    """Extract publication year."""
    date_str = summary.get("pubdate", "")
    try:
        return int(date_str.split(" ")[0])
    except (ValueError, IndexError):
        return 0


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("ERROR: ANTHROPIC_API_KEY environment variable not set.", file=sys.stderr)
        sys.exit(1)

    print(f"Searching PubMed for '{PUBMED_AUTHOR}' …")
    pmids = search_pubmed(PUBMED_AUTHOR, PUBMED_MAX)
    if not pmids:
        print("No results found.", file=sys.stderr)
        sys.exit(1)
    print(f"Found PMIDs: {pmids}")

    # Load existing publications to avoid re-generating snippets for known papers
    existing: dict[str, dict] = {}
    if os.path.exists(OUTPUT_FILE):
        with open(OUTPUT_FILE) as f:
            for pub in json.load(f):
                existing[pub["pmid"]] = pub

    print("Fetching eSummary records …")
    summaries = fetch_summaries(pmids)

    # Only fetch abstracts for papers without an existing snippet
    new_pmids = [p for p in pmids if p not in existing]
    abstracts: dict[str, str] = {}
    if new_pmids:
        print(f"Fetching abstracts for {len(new_pmids)} new paper(s) …")
        abstracts = fetch_abstracts(new_pmids)

    client = anthropic.Anthropic(api_key=api_key)
    publications = []
    today = datetime.date.today().isoformat()

    for summary in summaries:
        pmid = summary["uid"]
        title = summary.get("title", "").rstrip(".")
        journal = summary.get("fulljournalname", summary.get("source", ""))
        doi = doi_from_summary(summary)
        year = pub_year(summary)
        authors_str = authors_string(summary)

        if pmid in existing and existing[pmid].get("snippet"):
            # Reuse existing snippet
            print(f"Reusing snippet for PMID {pmid}")
            pub = existing[pmid]
            pub.update({
                "title": title,
                "journal": journal,
                "doi": doi,
                "year": year,
                "authors": authors_str,
                "fetched_date": today,
            })
        else:
            abstract = abstracts.get(pmid, "")
            if abstract:
                print(f"Generating snippet for PMID {pmid} …")
                snippet = generate_snippet(client, title, abstract)
                time.sleep(0.5)  # gentle rate limiting
            else:
                print(f"No abstract available for PMID {pmid}, skipping snippet.")
                snippet = ""

            pub = {
                "pmid": pmid,
                "doi": doi,
                "title": title,
                "journal": journal,
                "year": year,
                "authors": authors_str,
                "snippet": snippet,
                "fetched_date": today,
            }

        publications.append(pub)

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(publications, f, indent=2, ensure_ascii=False)

    print(f"✓ Wrote {len(publications)} publication(s) to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
