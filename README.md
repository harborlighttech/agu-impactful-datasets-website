# Impactful Datasets — data pipeline and site prototype

Turns the AGU *Impactful Datasets* nomination spreadsheet into RDF, reports on the
messiness of the source, and builds a two-page site prototype from the result.

Three scripts run in order. Each reads the previous one's output, so the chain is
reproducible from the original CSV with no manual steps in between.

```
Impactful_Datasets_v1_June_16_-_CSV_Format.csv        (source, 133 rows × 16 columns)
        │
        │  1. restructure_impactful_datasets.py
        ▼
impactful_datasets.jsonld        the RDF graph, 17,310 triples
column_report.md                 per-column multi-value analysis
column_statistics.json           the same, machine-readable
        │
        ├──── 2. analyze_graph.py ──────▶  graph_statistics.md
        │                                  graph_statistics.json
        │                                  conceptual_model.svg
        │
        └──── 3. build_wireframe.py ────▶  impactful_datasets.data.jsonld
                                           impactful_datasets_wireframe.html
```

---

## Running it

```bash
pip install pandas rdflib pillow

# 1. CSV  ->  RDF graph + column report
python restructure_impactful_datasets.py Impactful_Datasets_v1_June_16_-_CSV_Format.csv -o out

# 2. graph  ->  statistics + conceptual model diagram
python analyze_graph.py out/impactful_datasets.jsonld -o out

# 3. graph  ->  public data file + site prototype
python build_wireframe.py out/impactful_datasets.jsonld \
    --logo AGU_Logo_H_CMYK.png -o out
```

Step 2 is optional — it only produces reporting, and step 3 does not depend on it.
Steps 1 and 3 are required, in that order.

**Keep `out/impactful_datasets.data.jsonld` under version control.** Step 3 reads
the ids already in that file and reuses them. Delete it and every dataset is
renumbered, which breaks every published URL. See *Permanent identifiers* below.

---

## The scripts

### 1. `restructure_impactful_datasets.py`

CSV in, RDF out. The real work is guessing where a single spreadsheet cell holds
more than one value, which happens three different ways in this file:

- **delimiter-separated lists** — `;` is reliable; commas are not, since
  `Jochum, Klaus Peter` is one person and `A. J. Newman, M. P. Clark` is two
- **labelled parallel arrays** — four columns use `Nominator 1:` / `Nominator 2:`
  headers *inside* the cell, and block *n* of one column belongs to block *n* of
  the others (verified: the labels agree across all 133 rows)
- **sub-schemas inside a cell** — justifications nest `People:` / `Planet:` /
  `Prosperity:` blocks, the vocabulary named in the column header itself

It also repairs the file's encoding. The source is **not valid UTF-8**: 16 bytes
are Mac Roman, and a plain `pd.read_csv` raises `UnicodeDecodeError` until they
are fixed.

Every row keeps an `agu:SourceRow` node holding the verbatim original cells, so
each heuristic guess can be checked or reversed.

Outputs:

| File | What it is |
|---|---|
| `impactful_datasets.jsonld` | the full graph — 133 datasets, 149 nominators, 17,310 triples across 23 classes |
| `column_report.md` | per-column analysis: fill rate, cardinality histograms, which delimiter was guessed and why, and where the guesses are weakest |
| `column_statistics.json` | the same figures, for diffing against a future export |
| `_clean.csv` | the encoding-repaired intermediate, kept so you can see what changed |

### 2. `analyze_graph.py`

Reads the graph and answers questions about it with SPARQL rather than by
recomputing from the CSV. Every number in its output — and every label in the
diagram — comes from a query, so both stay correct when the source changes.

| File | What it is |
|---|---|
| `graph_statistics.md` | headline counts, all 23 classes with instance counts, the 10 datasets with multiple nominators, and the 9 people who nominated more than one |
| `graph_statistics.json` | the same, machine-readable |
| `conceptual_model.svg` | the class diagram, standalone with light/dark support; box labels are filled from the query results |

### 3. `build_wireframe.py`

Builds the public data file and the site prototype from the graph.

| File | What it is |
|---|---|
| `impactful_datasets.data.jsonld` | **the published data.** A schema.org `DataCatalog` of 133 `Dataset` records, valid JSON-LD (6,992 triples). Serve this at a stable URL and anyone can consume it. |
| `impactful_datasets_wireframe.html` | the site. Single file, no external assets — the AGU logo is embedded as a base64 CSS token. |

Useful flags: `--data-url` (where the page fetches its data once the file has a
permanent home), `--base-url` (host used in `mainEntityOfPage`), `--featured`
(which dataset page 2 opens on), `--logo`.

---

## Things to know

### The short display name is a placeholder

Every dataset in the data file carries an empty **`alternateName`**. That is the
short label shown on the book spines — schema.org's standard term for an
alternative name for the same thing. Fill these in (roughly 24 characters or
fewer fits a spine); the site falls back to `name` while they are blank, so
nothing breaks in the meantime.

### Permanent identifiers

Dataset URLs look like:

```
#/dataset/agu-0004-argo
```

Only `agu-0004` is authoritative. The trailing slug is decoration, ignored when
parsing, so a stale slug still resolves and is then rewritten — the pattern
Stack Overflow and Medium use.

Ids are **minted once and frozen**. Each build reads the ids already published in
the data file and reuses them, keyed on DOI plus title; only genuinely new
datasets get a number. A clean rebuild reports `0 new ids minted`. This is what
lets a URL survive a title edit, a re-sort, or rows being added or withdrawn.

Two rules follow: keep the data file in version control, and never renumber by
hand. Unknown ids fall back to the collection rather than erroring.

### Namespaces

```
terms   urn:org:agu:data:ns:{term}
ids     urn:org:agu:data:impactful-datasets:id:{type}:{local}
```

`{type}` is `dataset`, `person`, `organization`, `nomination`, `repository`,
`theme`, `sourcerow`, `scheme` or `collection`. URNs are location-independent, so
identifiers survive the site moving; the resolvable web address travels alongside
on `schema.org/mainEntityOfPage`. People with an ORCID keep the ORCID URI as their
`@id` — a real global identifier beats a minted local one.

### Opening the prototype from disk

The page fetches `impactful_datasets.data.jsonld` at load and keeps an embedded
copy as a fallback. The fallback matters: a `file://` page cannot fetch a sibling
file in most browsers, so without it, double-clicking the HTML would show an empty
collection. Serve both files together, or point at a hosted URL with `--data-url`.

### Two live API calls on the dataset page

Both are called from the browser, both degrade gracefully:

- **DataCite** (`api.datacite.org`) — authors, publisher, year, related works.
  Shown only when the registry answers, so nothing is ever attributed to DataCite
  unless it came from DataCite. Appears for the 37 of 133 datasets with a DOI.
- **DOI Citation Formatter** (`citation.doi.org`, APA / en-US) — behind the
  "Cite this dataset" button. Falls back to showing the DOI if unreachable.
  *This endpoint has not been verified from a browser; check CORS before relying
  on it in a demo.*

### Known data-quality gaps

These are properties of the nominations, not bugs to fix in code:

- 37 of 133 datasets carry a DOI, so the DataCite panel and cite button appear on
  about a quarter of pages
- 107 of 133 have reference publications
- repository names are unnormalised — `Zenodo` and `zenodo.org` merge, but
  `GES DISC` and its full NASA name do not, so 117 nodes represent roughly 99 real
  repositories
- affiliations are raw strings including postal addresses, so one institution can
  appear several times
- ~15 rows put a URL in the repository *name* column
- the data contains 173 personal email addresses — strip or hash them before
  publishing anything derived from the full graph
