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
        └──── 3. build_wireframe.py ────▶  index.html
                                           assets/css/*  assets/js/*  assets/img/*
                                           data/impactful_datasets.data.jsonld
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

**Keep `out/data/impactful_datasets.data.jsonld` under version control.** Step 3 reads
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
| `impactful_datasets.jsonld` | the full graph — 133 datasets, 161 nominators, 17,310 triples across 23 classes |
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

Emits a static website as ordinary linked assets:

```
index.html                            markup, SEO/OpenGraph metadata, rel=alternate
                                      link to the machine-readable data
assets/css/tokens.css                 design tokens — brand colours, type, logo.
                                      The only file a rebrand needs to touch.
assets/css/site.css                   component styles
assets/js/config.js                   deployment settings (data URL, featured record)
assets/js/app.js                      application script
assets/img/agu-logo.png               brand mark
data/impactful_datasets.data.jsonld   the published collection, schema.org JSON-LD
```

`data/impactful_datasets.data.jsonld` is **the published data** — a schema.org
`DataCatalog` of 133 `Dataset` records, valid JSON-LD. Serve it at a stable URL
and anyone can consume it. It is also the id registry; see *Permanent identifiers*.

The page fetches its data over HTTP, so **the site must be served, not opened from
disk**. It says so on screen if the fetch fails. Any static host works:

```bash
cd out && python3 -m http.server
```

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

If a build ever reports `133 new ids minted` when the registry file exists, stop:
something has changed the shape the registry is read from, and publishing would
break every URL. The build now refuses to continue when a registry file exists but
yields no readable ids — that guard was added after exactly this happened during a
format change.

### The shape of the published data

`data/impactful_datasets.data.jsonld` is a flat JSON-LD graph — a `DataCatalog`,
a `DefinedTermSet` of discipline groups, two property definitions, 133 `Dataset`
nodes, and 133 `ItemList`s holding 174 `EndorseAction`s, all as siblings under
`@graph`.

**Nominations are endorsements.** A nomination is not authorship, so each one is
a `schema.org/EndorseAction` rather than a `creator` or `contributor` link:

```json
{ "@type": "EndorseAction",
  "identifier": { "@type": "PropertyValue", "propertyID": "AGU-Nominator-Slot", "value": "1" },
  "agent":  { "@type": "Person", "@id": "https://orcid.org/0000-...", "name": "..." },
  "object": { "@id": "urn:org:agu:data:impactful-datasets:id:dataset:agu-0004" },
  "description": "how this nominator works with the dataset",
  "result": { "@type": "CreativeWork", "text": "their justification",
              "about": [ { "@type": "DefinedTerm", "name": "People" } ] } }
```

The action points at its dataset with `object`; schema.org has no property for
hanging a *performed* action off the thing acted on, which is why the graph is
flat rather than nested. The interaction statement sits on the action, not the
agent: the same person can nominate several datasets and agent nodes share an
ORCID `@id`, so a description there would merge across datasets.

**Ordering is explicit.** A graph is unordered, so the two sequences that matter
are declared `"@container": "@list"` in the context — `dataset` on the catalog
(collection display order) and `itemListElement` (nominator order within a
dataset). Both parse as genuine `rdf:List`s.

**Counts are never stored.** Nominator, citation and reuse totals are derived by
measuring the lists at load time. A stored count drifts from the list it
describes; this pipeline has already shipped that bug once.

### Discipline vocabulary

The nine discipline groups are published as a schema.org `DefinedTermSet` under
`agu:themes`. Each `DefinedTerm` carries the short key as its `identifier` and the
full label as its `name`. Datasets reference the term by `@id` through `keywords`,
so the label is stated once and never repeated per dataset. A group can hold more
than one keyword: one dataset was nominated under two disciplines and appears
under both.

Labels are never retyped in the site builder — they are read from the RDF graph,
which carries them verbatim from the spreadsheet. Corrections to the source
wording live in `DISCIPLINE_FIXES` in `restructure_impactful_datasets.py`, and the
verbatim original survives on the `agu:SourceRow` node.

Note: schema.org has no singular `keyword` property — `keywords` is the correct
term, and it accepts a `DefinedTerm`, which is exactly this pattern.

### agu:ResponsibleParty

One class is declared: `agu:ResponsibleParty`, a subclass of `prov:Agent`. It
covers whoever answers for a dataset — an individual, an institution, a standing
team or a service desk — and exists mainly for parties that cannot honestly be
resolved to either `schema:Person` or `schema:Organization`. Typing a science
working group as `ResponsibleParty` records what is known; typing it `Person`
guesses wrong.

Subsumption is asserted only in the direction that is AGU's to assert. The file
does **not** say `schema:Person rdfs:subClassOf agu:ResponsibleParty`: that is a
global claim, and once graphs are merged it makes every `schema:Person` anywhere
an AGU responsible party. Tested with an RDFS reasoner — an unrelated novelist and
bakery in a merged graph get pulled in under that assertion, and are untouched
without it. `prov:Agent` supplies the shared supertype instead, since it already
means a party that bears responsibility.

Two `skos:narrowMatch` pointers to `schema:Person` and `schema:Organization`
record which classes a responsible party will usually turn out to be. The
relation runs that way because this concept is the broader one: it also covers
the teams, working groups and service desks that are neither. They are
documentation, not logic — SKOS mapping relations carry no entailment, so the
pointers describe the relationship without asserting anything about anybody
else's data. Verified: a foreign `schema:Person` is untouched after reasoning,
while `ResponsibleParty` instances still infer as `prov:Agent`.

Nothing is typed `ResponsibleParty` yet. See `person_review.csv` and
`review_person_types.py`: 191 entities currently typed `Person` are flagged, of
which 82 look like organisations, 62 hold several entities in one string, and 43
are parse artifacts rather than entities at all. That review is unresolved.

### The two AGU properties, and why they are not aliased

Two keys stay in the AGU namespace: `agu:curator` and `agu:reuseExample`. Both are
declared as `rdf:Property` nodes in the graph, each carrying an `rdfs:comment`
that states precisely what AGU means by it, and an `owl:equivalentProperty` link
to its schema.org counterpart — `maintainer` and `subjectOf` respectively.

It is tempting to skip that and alias the keys directly in the context:

```json
"agu:curator": { "@id": "https://schema.org/maintainer" }     // DO NOT DO THIS
```

**That is invalid JSON-LD 1.1 and a conforming processor rejects the entire
document**, not just the term. The spec requires a term whose name is in
compact-IRI form to expand to the same IRI its prefix would give. `rdflib` accepts
it silently, which makes the mistake easy to ship; `pyld` refuses it with
`invalid IRI mapping`. Validate with a conforming processor before trusting a
context change:

```bash
python -c "from pyld import jsonld, json; jsonld.expand(json.load(open('out/data/impactful_datasets.data.jsonld')))"
```

The same rule blocks putting an `rdfs:comment` *inside* a term definition — only
JSON-LD keywords are allowed there. Hence the property nodes, where the
documentation is an ordinary triple any consumer can read.

Consumers wanting pure schema.org can apply the equivalence in three lines; it
yields 126 `maintainer` and 397 `subjectOf` triples:

```python
for p, q in g.subject_objects(OWL.equivalentProperty):
    for s, _, o in g.triples((None, p, None)):
        g.add((s, q, o))
```

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
