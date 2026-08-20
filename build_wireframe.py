#!/usr/bin/env python3
"""
Build the two-page "Impactful Datasets" site prototype as one standalone HTML file,
in AGU brand: Montserrat + Lora, primary #244C5A, secondary #007DBA, white ground.

Reads the RDF graph produced by restructure_impactful_datasets.py and inlines a
compact payload for all 133 datasets, plus the AGU logo as a base64 CSS token,
so the result is a single file with no external assets.

Requirements:
    pip install pillow      # only to downscale + embed the logo

Usage:
    python build_wireframe.py impactful_datasets.jsonld --logo AGU_Logo_H_CMYK.png [-o OUTDIR]

Notes
-----
Page 1 groups the books by discipline and lays each group out in uniform rows:
20 books per row on desktop, 14 on tablets, 10 on phones. A group of 29 therefore
fills one row of 20 and a second of 9 on desktop. Rows are rebuilt when the
viewport crosses a breakpoint; edit ROW_SIZES in the embedded JS to change them.

Search runs entirely client-side over a haystack built per book from title,
discipline group, repository, nominators, creators and curators. Edit the `hay`
assignment in the embedded JS to change which fields are searchable. Matching
normalises accents, apostrophes and dashes, so "earth's interior" and "earths
interior" both hit the curly-apostrophe discipline label.

Page 2 always shows "Referenced in" from our own nomination record, up to 8
citations with a "+N more" line beyond that; URLs and DOIs inside the citation
text are linkified. The DataCite panel is separate and appears only when the
registry actually answers: hidden for datasets without a DOI, and hidden again
if the call fails or times out. The two may overlap in what they list, which is
intended -- one is our record, the other is the registry's.

The eight discipline colours are anchored on the two brand colours and every one
clears 4.5:1 against the white spine text.
"""
import argparse, base64, collections, io, json, re
from pathlib import Path

ap = argparse.ArgumentParser(description=__doc__,
                             formatter_class=argparse.RawDescriptionHelpFormatter)
ap.add_argument("jsonld", type=Path)
ap.add_argument("--logo", type=Path, default=None,
                help="AGU logo PNG; omitted = logo slots render empty")
ap.add_argument("-o", "--outdir", type=Path, default=Path("out"))
ap.add_argument("--featured", default="Argo",
                help="title of the dataset shown on page 2 (default: Argo)")
ap.add_argument("--nominators", type=int, default=149,
                help="distinct nominator count shown in the tally")
ap.add_argument("--logo-width", type=int, default=620,
                help="px width the logo is downscaled to before embedding")
args = ap.parse_args()
JSONLD = args.jsonld
args.outdir.mkdir(parents=True, exist_ok=True)
OUT = args.outdir / "impactful_datasets_wireframe.html"


def _logo_png():
    """Downscale the brand logo so the embedded copy stays small."""
    if not args.logo:
        return b""
    from PIL import Image
    im = Image.open(args.logo).convert("RGBA")
    w = args.logo_width
    im = im.resize((w, round(w * im.size[1] / im.size[0])), Image.LANCZOS)
    buf = io.BytesIO()
    im.save(buf, "PNG", optimize=True)
    return buf.getvalue()


d = json.load(open(JSONLD))
g = d['@graph']; by = {n['@id']: n for n in g}

THEME_ORDER = [
 ("id:theme/atmospheric-science-space-weather", "Atmospheric Science, Space Weather", "atmos"),
 ("id:theme/ocean-science-hydrology-cryosphere", "Ocean Science, Hydrology, Cryosphere", "ocean"),
 ("id:theme/global-environmental-change-paleoceanography-and-paleoclimatology-biogeoscience", "Global Environmental Change, Paleoclimatology, Biogeoscience", "biosphere"),
 ("id:theme/earth-s-interior-geodesy", "Earth's Interior, Geodesy", "interior"),
 ("id:theme/earth-surface-natural-hazards-geology-near-surface-geophysics", "Earth Surface, Natural Hazards, Geology", "surface"),
 ("id:theme/education-geohealth-society-education", "Education, GeoHealth, Society", "society"),
 ("id:theme/space-and-planetary-science", "Space and Planetary Science", "space"),
 ("id:theme/earth-planetary-materials", "Earth & Planetary Materials", "materials"),
]
tkey = {t[0]: t[2] for t in THEME_ORDER}
# verify every theme id resolves
real = {n['@id'] for n in g if n.get('@type')=='skos:Concept'}
missing = real - set(tkey)
assert not missing, f"unmapped themes: {missing}"

nom_of = {}
for n in g:
    if 'agu:Nomination' in (n.get('@type') or []):
        nom_of[n['nominates']] = n

def txt(v, cap=None):
    if v is None: return None
    if isinstance(v, list):
        v = " ".join(txt(x) or "" for x in v)
    elif isinstance(v, dict):
        v = v.get('schema:text') or v.get('name') or ""
    v = re.sub(r'\s+', ' ', str(v)).strip()
    return (v[:cap].rsplit(' ', 1)[0] + '…') if cap and len(v) > cap else v

out = []
for x in g:
    if 'dcat:Dataset' not in (x.get('@type') or []): continue
    nm = nom_of.get(x['@id'], {})
    people = []
    # Nominator order in the graph follows the "Nominator N:" blocks in the source
    # spreadsheet, so position maps to the sequence used by the justification blocks.
    for seq, pid in enumerate((nm.get('nominator') or []), start=1):
        p = by.get(pid, {})
        affs = [by[a]['name'] for a in (p.get('affiliation') or []) if a in by]
        people.append({"seq": seq, "name": p.get('name'),
                       "orcid": pid if pid.startswith('http') else None,
                       "affil": affs[0] if affs else None})
    just = []
    for j in (nm.get('justification') or []):
        dims = [{"label": dd.get('prefLabel'), "text": txt(dd.get('schema:text'), 420)}
                for dd in (j.get('impactDimension') or [])]
        just.append({"seq": j.get('sequence'), "text": txt(j.get('schema:text'), 900), "dims": dims})
    lp = x.get('landingPage') or []
    doi = next((u for u in lp if 'doi.org/' in u), None)
    repos = [by[r] for r in (x.get('inCatalog') or []) if r in by]
    refs = [txt(r.get('schema:citation'), 300) for r in (x.get('isReferencedBy') or [])][:8]
    reuse = [txt(r.get('schema:text'), 200) for r in (x.get('reuseExample') or [])][:5]
    out.append({
        "id": x['@id'].split('/')[-1],
        "title": x.get('title'),
        "theme": tkey[(x.get('theme') or [None])[0]] if x.get('theme') else "society",
        "nomCount": len(people),
        "nominators": people,
        "doi": doi,
        "links": [u for u in lp if u != doi][:3],
        "repo": repos[0].get('name') if repos else None,
        "repoIds": (repos[0].get('identifier') if repos else None) or [],
        "creators": [c.get('name') for c in (x.get('creator') or [])][:4],
        "curators": [c.get('name') for c in (x.get('curator') or [])][:3],
        "desc": txt(x.get('description'), 1100),
        "just": just[:4],
        "refs": refs,
        "reuse": reuse,
        "reuseTotal": len(x.get('reuseExample') or []),
        "refsTotal": len(x.get('isReferencedBy') or []),
    })

out.sort(key=lambda r: (-r['nomCount'], r['title'].lower()))
payload = {"themes": [{"key": k, "label": l} for _, l, k in THEME_ORDER], "datasets": out}



DATA = payload
DATA['featured'] = next((d['id'] for d in DATA['datasets'] if d['title'] == args.featured),
                        DATA['datasets'][0]['id'])
DATA['nominatorCount'] = args.nominators



HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Impactful Datasets — wireframe</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Montserrat:wght@400;500;600;700;800&family=Lora:ital,wght@0,400;0,500;0,600;1,400&display=swap" rel="stylesheet">
<style>
:root{
  /* AGU brand: primary #244C5A, secondary #007DBA, white ground */
  --primary:#244C5A; --secondary:#007DBA;
  --paper:#FFF; --surface:#FFF; --surface-2:#F5F7F8;
  --ink:#244C5A; --ink-2:#587380; --ink-3:#5E7682;
  --rule:#D5DFE3; --rule-2:#E8EEF0;
  --mark:#007DBA; --mark-bg:#E4F2FA;
  /* discipline ramp, anchored on the two brand colours; all >=4.5:1 vs white */
  --atmos:#007DBA; --ocean:#00778A; --biosphere:#2F7D5C; --interior:#A24B2E;
  --surface-c:#8C6410; --society:#6B4C93; --space:#244C5A; --materials:#6B5B4B;
  --f-display:'Montserrat','Helvetica Neue',Arial,sans-serif;
  --f-body:'Lora',Georgia,'Times New Roman',serif;
  --f-label:'Montserrat','Helvetica Neue',Arial,sans-serif;
  --f-code:ui-monospace,'SF Mono',Menlo,Consolas,monospace;
  --shell:1180px;
  --logo:url(data:image/png;base64,__LOGO__);
}
*{box-sizing:border-box}
html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--paper);color:var(--ink);font-family:var(--f-display);
  font-size:15px;line-height:1.6;font-weight:400;-webkit-font-smoothing:antialiased}
h1,h2,h3,h4{margin:0;font-weight:800;letter-spacing:-.024em;line-height:1.14}
p{margin:0 0 .9em}
a{color:inherit}
.shell{max-width:var(--shell);margin:0 auto;padding:0 32px}
.mono{font-family:var(--f-label);font-size:11px;letter-spacing:.06em;text-transform:uppercase}
[class*="label"],.pagemark,.chip,.dl dt,.tip dt,.sec>h2,.card>h2,.dc-bar h2,.legend button,
.searchbar .count,.searchbar .clear,.linklist .k,.dim,.just .who,.more,.dc-status,
.group-head .n,.tally span,.readlink,.back{
  font-weight:600}
/* prose runs in Lora */
.masthead .lede,.callout p,.btn-nominate p,.sec p,.just p,.reuse li,.refs li,
.people .aff,.dl dd,.tip dd,.empty p,.repo-sub{font-family:var(--f-body);letter-spacing:0}
.endpoint,.people .oid{font-family:var(--f-code)}

/* ---------- brand header / footer ---------- */
.site{background:#fff;border-bottom:1px solid var(--rule)}
.site .shell{display:flex;align-items:center;gap:32px;height:82px}
.brand{display:flex;align-items:center;text-decoration:none;flex:none}
.logo{display:block;background:var(--logo) no-repeat left center;background-size:contain;
  height:38px;width:128px;print-color-adjust:exact;-webkit-print-color-adjust:exact}
.logo.foot{height:30px;width:101px;opacity:.92}
.site-nav{display:flex;align-items:center;gap:28px;margin-left:auto}
.site-nav a{font-family:var(--f-label);font-size:12px;font-weight:600;letter-spacing:.09em;
  text-transform:uppercase;color:var(--ink-2);text-decoration:none;padding:4px 0;
  border-bottom:2px solid transparent}
.site-nav a:hover{color:var(--primary);border-bottom-color:var(--secondary)}
.site-nav a[aria-current="page"]{color:var(--primary);border-bottom-color:var(--primary)}
.site-foot{border-top:3px solid var(--primary);background:var(--surface-2);margin-top:60px}
.site-foot .shell{display:flex;align-items:center;gap:28px;padding-top:28px;padding-bottom:28px}

.site-foot p{margin:0;margin-left:auto;font-family:var(--f-label);font-size:11px;font-weight:500;
  letter-spacing:.06em;text-transform:uppercase;color:var(--ink-3);text-align:right}

/* ---------- page frame ---------- */
.page{display:none;padding:44px 0 80px}
.page.active{display:block}
.pagemark{font-family:var(--f-label);font-size:10px;letter-spacing:.16em;text-transform:uppercase;
  color:var(--ink-3);display:flex;align-items:center;gap:10px;margin-bottom:26px}
.pagemark::after{content:"";flex:1;height:1px;background:var(--rule)}

/* ---------- page 1 header ---------- */
.masthead{display:grid;grid-template-columns:minmax(0,1fr) 300px;gap:56px;align-items:end;
  padding-bottom:26px;border-bottom:3px solid var(--primary)}
.masthead h1{font-size:clamp(29px,4.1vw,45px);letter-spacing:-.028em;max-width:19ch}
.masthead .lede{margin:18px 0 0;font-size:16.5px;line-height:1.65;color:var(--ink-2);max-width:58ch}
.tally{display:flex;flex-direction:column;gap:12px}
.tally div{display:flex;align-items:baseline;justify-content:space-between;gap:12px;
  border-bottom:1px solid var(--rule-2);padding-bottom:7px}
.tally b{font-size:29px;font-weight:800;letter-spacing:-.025em;color:var(--primary)}
.tally span{font-family:var(--f-label);font-size:10px;letter-spacing:.09em;text-transform:uppercase;
  color:var(--ink-2);text-align:right}

/* ---------- actions ---------- */
.actions{position:relative;display:grid;grid-template-columns:290px minmax(0,1fr);gap:22px;margin:30px 0 46px}
.act{position:relative;background:var(--surface);border:1px solid var(--rule);border-radius:6px;padding:22px}
.btn-nominate{display:flex;flex-direction:column;justify-content:space-between;gap:16px;
  background:var(--primary);border-color:var(--primary);color:#fff}
.btn-nominate .cta{display:inline-flex;align-items:center;justify-content:center;gap:9px;width:100%;
  text-decoration:none;box-sizing:border-box;
  background:#fff;color:var(--ink);border:none;border-radius:4px;padding:13px 16px;cursor:pointer;
  font-family:var(--f-display);font-size:15px;font-weight:600;letter-spacing:-.01em}
.btn-nominate .cta{color:var(--primary);font-weight:700}
.btn-nominate .cta:hover{background:#D9E7EE}
.btn-nominate .cta:focus-visible{outline:2px solid #4FB3E8;outline-offset:3px}
.btn-nominate p{color:#BBD2DC;font-size:13.5px;margin:0}
.callout{display:grid;grid-template-columns:112px minmax(0,1fr);gap:22px;align-items:center}
.callout .thumb{aspect-ratio:1;border:1px solid var(--rule);border-radius:4px;background:var(--surface-2);
  display:flex;align-items:center;justify-content:center;color:var(--ink-3);
  font-family:var(--f-label);font-size:9px;letter-spacing:.1em;text-align:center;line-height:1.5}
.callout h3{font-size:21px;letter-spacing:-.022em;margin-bottom:7px}
.callout p{font-size:14px;color:var(--ink-2);margin-bottom:11px}
.readlink{font-family:var(--f-label);font-size:11px;letter-spacing:.06em;text-transform:uppercase;
  color:var(--mark);text-decoration:none;border-bottom:1px solid currentColor;padding-bottom:2px}

/* ---------- collection ---------- */
.group{margin-bottom:34px;scroll-margin-top:16px}
.group-head{display:flex;align-items:baseline;gap:12px;margin-bottom:10px}
.group-swatch{width:11px;height:11px;border-radius:2px;flex:none;transform:translateY(1px)}
.group-head h3{font-size:15px;font-weight:600;letter-spacing:-.012em}

.books{display:grid;grid-template-columns:repeat(20,1fr);gap:5px;align-items:end;
  padding:18px 7px 0;background:linear-gradient(180deg,transparent 0 58%,var(--surface-2) 58%);
  border-bottom:5px solid var(--primary);border-radius:2px;margin-bottom:9px}
.books:last-child{margin-bottom:0}
.book{min-width:0;position:relative;height:190px;border:none;border-radius:3px 3px 0 0;cursor:pointer;
  padding:13px 0 13px;display:flex;align-items:flex-end;justify-content:center;
  transition:transform .13s ease;color:#fff;font-family:var(--f-label);font-size:11.5px;
  font-weight:600;letter-spacing:.012em;overflow:hidden;
  box-shadow:inset -1px 0 0 rgba(0,0,0,.15),inset 1px 0 0 rgba(255,255,255,.13)}
.book span{writing-mode:vertical-rl;transform:rotate(180deg);white-space:nowrap;
  overflow:hidden;text-overflow:ellipsis;max-height:100%;opacity:1;
  text-shadow:0 1px 2px rgba(0,0,0,.24)}
.book:hover,.book:focus-visible{transform:translateY(-9px);outline:none;
  box-shadow:0 5px 14px rgba(22,32,42,.26)}
.book:focus-visible{box-shadow:0 0 0 2px var(--mark),0 5px 14px rgba(22,32,42,.26)}
.book::after{content:"";position:absolute;left:0;right:0;top:0;height:8px;
  background:rgba(255,255,255,.17);border-radius:3px 3px 0 0}
.legend{display:flex;flex-wrap:wrap;gap:9px;margin:0 0 28px}
.legend button{display:inline-flex;align-items:center;gap:10px;cursor:pointer;border:none;
  border-radius:5px;padding:10px 11px 10px 14px;font-family:var(--f-label);font-size:12px;
  font-weight:600;letter-spacing:.035em;text-transform:uppercase;color:#fff;line-height:1.15;
  box-shadow:0 1px 0 rgba(0,0,0,.13);transition:transform .12s ease,box-shadow .12s ease}
.legend button:hover{transform:translateY(-2px);box-shadow:0 5px 14px rgba(36,76,90,.28)}
.legend button:focus-visible{outline:2px solid var(--primary);outline-offset:3px}
.legend button .c{background:rgba(255,255,255,.24);border-radius:3px;padding:2px 7px;
  font-size:11px;font-variant-numeric:tabular-nums}

/* ---------- search ---------- */
.searchbar{display:flex;align-items:center;gap:14px;height:54px;padding:0 8px 0 17px;
  background:var(--surface);border:1px solid var(--rule);border-radius:6px;margin:0 0 16px}
.searchbar:focus-within{border-color:var(--ink);box-shadow:0 0 0 3px rgba(27,77,184,.11)}
.searchbar input{flex:1;min-width:0;border:none;background:none;outline:none;
  font-family:var(--f-display);font-size:16px;letter-spacing:-.01em;color:var(--ink)}
.searchbar input::placeholder{color:var(--ink-3)}
.searchbar .glyph{font-size:15px;color:var(--ink-3);flex:none;line-height:1}
.searchbar .count{font-family:var(--f-label);font-size:10px;letter-spacing:.07em;
  text-transform:uppercase;color:var(--ink-2);white-space:nowrap;flex:none;
  font-variant-numeric:tabular-nums}
.searchbar .clear{flex:none;border:1px solid var(--rule);background:var(--surface-2);
  border-radius:4px;padding:6px 11px;cursor:pointer;font-family:var(--f-label);font-size:10px;
  letter-spacing:.07em;text-transform:uppercase;color:var(--ink-2)}
.searchbar .clear:hover{border-color:var(--ink);color:var(--ink)}
.searchbar .clear[hidden]{display:none}
.empty{padding:44px 8px;text-align:center;border:1px dashed var(--rule);border-radius:6px;
  background:var(--surface-2)}
.empty p{font-size:15px;color:var(--ink-2);max-width:44ch;margin:0 auto .9em}
.empty b{color:var(--ink);font-weight:600}
[hidden]{display:none!important}

/* ---------- hover bubble ---------- */
.tip{position:fixed;z-index:80;width:310px;background:var(--primary);color:#fff;border-radius:7px;
  padding:14px 16px;box-shadow:0 12px 34px rgba(22,32,42,.32);pointer-events:none;
  opacity:0;transform:translateY(5px);transition:opacity .12s ease,transform .12s ease}
.tip.on{opacity:1;transform:none}
.tip h4{font-size:14.5px;font-weight:600;letter-spacing:-.012em;line-height:1.32;margin:0 0 11px}
.tip dl{margin:0;display:grid;grid-template-columns:auto minmax(0,1fr);gap:6px 13px}
.tip dt{font-family:var(--f-label);font-size:9px;font-weight:600;letter-spacing:.09em;
  text-transform:uppercase;color:#9CC3D4;padding-top:2px;white-space:nowrap}
.tip dd{margin:0;font-size:12.5px;line-height:1.45;color:#E4EBF0}
.tip .tail{position:absolute;width:11px;height:11px;background:var(--primary);transform:rotate(45deg)}

/* ---------- page 2 ---------- */
.back{display:inline-flex;align-items:center;gap:8px;background:none;border:none;cursor:pointer;
  font-family:var(--f-label);font-size:11px;letter-spacing:.08em;text-transform:uppercase;
  color:var(--ink-2);padding:0;margin-bottom:24px}
.back:hover{color:var(--mark)}
.d-head{padding-bottom:24px;border-bottom:3px solid var(--primary)}
.chip{display:inline-flex;align-items:center;gap:8px;font-family:var(--f-label);font-size:10px;
  letter-spacing:.09em;text-transform:uppercase;color:var(--ink-2);margin-bottom:14px}
.chip i{width:10px;height:10px;border-radius:2px}
.d-head h1{font-size:clamp(32px,4.4vw,50px);letter-spacing:-.03em;max-width:20ch}
.d-meta{display:flex;flex-wrap:wrap;gap:8px 26px;margin-top:16px;font-family:var(--f-label);
  font-size:11px;color:var(--ink-2)}
.d-meta b{color:var(--ink);font-weight:500}
.d-grid{position:relative;display:grid;grid-template-columns:minmax(0,1.65fr) minmax(0,1fr);
  gap:44px;margin-top:34px;align-items:start}
.sec{margin-bottom:38px}
.sec > h2{font-size:12px;font-family:var(--f-label);font-weight:500;letter-spacing:.12em;
  text-transform:uppercase;color:var(--ink-3);padding-bottom:9px;margin-bottom:16px;
  border-bottom:1px solid var(--rule)}
.sec p{font-size:15.5px;color:#31505C}
.card{position:relative;background:var(--surface);border:1px solid var(--rule);border-radius:6px;
  padding:20px;margin-bottom:20px}
.card > h2{font-size:11px;font-family:var(--f-label);font-weight:500;letter-spacing:.12em;
  text-transform:uppercase;color:var(--ink-3);margin-bottom:14px}
.just{border-left:2px solid var(--rule);padding:2px 0 2px 18px;margin-bottom:20px}
.just .who{font-family:var(--f-label);font-size:10px;letter-spacing:.08em;text-transform:uppercase;
  color:var(--mark);margin-bottom:7px}
.just p{font-size:14.5px;color:#31505C;margin-bottom:.7em}
.dims{display:flex;flex-wrap:wrap;gap:6px;margin-top:9px}
.dim{font-family:var(--f-label);font-size:9.5px;letter-spacing:.08em;text-transform:uppercase;
  background:var(--surface-2);border:1px solid var(--rule);border-radius:99px;padding:3px 10px;color:var(--ink-2)}
.people{list-style:none;margin:0;padding:0}
.people li{padding:12px 0;border-top:1px solid var(--rule-2)}
.people li:first-child{border-top:none;padding-top:0}
.people b{display:block;font-size:14.5px;font-weight:600;letter-spacing:-.01em}
.people .aff{font-size:12.5px;color:var(--ink-2);line-height:1.45;margin-top:2px}
.people .oid{font-family:var(--f-label);font-size:10px;color:var(--ink-3);margin-top:4px;display:block;
  word-break:break-all}
.linklist{list-style:none;margin:0;padding:0}
.linklist li{border-top:1px solid var(--rule-2)}
.linklist li:first-child{border-top:none}
.linklist a{display:flex;align-items:center;justify-content:space-between;gap:12px;padding:11px 0;
  text-decoration:none;font-size:13.5px;word-break:break-all}
.linklist a:hover{color:var(--mark)}
.linklist .k{font-family:var(--f-label);font-size:9.5px;letter-spacing:.09em;text-transform:uppercase;
  color:var(--ink-3);flex:none}
.reuse{list-style:none;margin:0;padding:0;counter-reset:r}
.reuse li{position:relative;padding:0 0 14px 30px;font-size:14px;color:#31505C;counter-increment:r}
.reuse li::before{content:counter(r,decimal-leading-zero);position:absolute;left:0;top:1px;
  font-family:var(--f-label);font-size:10px;color:var(--ink-3)}
.refs{list-style:none;margin:0;padding:0}
.refs li{padding:11px 0;border-top:1px solid var(--rule-2);font-size:13px;color:var(--ink-2);line-height:1.5}
.refs li:first-child{border-top:none}
.refs a{color:var(--secondary);text-decoration:none;word-break:break-all}
.refs a:hover{text-decoration:underline}
.more{font-family:var(--f-label);font-size:10px;letter-spacing:.07em;text-transform:uppercase;
  color:var(--ink-3);margin-top:10px}

/* ---------- nominator cross-links ---------- */
.just .who{display:inline-flex;align-items:center;gap:7px;background:none;border:none;padding:0;
  cursor:pointer;text-align:left}
.just .who .nm{color:var(--secondary);border-bottom:1px solid transparent}
.just .who:hover .nm,.just .who:focus-visible .nm{border-bottom-color:currentColor}
.just .who:focus-visible{outline:2px solid var(--secondary);outline-offset:3px;border-radius:3px}
.just .who .seq{font-size:9.5px;background:var(--surface-2);border:1px solid var(--rule);
  border-radius:99px;padding:1px 7px;color:var(--ink-2)}
.people li{transition:background .3s ease,box-shadow .3s ease;border-radius:5px;
  scroll-margin-top:20px}
.people li.lit{background:var(--mark-bg);box-shadow:0 0 0 6px var(--mark-bg)}
.people .jump{display:inline-block;margin-top:5px;font-family:var(--f-label);font-size:9.5px;
  font-weight:600;letter-spacing:.07em;text-transform:uppercase;color:var(--secondary);
  background:none;border:none;padding:0;cursor:pointer}
.people .jump:hover{text-decoration:underline}

/* ---------- cite button + modal ---------- */
.citebtn{display:inline-flex;align-items:center;justify-content:center;gap:8px;width:100%;
  margin-top:14px;padding:11px 14px;cursor:pointer;background:var(--primary);color:#fff;border:none;
  border-radius:5px;font-family:var(--f-label);font-size:11px;font-weight:600;letter-spacing:.08em;
  text-transform:uppercase}
.citebtn:hover{background:#1B3B47}
.citebtn:focus-visible{outline:2px solid var(--secondary);outline-offset:3px}
.modal[hidden]{display:none}
.modal{position:fixed;inset:0;z-index:90;display:flex;align-items:center;justify-content:center;
  padding:24px;background:rgba(20,44,54,.55)}
.modal-box{background:#fff;border-radius:8px;width:min(620px,100%);max-height:82vh;overflow:auto;
  box-shadow:0 24px 60px rgba(16,40,50,.34);padding:26px 28px}
.modal-box h3{font-size:19px;letter-spacing:-.02em;margin-bottom:4px}
.modal-src{font-family:var(--f-label);font-size:10px;font-weight:600;letter-spacing:.09em;
  text-transform:uppercase;color:var(--ink-3);margin-bottom:16px}
.cite-out{font-family:var(--f-body);font-size:15px;line-height:1.62;color:var(--ink);
  background:var(--surface-2);border:1px solid var(--rule);border-radius:6px;padding:16px 18px;
  word-break:break-word}
.cite-out a{color:var(--secondary)}
.modal-acts{display:flex;gap:9px;margin-top:16px}
.modal-acts button{cursor:pointer;border-radius:5px;padding:9px 15px;font-family:var(--f-label);
  font-size:11px;font-weight:600;letter-spacing:.07em;text-transform:uppercase}
.btn-copy{background:var(--secondary);color:#fff;border:none}
.btn-close{background:#fff;color:var(--ink-2);border:1px solid var(--rule);margin-left:auto}
.btn-copy:focus-visible,.btn-close:focus-visible{outline:2px solid var(--primary);outline-offset:2px}

/* ---------- datacite panel ---------- */
.dc{border-color:var(--mark);background:#FBFCFE}
.dc-bar{display:flex;align-items:center;gap:9px;margin-bottom:13px}
.dc-bar h2{font-size:11px;font-family:var(--f-label);font-weight:500;letter-spacing:.12em;
  text-transform:uppercase;color:var(--mark);margin:0}
.dc-status{margin-left:auto;font-family:var(--f-label);font-size:9px;letter-spacing:.08em;
  text-transform:uppercase;padding:2px 7px;border-radius:99px;border:1px solid var(--rule);color:var(--ink-3)}
.dc-status[data-s="live"]{color:#0B6B4F;border-color:#9AD3BE;background:#EAF7F1}
.endpoint{font-family:var(--f-label);font-size:10px;color:var(--ink-2);background:var(--surface-2);
  border:1px solid var(--rule-2);border-radius:4px;padding:7px 9px;margin-bottom:14px;word-break:break-all}
.dl{margin:0;font-size:13.5px}
.dl div{display:grid;grid-template-columns:96px minmax(0,1fr);gap:12px;padding:8px 0;
  border-top:1px solid var(--rule-2)}
.dl div:first-child{border-top:none}
.dl dt{font-family:var(--f-label);font-size:9.5px;letter-spacing:.08em;text-transform:uppercase;
  color:var(--ink-3);padding-top:3px}
.dl dd{margin:0;line-height:1.5}

@media (max-width:940px){
  .masthead,.actions,.d-grid{grid-template-columns:minmax(0,1fr);gap:26px}
  .shell{padding:0 20px}
  .callout{grid-template-columns:70px minmax(0,1fr);gap:16px}
  .books{gap:4px;padding:16px 5px 0}
  .book{height:158px;font-size:11px}
  .tip{width:min(310px,calc(100vw - 32px))}
}
@media (prefers-reduced-motion:reduce){*{transition:none!important}}
@media print{
  .site{border-bottom:2px solid var(--primary)}
  .page{display:block!important;padding:0 0 40px;break-after:page}
  body{background:#fff}
}
</style>
</head>
<body>

<header class="site">
  <div class="shell">
    <a class="brand" href="#" data-go="collection" onclick="return false"
       aria-label="American Geophysical Union — home">
      <span class="logo" role="img" aria-label="AGU — Advancing Earth and Space Sciences"></span>
    </a>
    <nav class="site-nav">
      <a href="#" id="nav-collection" data-go="collection" aria-current="page"
         onclick="return false">The Collection</a>
      <a href="https://agupubs.onlinelibrary.wiley.com/hub/journal/23335084/call-for-papers/si-2026-000577"
         target="_blank" rel="noopener">About the project</a>
      <a href="https://docs.google.com/forms/d/e/1FAIpQLSf0Tlb1a29C2I-lNyl8qf_1oG1tFBosYW5qGBBj70D42Nhn_w/viewform" target="_blank" rel="noopener">Nominate</a>
    </nav>
  </div>
</header>

<!-- ============ PAGE 1 ============ -->
<main class="page active" id="page-collection">
<div class="shell">

  <header class="masthead">
    <div>
      <h1>Impactful Datasets in the Earth, Space, and Environmental Sciences</h1>
      <p class="lede">The American Geophysical Union (AGU) is celebrating and highlighting the
      many impactful datasets that support the broad spectrum of research, analysis, and decision
      making by our community. The creation, stewardship, and use of these impactful datasets
      should be broadly recognized.</p>
    </div>
    <div class="tally">
      <div><b id="t-ds">0</b><span>Datasets</span></div>
      <div><b id="t-th">0</b><span>Discipline groups</span></div>
      <div><b id="t-nm">0</b><span>Nominators</span></div>
    </div>
  </header>

  <section class="actions">
    <div class="act btn-nominate">
      <div>
        <h3 style="font-size:18px;margin-bottom:8px">Know one we're missing?</h3>
        <p>Nominations stay open. It takes about ten minutes.</p>
      </div>
      <a class="cta" href="https://docs.google.com/forms/d/e/1FAIpQLSf0Tlb1a29C2I-lNyl8qf_1oG1tFBosYW5qGBBj70D42Nhn_w/viewform" target="_blank" rel="noopener">Nominate a dataset →</a>
    </div>
    <div class="act callout">
      <div class="thumb">FEATURE<br>IMAGE</div>
      <div>
        <h3>How this collection was built</h3>
        <p>The story behind the nominations — what the community chose, what surprised
        the editors, and what it says about how research data earns its keep.</p>
        <a class="readlink" href="https://agupubs.onlinelibrary.wiley.com/hub/journal/23335084/call-for-papers/si-2026-000577"
           target="_blank" rel="noopener">Read the article →</a>
      </div>
    </div>
  </section>

  <div class="searchbar">
      <span class="glyph" aria-hidden="true">&#9906;</span>
      <input id="q" type="search" autocomplete="off" spellcheck="false"
        aria-label="Search datasets by title, discipline, repository or nominator"
        placeholder="Search titles, disciplines, repositories, nominators…">
      <span class="count" id="q-count"></span>
      <button class="clear" id="q-clear" hidden>Clear</button>
  </div>
  <div class="legend" id="legend"></div>
  <div id="groups"></div>
    <div class="empty" id="empty" hidden>
      <p>No datasets match <b id="empty-q"></b>.</p>
      <p style="font-size:13.5px">Try a discipline group, a repository, or a nominator's name.</p>
      <button class="clear" style="margin-top:4px" onclick="document.getElementById('q-clear').click()">Clear search</button>
  </div>
</div>
</main>

<!-- ============ PAGE 2 ============ -->
<main class="page" id="page-detail">
<div class="shell">
  <button class="back" data-go="collection">← Back to the collection</button>

  <header class="d-head">
    <span class="chip"><i id="d-swatch"></i><span id="d-theme"></span></span>
    <h1 id="d-title"></h1>
    <div class="d-meta" id="d-meta"></div>
  </header>

  <div class="d-grid">
    <div>
      <section class="sec">
        <h2>What it is</h2>
        <p id="d-desc"></p>
      </section>

      <section class="sec">
        <h2>Why it was nominated</h2>
        <div id="d-just"></div>
      </section>

      <section class="sec" id="d-reuse-sec">
        <h2>How it has been reused</h2>
        <ol class="reuse" id="d-reuse"></ol>
        <div class="more" id="d-reuse-more"></div>
      </section>

      <section class="sec" id="d-refs-sec">
        <h2>Referenced in</h2>
        <ul class="refs" id="d-refs"></ul>
        <div class="more" id="d-refs-more"></div>
      </section>
    </div>

    <aside>
      <div class="card">
        <h2>Get the data</h2>
        <ul class="linklist" id="d-links"></ul>
        <button class="citebtn" id="citebtn" hidden>Cite this dataset</button>
      </div>

      <div class="card">
        <h2>Held by</h2>
        <div id="d-repo"></div>
      </div>

      <div class="card">
        <h2>Nominated by</h2>
        <ul class="people" id="d-people"></ul>
      </div>

      <div class="card dc" id="d-dc">
        <div class="dc-bar">
          <h2>DataCite record</h2>
          <span class="dc-status" id="dc-status" data-s="idle">idle</span>
        </div>
        <div class="endpoint" id="dc-endpoint"></div>
        <dl class="dl" id="dc-body"></dl>
      </div>
    </aside>
  </div>
</div>
</main>

<footer class="site-foot">
  <div class="shell">
    <span class="logo foot" aria-hidden="true"></span>
    <p>Impactful Datasets &middot; concept wireframe &middot; not for distribution</p>
  </div>
</footer>

<div class="modal" id="citemodal" role="dialog" aria-modal="true"
     aria-labelledby="cite-h" hidden>
  <div class="modal-box">
    <h3 id="cite-h">Cite this dataset</h3>
    <div class="modal-src" id="cite-src"></div>
    <div class="cite-out" id="cite-out"></div>
    <div class="modal-acts">
      <button class="btn-copy" id="cite-copy">Copy citation</button>
      <button class="btn-close" id="cite-close">Close</button>
    </div>
  </div>
</div>

<div class="tip" id="tip" role="tooltip" aria-hidden="true">
  <span class="tail"></span>
  <h4></h4>
  <dl></dl>
</div>

<script>
const DATA = __DATA__;
const THEME_LABEL = {}, THEME_VAR = {atmos:'--atmos',ocean:'--ocean',biosphere:'--biosphere',
  interior:'--interior',surface:'--surface-c',society:'--society',space:'--space',materials:'--materials'};
DATA.themes.forEach(t => THEME_LABEL[t.key] = t.label);
const css = k => getComputedStyle(document.documentElement).getPropertyValue(THEME_VAR[k]).trim();
const esc = s => (s==null?'':String(s)).replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
// Turn URLs inside already-escaped citation text into links. Safe because esc()
// has removed every angle bracket and quote before this runs.
const linkify = s => s.replace(/https?:\/\/[^\s,;)\]]+/g, u => {
  const trimmed = u.replace(/[.,;:)\]]+$/, '');
  const tail = u.slice(trimmed.length);
  return `<a href="${trimmed}" target="_blank" rel="noopener">${trimmed}</a>${tail}`;
});

/* ---- page 1 ---- */
const uniqNoms = new Set();
DATA.datasets.forEach(d => (d.nomNames||[]).forEach(n => uniqNoms.add(n)));
document.getElementById('t-ds').textContent = DATA.datasets.length;
document.getElementById('t-th').textContent = DATA.themes.length;
document.getElementById('t-nm').textContent = DATA.nominatorCount;

/* Books per shelf, by viewport. Phones get 10 so the spines stay wide enough to
   read and tap; the rows are rebuilt when the breakpoint changes. */
const ROW_SIZES = [[640, 10], [940, 14]];
const DEFAULT_ROW = 20;
const perRow = () => (ROW_SIZES.find(([w]) => window.innerWidth <= w) || [0, DEFAULT_ROW])[1];
const groups = document.getElementById('groups');
const INDEX = [];   // one entry per discipline: {key, sec, rows:[{row, books:[{el,hay}]}], chip}
const norm = s => (s==null?'':String(s))
  .normalize('NFD').replace(/[\u0300-\u036f]/g,'')      // fold accents: Martinez == Martínez
  .replace(/[\u2018\u2019\u02bc']/g,'')                 // drop apostrophes: earths == Earth's
  .replace(/[\u2013\u2014]/g,'-')                       // en/em dash -> hyphen
  .toLowerCase();

/* Each discipline is its own section. Books are uniform width, perRow() to a row;
   a group of 29 fills one row of 20 and a second of 9 on desktop, and the short row
   is left short rather than stretched or filled from the next discipline. */
DATA.themes.forEach(t => {
  const items = DATA.datasets.filter(d => d.theme === t.key);
  if (!items.length) return;
  const c = css(t.key);
  const sec = document.createElement('section');
  sec.className = 'group';
  sec.id = 'group-' + t.key;
  const entry = {key:t.key, sec, rows:[], books:[], chip:null, label:t.label};
  sec.innerHTML = `<div class="group-head"><span class="group-swatch" style="background:${c}"></span>
    <h3>${esc(t.label)}</h3></div>`;
  {
    items.forEach(d => {
      const b = document.createElement('button');
      b.className = 'book';
      b.style.background = c;
      b.setAttribute('aria-label', `${d.title} — open dataset`);
      b.innerHTML = `<span>${esc(d.title)}</span>`;
      b.addEventListener('click', () => openDataset(d.id));
      b.addEventListener('mouseenter', () => showTip(b, d, t.label));
      b.addEventListener('focus', () => showTip(b, d, t.label));
      b.addEventListener('mouseleave', hideTip);
      b.addEventListener('blur', hideTip);
      const hay = norm([
        d.title, t.label, d.repo,
        (d.nominators||[]).map(p => p.name).join(' '),
        (d.creators||[]).join(' '), (d.curators||[]).join(' ')
      ].filter(Boolean).join(' \u00b7 '));
      entry.books.push({el:b, hay});
    });
  }
  groups.appendChild(sec);
  INDEX.push(entry);
});

/* Lay out one discipline's books into rows of `n`, reusing the same button elements
   so listeners survive. `list` is the books to show, which during a search is the
   matching subset -- results are re-packed into full rows from the top, rather than
   left scattered across the rows they happened to start in. */
function buildRows(entry, list, n){
  entry.sec.querySelectorAll('.books').forEach(r => r.remove());
  entry.rows = [];
  for (let i = 0; i < list.length; i += n){
    const row = document.createElement('div');
    row.className = 'books';
    row.style.gridTemplateColumns = `repeat(${n},1fr)`;
    list.slice(i, i + n).forEach(bk => row.appendChild(bk.el));
    entry.rows.push(row);
    entry.sec.appendChild(row);
  }
}

let currentRow = perRow();
window.addEventListener('resize', () => {
  const n = perRow();
  if (n === currentRow) return;   // only relayout when the breakpoint actually changes
  currentRow = n;
  applyFilter();
  hideTip();
});

/* ---- discipline index doubles as navigation ---- */
const legend = document.getElementById('legend');
DATA.themes.forEach(t => {
  const n = DATA.datasets.filter(d => d.theme === t.key).length;
  if (!n) return;
  const b = document.createElement('button');
  b.style.background = css(t.key);
  b.innerHTML = `${esc(t.label)}<span class="c">${n}</span>`;
  const ie = INDEX.find(e => e.key === t.key);
  if (ie) ie.chip = b;
  b.addEventListener('click', () => {
    const sec = document.getElementById('group-' + t.key);
    if (!sec || sec.hidden) return;
    sec.scrollIntoView({behavior:'smooth', block:'start'});
    const first = sec.querySelector('.book');
    if (first) setTimeout(() => first.focus({preventScroll:true}), 380);
  });
  legend.appendChild(b);
});

/* ---- client-side search ---- */
const qEl = document.getElementById('q'), qCount = document.getElementById('q-count'),
      qClear = document.getElementById('q-clear'), emptyEl = document.getElementById('empty'),
      emptyQ = document.getElementById('empty-q');
const TOTAL = DATA.datasets.length;

function applyFilter(){
  const raw = qEl.value.trim();
  const terms = norm(raw).split(/\s+/).filter(Boolean);
  const active = terms.length > 0;
  const n = currentRow;
  let shown = 0;

  INDEX.forEach(entry => {
    const hits = active
      ? entry.books.filter(bk => terms.every(term => bk.hay.includes(term)))
      : entry.books;
    buildRows(entry, hits, n);         // re-packed: results always start a new row
    entry.sec.hidden = hits.length === 0;
    if (entry.chip){
      entry.chip.hidden = hits.length === 0;
      entry.chip.querySelector('.c').textContent = hits.length;
    }
    shown += hits.length;
  });

  qClear.hidden = !active;
  emptyQ.textContent = raw;
  emptyEl.hidden = shown > 0;
  qCount.textContent = active
    ? `${shown} of ${TOTAL} ${shown === 1 ? 'dataset' : 'datasets'}`
    : `${TOTAL} datasets`;
  hideTip();
}

qEl.addEventListener('input', applyFilter);
qEl.addEventListener('keydown', e => { if (e.key === 'Escape'){ qEl.value=''; applyFilter(); } });
qClear.addEventListener('click', () => { qEl.value=''; applyFilter(); qEl.focus(); });

/* ---- hover bubble ---- */
const tip = document.getElementById('tip');
const tipTitle = tip.querySelector('h4'), tipList = tip.querySelector('dl'), tipTail = tip.querySelector('.tail');
function showTip(el, d, themeLabel){
  const names = (d.nominators||[]).map(p => p.name).filter(Boolean);
  const repo = !d.repo ? 'Not recorded'
    : (/^https?:\/\//.test(d.repo) ? d.repo.replace(/^https?:\/\/(www\.)?/,'').replace(/\/$/,'') : d.repo);
  tipTitle.textContent = d.title;
  tipList.innerHTML =
    `<dt>Discipline</dt><dd>${esc(themeLabel)}</dd>` +
    `<dt>Repository</dt><dd>${esc(repo)}</dd>` +
    `<dt>Nominated by</dt><dd>${names.length ? esc(names.join(', ')) : 'Not recorded'}</dd>`;
  tip.classList.add('on');
  tip.setAttribute('aria-hidden','false');
  const r = el.getBoundingClientRect(), t = tip.getBoundingClientRect();
  const M = 12;
  let left = r.left + r.width/2 - t.width/2;
  left = Math.max(M, Math.min(left, window.innerWidth - t.width - M));
  const above = r.top - t.height - 12;
  const below = r.bottom + 12;
  const placeBelow = above < 60;
  tip.style.left = left + 'px';
  tip.style.top = (placeBelow ? below : above) + 'px';
  const tailX = Math.max(10, Math.min(r.left + r.width/2 - left - 5.5, t.width - 21));
  tipTail.style.left = tailX + 'px';
  tipTail.style.top = placeBelow ? '-5px' : 'auto';
  tipTail.style.bottom = placeBelow ? 'auto' : '-5px';
}
function hideTip(){ tip.classList.remove('on'); tip.setAttribute('aria-hidden','true'); }
window.addEventListener('scroll', hideTip, {passive:true});

/* ---- page 2 ---- */
function openDataset(id){
  const d = DATA.datasets.find(x => x.id === id) || DATA.datasets[0];
  const c = css(d.theme);
  document.getElementById('d-swatch').style.background = c;
  document.getElementById('d-theme').textContent = THEME_LABEL[d.theme];
  document.getElementById('d-title').textContent = d.title;

  const meta = [];
  if (d.doi) meta.push(`<span>DOI &nbsp;<b>${esc(d.doi.replace('https://doi.org/',''))}</b></span>`);
  meta.push(`<span>Nominated by &nbsp;<b>${d.nomCount}</b></span>`);
  if (d.refsTotal) meta.push(`<span>Cited in &nbsp;<b>${d.refsTotal}</b>&nbsp; publications</span>`);
  if (d.reuseTotal) meta.push(`<span>Reuse examples &nbsp;<b>${d.reuseTotal}</b></span>`);
  document.getElementById('d-meta').innerHTML = meta.join('');
  document.getElementById('d-desc').textContent = d.desc || 'No description supplied in the nomination.';

  // Match each justification block to the nominator who wrote it, so the reader
  // sees a name rather than "Nominator 2".
  const bySeq = {};
  (d.nominators||[]).forEach(p => { if (p.seq != null) bySeq[p.seq] = p; });
  const multi = (d.nominators||[]).length > 1;
  document.getElementById('d-just').innerHTML = (d.just||[]).map((j,i) => {
    const seq = j.seq || i+1;
    const who = bySeq[seq];
    const dims = (j.dims||[]).map(x => `<span class="dim">${esc(x.label)}</span>`).join('');
    const head = who && who.name
      ? `<button class="who" data-seq="${seq}" aria-label="Show ${esc(who.name)} under Nominated by">
           <span class="nm">${esc(who.name)}</span>${multi?`<span class="seq">Nominator ${seq}</span>`:''}
         </button>`
      : `<div class="who"><span class="nm">Nominator ${seq}</span></div>`;
    return `<div class="just">${head}
      <p>${esc(j.text)}</p>${dims?`<div class="dims">${dims}</div>`:''}</div>`;
  }).join('') || '<p>No justification recorded.</p>';

  const rs = document.getElementById('d-reuse-sec');
  if ((d.reuse||[]).length){
    rs.style.display='';
    document.getElementById('d-reuse').innerHTML = d.reuse.map(r => `<li>${esc(r)}</li>`).join('');
    document.getElementById('d-reuse-more').textContent =
      d.reuseTotal > d.reuse.length ? `+ ${d.reuseTotal - d.reuse.length} more in the record` : '';
  } else rs.style.display='none';

  const rf = document.getElementById('d-refs-sec');
  if ((d.refs||[]).length){
    rf.style.display='';
    document.getElementById('d-refs').innerHTML =
      d.refs.map(r => `<li>${linkify(esc(r))}</li>`).join('');
    document.getElementById('d-refs-more').textContent =
      d.refsTotal > d.refs.length ? `+ ${d.refsTotal - d.refs.length} more in the record` : '';
  } else rf.style.display='none';

  const links = [];
  if (d.doi) links.push(['DOI', d.doi]);
  (d.links||[]).forEach(u => links.push(['Site', u]));
  document.getElementById('d-links').innerHTML = links.length
    ? links.map(([k,u]) => `<li><a href="${esc(u)}" target="_blank" rel="noopener">
        <span>${esc(u.replace(/^https?:\/\//,''))}</span><span class="k">${k}</span></a></li>`).join('')
    : '<li style="padding:11px 0;color:var(--ink-3);font-size:13px">No link recorded</li>';

  const repoName = !d.repo ? 'Not recorded'
    : (/^https?:\/\//.test(d.repo) ? d.repo.replace(/^https?:\/\/(www\.)?/,'').replace(/\/$/,'') : d.repo);
  document.getElementById('d-repo').innerHTML =
    `<div style="font-size:15px;font-weight:600;letter-spacing:-.01em">${esc(repoName)}</div>`
    + ((d.curators||[]).length ? `<div style="font-size:12.5px;color:var(--ink-2);margin-top:6px">
        Curated by ${esc(d.curators.join('; '))}</div>` : '')
    + ((d.creators||[]).length ? `<div style="font-size:12.5px;color:var(--ink-2);margin-top:6px">
        Produced by ${esc(d.creators.join('; '))}</div>` : '');

  const hasJust = {};
  (d.just||[]).forEach((j,i) => { hasJust[j.seq || i+1] = true; });
  document.getElementById('d-people').innerHTML = (d.nominators||[]).map(p =>
    `<li id="nominator-${p.seq}"><b>${esc(p.name || 'Name withheld')}</b>
      ${p.affil ? `<span class="aff">${esc(p.affil)}</span>` : ''}
      ${p.orcid ? `<span class="oid">${esc(p.orcid)}</span>` : ''}
      ${hasJust[p.seq] ? `<button class="jump" data-jump="${p.seq}">Read their justification ↑</button>` : ''}
    </li>`).join('')
    || '<li style="color:var(--ink-3);font-size:13px">No nominator recorded</li>';

  // wire both directions of the link
  document.querySelectorAll('#d-just .who[data-seq]').forEach(b =>
    b.addEventListener('click', () => spotlight(document.getElementById('nominator-' + b.dataset.seq))));
  document.querySelectorAll('#d-people .jump').forEach(b =>
    b.addEventListener('click', () => {
      const head = document.querySelector(`#d-just .who[data-seq="${b.dataset.jump}"]`);
      if (head) spotlight(head.closest('.just'), head);
    }));

  citeDoi = d.doi ? d.doi.replace('https://doi.org/','') : null;
  citeBtn.hidden = !citeDoi;
  if (!citeModal.hidden) closeCite();

  loadDataCite(d);
  show('detail');
  window.scrollTo({top:0});
}

/* ---- scroll to a linked element and flash it ---- */
let litTimer;
function spotlight(el, focusEl){
  if (!el) return;
  el.scrollIntoView({behavior:'smooth', block:'center'});
  el.classList.add('lit');
  clearTimeout(litTimer);
  litTimer = setTimeout(() => el.classList.remove('lit'), 1800);
  if (focusEl) setTimeout(() => focusEl.focus({preventScroll:true}), 360);
}

/* ---- Cite this dataset (DOI Citation Formatter, APA / en-US) ---- */
const citeBtn = document.getElementById('citebtn'),
      citeModal = document.getElementById('citemodal'),
      citeOut = document.getElementById('cite-out'),
      citeSrc = document.getElementById('cite-src');
let citeDoi = null, lastFocus = null;

function openCite(){
  if (!citeDoi) return;
  lastFocus = document.activeElement;
  citeModal.hidden = false;
  citeSrc.textContent = 'APA · en-US · via citation.doi.org';
  citeOut.textContent = 'Building citation…';
  document.getElementById('cite-close').focus();
  const url = 'https://citation.doi.org/format?doi=' + encodeURIComponent(citeDoi)
            + '&style=apa&lang=en-US';
  const ctl = new AbortController();
  const timer = setTimeout(() => ctl.abort(), 8000);
  fetch(url, {signal: ctl.signal})
    .then(r => r.ok ? r.text() : Promise.reject(new Error('HTTP ' + r.status)))
    .then(txt => {
      clearTimeout(timer);
      const clean = txt.trim();
      citeOut.innerHTML = clean ? linkify(esc(clean)) : esc('No citation returned for this DOI.');
    })
    .catch(() => {
      clearTimeout(timer);
      citeSrc.textContent = 'Citation service unavailable';
      citeOut.innerHTML = `The citation formatter could not be reached. The DOI is
        <a href="https://doi.org/${esc(citeDoi)}" target="_blank" rel="noopener">${esc(citeDoi)}</a>.`;
    });
}
function closeCite(){
  citeModal.hidden = true;
  if (lastFocus) lastFocus.focus();
}
citeBtn.addEventListener('click', openCite);
document.getElementById('cite-close').addEventListener('click', closeCite);
citeModal.addEventListener('click', e => { if (e.target === citeModal) closeCite(); });
document.addEventListener('keydown', e => { if (e.key === 'Escape' && !citeModal.hidden) closeCite(); });
document.getElementById('cite-copy').addEventListener('click', e => {
  const txt = citeOut.textContent;
  const done = () => { e.target.textContent = 'Copied'; setTimeout(() => e.target.textContent = 'Copy citation', 1600); };
  if (navigator.clipboard) navigator.clipboard.writeText(txt).then(done).catch(() => {});
  else done();
});

/* ---- DataCite ---- */
function loadDataCite(d){
  const panel = document.getElementById('d-dc');
  if (!d.doi){ panel.style.display='none'; return; }
  panel.style.display='';
  const doi = d.doi.replace('https://doi.org/','');
  const url = 'https://api.datacite.org/dois/' + doi;
  const status = document.getElementById('dc-status');
  const body = document.getElementById('dc-body');
  document.getElementById('dc-endpoint').textContent = 'GET ' + url;
  status.dataset.s = 'idle'; status.textContent = 'fetching…';
  body.innerHTML = '<div><dt>Status</dt><dd>Calling the DataCite registry…</dd></div>';

  const rows = (pairs) => body.innerHTML = pairs
    .filter(([,v]) => v)
    .map(([k,v]) => `<div><dt>${esc(k)}</dt><dd>${v}</dd></div>`).join('');

  // If the registry can't be reached, drop the panel entirely rather than
  // falling back to our own record — the page should not imply registry
  // data it does not actually have.
  const fallback = () => { panel.style.display = 'none'; };

  const ctl = new AbortController();
  const timer = setTimeout(() => ctl.abort(), 6000);
  fetch(url, {headers:{'Accept':'application/vnd.api+json'}, signal:ctl.signal})
    .then(r => r.ok ? r.json() : Promise.reject(new Error('HTTP ' + r.status)))
    .then(j => {
      clearTimeout(timer);
      const a = j.data.attributes;
      status.dataset.s = 'live'; status.textContent = 'live from datacite';
      const authors = (a.creators||[]).map(c => esc(c.name)).slice(0,12);
      const relAll = (a.relatedIdentifiers||[])
        .filter(r => /Cites|IsCitedBy|IsReferencedBy|IsSupplementTo/i.test(r.relationType||''));
      const related = relAll.slice(0,6)
        .map(r => `<li>${esc(r.relationType)} · ${esc(r.relatedIdentifier)}</li>`);
      if (relAll.length > related.length)
        related.push(`<li style="color:var(--ink-3)">+ ${relAll.length - related.length} more in the registry</li>`);
      rows([
        ['Title', esc((a.titles||[{}])[0].title || d.title)],
        ['Authors', authors.length
          ? authors.join(', ') + ((a.creators||[]).length > 12 ? ` <span style="color:var(--ink-3)">+${a.creators.length-12} more</span>` : '')
          : '—'],
        ['Publisher', esc(a.publisher && a.publisher.name ? a.publisher.name : a.publisher)],
        ['Published', esc(a.publicationYear)],
        ['Type', esc((a.types||{}).resourceTypeGeneral)],
        ['Version', esc(a.version)],
        ['Citations', a.citationCount != null ? a.citationCount : null],
        [`Related works${relAll.length ? ` (${relAll.length})` : ''}`,
         related.length ? `<ul class="refs" style="margin-top:2px">${related.join('')}</ul>` : null],
      ]);
    })
    .catch(() => { clearTimeout(timer); fallback(); });
}

/* ---- routing ---- */
function show(which){
  document.querySelectorAll('.page').forEach(p => p.classList.toggle('active', p.id === 'page-' + which));
  const onCollection = which === 'collection';
  const navHome = document.getElementById('nav-collection');
  if (navHome) navHome.setAttribute('aria-current', onCollection ? 'page' : 'false');
}
document.querySelectorAll('[data-go]').forEach(b => b.addEventListener('click', () => {
  show(b.dataset.go);
  window.scrollTo({top:0});
}));
applyFilter();
openDataset(DATA.featured);
show('collection');
</script>
</body>
</html>
"""



LOGO = base64.b64encode(_logo_png()).decode()
out = (HTML.replace('__DATA__', json.dumps(DATA, ensure_ascii=False, separators=(',', ':')))
           .replace('__LOGO__', LOGO))
OUT.write_text(out, encoding='utf-8')
print(f'wrote {OUT}  ({len(out)/1024:.0f} KB, {len(DATA["datasets"])} datasets)')
