#!/usr/bin/env python3
"""Build data/institutions.json: the institutions and authors behind the papers in the
single-cell foundation model catalogue, from OpenAlex author affiliations.

    python scripts/fetch_institutions.py                       # catalogue from its website
    python scripts/fetch_institutions.py --catalogue ../github_repo/docs/data.json

Papers included: every catalogued model, plus benchmarks and interpretability studies (the work done
*with* models). Each paper is matched in OpenAlex by its published DOI first, then its preprint
(DOI or arXiv id). Institutions come from OpenAlex's affiliation matching and locations from its
institution records (ROR). Papers without an OpenAlex match are listed under "unmatched".
OpenAlex data is CC0. Set OPENALEX_KEY to use your own API key (optional; never commit it).
"""
import argparse
import collections
import datetime
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CATALOGUE_URL = "https://mohammadusman0.github.io/single-cell-foundation-models/data.json"
OUT = os.path.join(ROOT, "data", "institutions.json")
API = "https://api.openalex.org"
RESOURCE_TYPES = {"benchmark", "interpretability"}

DOI_RE = re.compile(r"(10\.\d{4,9}/[^\s?#]+)", re.I)
ARXIV_RE = re.compile(r"arxiv\.org/(?:abs|pdf|html)/(\d{4}\.\d{4,5})", re.I)
NATURE_RE = re.compile(r"nature\.com/articles/(s\d{5}-\d{3}-\d{5}-\w)", re.I)


def get(url, params):
    key = os.environ.get("OPENALEX_KEY", "").strip()
    if key:
        params = {**params, "api_key": key}
    full = f"{url}?{urllib.parse.urlencode(params)}"
    for attempt in range(4):
        try:
            req = urllib.request.Request(full, headers={"User-Agent": "virtual-cell-map/1.0"})
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.load(r)
        except Exception as e:  # network errors and 429s: back off and retry
            if attempt == 3:
                raise
            print(f"  retry after {e}", file=sys.stderr)
            time.sleep(5 * (attempt + 1))


def ids_of(entry):
    """Candidate DOIs, in order of preference (published version first)."""
    out = []
    for key in ("paper", "preprint"):
        url = (entry.get("links") or {}).get(key) or ""
        if m := ARXIV_RE.search(url):
            out.append(f"10.48550/arxiv.{m.group(1)}")
        elif m := DOI_RE.search(url):
            out.append(re.sub(r"(v\d+|\.full|\.abstract|\.pdf)+$", "", m.group(1).rstrip("/.")).lower())
        elif m := NATURE_RE.search(url):
            out.append(f"10.1038/{m.group(1)}".lower())
    return list(dict.fromkeys(out))


def works_by_doi(dois):
    found = {}
    for i in range(0, len(dois), 50):
        chunk = dois[i:i + 50]
        body = get(f"{API}/works", {"filter": "doi:" + "|".join(chunk), "per-page": 50,
                                    "select": "id,doi,publication_year,authorships"})
        for w in body.get("results", []):
            found[(w.get("doi") or "").replace("https://doi.org/", "").lower()] = w
    return found


def institutions_by_id(iids):
    out = {}
    for i in range(0, len(iids), 50):
        chunk = [x.rsplit("/", 1)[-1] for x in iids[i:i + 50]]
        body = get(f"{API}/institutions", {"filter": "openalex_id:" + "|".join(chunk), "per-page": 50,
                                           "select": "id,display_name,ror,country_code,type,geo"})
        for r in body.get("results", []):
            out[r["id"]] = r
    return out


def load_catalogue(src):
    if re.match(r"https?://", src):
        with urllib.request.urlopen(urllib.request.Request(src, headers={"User-Agent": "virtual-cell-map/1.0"})) as r:
            return json.load(r)
    with open(src, encoding="utf-8") as f:
        return json.load(f)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--catalogue", default=CATALOGUE_URL, help="data.json path or URL")
    args = ap.parse_args()

    cat = load_catalogue(args.catalogue)
    entries = [dict(e, _kind="model") for e in cat["models"]] + \
              [dict(e, _kind=e["type"]) for e in cat["resources"] if e.get("type") in RESOURCE_TYPES]
    print(f"{len(entries)} catalogue entries (models, benchmarks, interpretability studies)")

    wanted = {e["id"]: ids_of(e) for e in entries}
    first = works_by_doi(sorted({d[0] for d in wanted.values() if d}))
    second = works_by_doi(sorted({d[1] for d in wanted.values() if len(d) > 1 and d[0] not in first}))
    found = {**second, **first}

    papers, unmatched, inst, authors = [], [], {}, {}
    for e in entries:
        work = next((found[d] for d in wanted[e["id"]] if d in found), None)
        if not work:
            unmatched.append(e["id"])
            continue
        p = len(papers)
        papers.append({"id": e["id"], "kind": e["_kind"], "name": e.get("name") or "", "title": e["title"],
                       "year": e.get("year"), "group": e.get("category") or e.get("type"),
                       "openalex": work["id"].rsplit("/", 1)[-1]})
        for a in work.get("authorships") or []:
            au = a.get("author") or {}
            if not au.get("id"):
                continue
            aid = au["id"].rsplit("/", 1)[-1]
            authors.setdefault(aid, {"name": au.get("display_name") or a.get("raw_author_name") or "",
                                     "orcid": (au.get("orcid") or "").replace("https://orcid.org/", "")})
            for i in a.get("institutions") or []:
                if not i.get("id"):
                    continue
                rec = inst.setdefault(i["id"], {"papers": set(), "authors": {}})
                rec["papers"].add(p)
                rec["authors"].setdefault(aid, set()).add(p)

    meta = institutions_by_id(sorted(inst))
    a_index, a_list = {}, []
    out_inst, no_geo = [], 0
    for iid, rec in inst.items():
        m = meta.get(iid) or {}
        geo = m.get("geo") or {}
        if geo.get("latitude") is None:
            no_geo += 1
            continue
        auth = []
        for aid, ps in sorted(rec["authors"].items(), key=lambda kv: (-len(kv[1]), authors[kv[0]]["name"])):
            if aid not in a_index:
                a_index[aid] = len(a_list)
                a_list.append([aid, authors[aid]["name"], authors[aid]["orcid"]])
            auth.append([a_index[aid], sorted(ps)])
        out_inst.append({
            "id": iid.rsplit("/", 1)[-1], "name": m.get("display_name", ""),
            "ror": (m.get("ror") or "").replace("https://ror.org/", ""), "type": m.get("type") or "",
            "country": geo.get("country") or m.get("country_code") or "", "city": geo.get("city") or "",
            "lat": round(geo["latitude"], 3), "lon": round(geo["longitude"], 3),
            "papers": sorted(rec["papers"]), "authors": auth,
        })
    out_inst.sort(key=lambda r: (-len(r["papers"]), r["name"]))

    data = {
        "source": "OpenAlex author affiliations (CC0) for papers in the single-cell foundation model catalogue",
        "catalogue": "https://github.com/MohammadUsman0/single-cell-foundation-models",
        "catalogue_date": cat.get("generated", ""),
        "fetched": datetime.date.today().isoformat(),
        "catalogue_entries": dict(collections.Counter(e["_kind"] for e in entries)),
        "papers": papers, "unmatched": sorted(unmatched),
        "authors": a_list, "institutions": out_inst,
        "institutions_without_location": no_geo,
    }
    with open(OUT, "w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
        f.write("\n")
    print(f"matched {len(papers)}/{len(entries)} papers; {len(out_inst)} institutions with a location "
          f"({no_geo} without); {len(a_list)} authors -> {os.path.relpath(OUT, ROOT)}")


if __name__ == "__main__":
    main()
