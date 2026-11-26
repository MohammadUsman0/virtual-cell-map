#!/usr/bin/env python3
"""Validate data/ and build the site in docs/. No dependencies beyond the standard library.

    python scripts/build.py          # validate, then write docs/
    python scripts/build.py --check  # validate and fail if docs/ is out of date (used in CI)
"""
import collections
import datetime
import json
import math
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO = "https://github.com/MohammadUsman0/virtual-cell-map"
CATALOGUE = "https://mohammadusman0.github.io/single-cell-foundation-models/"

FIELDS = {
    "id", "name", "type", "category", "city", "country", "metro", "lat", "lon", "founded", "founded_source",
    "website", "approach", "data", "summary", "models", "open_release", "openness_detail", "pharma_partners",
    "virtual_cell_challenge", "sources", "context_note", "needs_verification", "last_checked",
}
REQUIRED = ["id", "name", "type", "category", "city", "country", "metro", "lat", "lon", "summary", "sources", "last_checked"]
OPEN = {"Yes", "Partial", "No", "—"}
QUALITY = {"primary", "press"}
URL = re.compile(r"^https?://\S+$")
DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def load(name):
    with open(os.path.join(ROOT, "data", name), encoding="utf-8") as f:
        return json.load(f)


def validate(orgs, cats):
    errors, seen = [], set()
    for i, o in enumerate(orgs):
        where = o.get("id") or f"record {i}"
        for k in REQUIRED:
            if o.get(k) in (None, "", []):
                errors.append(f"{where}: missing {k}")
        for k in set(o) - FIELDS:
            errors.append(f"{where}: unknown field {k!r}")
        if o.get("id") in seen:
            errors.append(f"{where}: duplicate id")
        seen.add(o.get("id"))
        if o.get("id") and not re.fullmatch(r"[a-z0-9][a-z0-9-]*", o["id"]):
            errors.append(f"{where}: id must be lowercase letters, digits and hyphens")
        if o.get("category") not in cats:
            errors.append(f"{where}: category {o.get('category')!r} not in {cats}")
        if o.get("open_release", "—") not in OPEN:
            errors.append(f"{where}: open_release must be one of {sorted(OPEN)}")
        if o.get("founded") and not o.get("founded_source"):
            errors.append(f"{where}: founded year needs founded_source")
        if o.get("founded_source") and not URL.match(o["founded_source"]):
            errors.append(f"{where}: founded_source is not a URL")
        if not DATE.match(str(o.get("last_checked", ""))):
            errors.append(f"{where}: last_checked must be YYYY-MM-DD")
        if not (-90 <= float(o.get("lat", 0)) <= 90 and -180 <= float(o.get("lon", 0)) <= 180):
            errors.append(f"{where}: lat/lon out of range")
        if not isinstance(o.get("pharma_partners", []), list):
            errors.append(f"{where}: pharma_partners must be a list")
        for s in o.get("sources") or []:
            if not URL.match(s.get("url", "")):
                errors.append(f"{where}: source URL {s.get('url')!r} is not a URL")
            if s.get("quality") not in QUALITY:
                errors.append(f"{where}: source quality must be one of {sorted(QUALITY)}")
            if not s.get("supports"):
                errors.append(f"{where}: source {s.get('url')} needs 'supports'")
    return errors


def nice_date(iso):
    d = datetime.date.fromisoformat(iso)
    return f"{d.day} {d:%b %Y}"


def km(a, b):
    la1, lo1, la2, lo2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    h = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    return 12742 * math.asin(math.sqrt(h))


# Area names that match the organisations layer, for bubbles whose largest city is not the usual name.
HUB_NAMES = {
    ("Stanford", "United States"): "SF Bay Area",
    ("San Francisco", "United States"): "SF Bay Area",
    ("Cambridge", "United States"): "Boston area",
    ("Boston", "United States"): "Boston area",
    ("Cambridge", "United Kingdom"): "Cambridge (UK)",
}


def group_cities(labs, radius=60):
    """Give each institution a map bubble: cities within `radius` km of a bigger city join its bubble."""
    cities = {}
    for i in labs["institutions"]:
        c = cities.setdefault((i["city"], i["country"]), {"n": 0, "lat": i["lat"], "lon": i["lon"]})
        c["n"] += len(i["papers"])
    hubs = []
    for key, c in sorted(cities.items(), key=lambda kv: (-kv[1]["n"], kv[0])):
        hub = next((h for h in hubs if km((h["lat"], h["lon"]), (c["lat"], c["lon"])) <= radius), None)
        if hub:
            hub["members"].append(key)
        else:
            hubs.append({"name": key[0] or key[1], "country": key[1], "lat": c["lat"], "lon": c["lon"], "members": [key]})
    names = collections.Counter(h["name"] for h in hubs)
    where = {}
    for h in hubs:
        label = h["name"] + (" area" if len(h["members"]) > 1 else "")
        if names[h["name"]] > 1:
            label += f" ({h['country']})"
        label = HUB_NAMES.get((h["name"], h["country"]), label)
        for key in h["members"]:
            where[key] = (label, h["lat"], h["lon"])
    for i in labs["institutions"]:
        i["metro"], i["mlat"], i["mlon"] = where[(i["city"], i["country"])]
    return labs


def render(orgs, cands, labs):
    tpl = open(os.path.join(ROOT, "site", "template.html"), encoding="utf-8").read()
    last = max(o["last_checked"] for o in orgs)
    countries = {c.strip() for o in orgs for c in o["country"].split("/")}
    data = json.dumps(orgs, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    values = {
        "DATA": data,
        "N_ORGS": len(orgs),
        "N_CITIES": len({o["metro"] for o in orgs}),
        "N_COUNTRIES": len(countries),
        "N_SOURCES": sum(len(o["sources"]) for o in orgs),
        "N_OPEN": sum(1 for o in orgs if o.get("needs_verification")),
        "N_CAND": sum(1 for c in cands["candidates"] if not c.get("status", "").startswith("Added to map")),
        "DATE": nice_date(last),
        "REPO": REPO,
        "CATALOGUE": CATALOGUE,
        "LABS": json.dumps(labs, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/"),
        "N_INST": len(labs["institutions"]),
        "N_PAPERS": len(labs["papers"]),
        "N_LABPAPERS": len(labs["papers"]) + len(labs["unmatched"]),
        "LABS_DATE": nice_date(labs["catalogue_date"]),
        "LABS_FETCHED": nice_date(labs["fetched"]),
    }
    out = re.sub(r"\{\{(\w+)\}\}", lambda m: str(values[m.group(1)]), tpl)
    left = re.findall(r"\{\{\w+\}\}", out)
    if left:
        sys.exit(f"unfilled placeholders: {left}")
    return out


def main():
    check = "--check" in sys.argv
    orgs, cands = load("organisations.json"), load("vcc2026_candidates.json")
    tpl = open(os.path.join(ROOT, "site", "template.html"), encoding="utf-8").read()
    cats = json.loads(re.search(r"const CATS=(\[.*?\]);", tpl).group(1))
    errors = validate(orgs, cats)
    if errors:
        print("\n".join(errors))
        sys.exit(f"{len(errors)} error(s)")
    orgs = sorted(orgs, key=lambda o: o["name"].lower())
    labs = group_cities(load("institutions.json"))
    files = {
        "docs/index.html": render(orgs, cands, labs),
        "docs/institutions.json": json.dumps(load("institutions.json"), ensure_ascii=False, indent=1) + "\n",
        "docs/organisations.json": json.dumps(orgs, ensure_ascii=False, indent=2) + "\n",
        "docs/vcc2026_candidates.json": json.dumps(cands, ensure_ascii=False, indent=1) + "\n",
        "docs/.nojekyll": "",
    }
    stale = []
    for path, text in files.items():
        full = os.path.join(ROOT, path)
        old = open(full, encoding="utf-8").read() if os.path.exists(full) else None
        if old != text:
            stale.append(path)
            if not check:
                with open(full, "w", encoding="utf-8", newline="\n") as f:
                    f.write(text)
    if check and stale:
        sys.exit(f"docs/ is out of date ({', '.join(stale)}): run python scripts/build.py")
    print(f"OK: {len(orgs)} organisations, {sum(len(o['sources']) for o in orgs)} sources"
          + (f"; wrote {', '.join(stale)}" if stale and not check else "; docs/ up to date"))


if __name__ == "__main__":
    main()
