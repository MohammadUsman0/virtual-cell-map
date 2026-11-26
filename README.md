# Virtual Cell Map

**Who is building AI models of the cell, how they do it, and where.**
An interactive, source-linked world map of the organisations working on AI virtual cells: perturbation
models, single-cell foundation and world models, imaging, spatial and patient models, mechanistic
simulation, and the data generators, funders and pharma programmes behind them.

**[Open the map →](https://mohammadusman0.github.io/virtual-cell-map/)**

For the papers and models themselves, see the companion
[single-cell foundation model catalogue](https://github.com/MohammadUsman0/single-cell-foundation-models).

## What is in it

Each organisation has a type, location, approach, models, an openness label, Virtual Cell Challenge
involvement where relevant, and **at least one linked source**. Every source is marked `primary`
(the organisation's own release, paper, repository or institute page) or `press` (trade or news coverage).

| File | Contents |
|---|---|
| [`data/organisations.json`](data/organisations.json) | The dataset: one record per organisation |
| [`data/vcc2026_candidates.json`](data/vcc2026_candidates.json) | Organisations seen only on the Virtual Cell Challenge 2026 leaderboard, kept off the map until their own virtual-cell work is confirmed |
| [`data/institutions.json`](data/institutions.json) | Generated: institutions and authors behind the catalogue's papers (see below) |
| [`site/template.html`](site/template.html) | The page (self-contained: D3, topojson and the basemap are inlined) |
| [`scripts/build.py`](scripts/build.py) | Validates `data/` and writes the site to `docs/` |
| [`scripts/fetch_institutions.py`](scripts/fetch_institutions.py) | Rebuilds `data/institutions.json` from the catalogue and OpenAlex |

## Two layers

- **Organisations**: the curated list above, compiled by hand from public sources.
- **Research groups from papers**: built from data. For every model, benchmark and interpretability study
  in the [single-cell foundation model catalogue](https://github.com/MohammadUsman0/single-cell-foundation-models),
  the authors' institutions and their locations come from [OpenAlex](https://openalex.org) (CC0). Each
  institution links to its papers in the catalogue and to its authors in OpenAlex. Counts are papers *in the
  catalogue*, not an institution's total output or a ranking, and they inherit OpenAlex's affiliation matching.
  Papers OpenAlex cannot match (mostly OpenReview-only and very recent preprints) are listed under `unmatched`.

```bash
python scripts/fetch_institutions.py    # refresh after the catalogue changes (optional: OPENALEX_KEY)
python scripts/build.py
```

## What it deliberately leaves out

- **Funding figures**: not shown, because they could not each be traced to a specific source.
- **Founding years** without a linked source.
- **Challenge ranks** outside the top 10 of the 2026 final leaderboard; taking part is not, on its own,
  evidence of ongoing virtual-cell work.

Entries with unresolved questions are marked ⚠ and listed in the "Not yet confirmed" section of the page.
This is an independent overview compiled from public sources, not an authoritative record, and it implies
no endorsement or ranking of anyone's work.

## Corrections and additions

Spotted an error, or want an organisation added, updated or removed?
[Open an issue](https://github.com/MohammadUsman0/virtual-cell-map/issues) with a link to a source.
To edit the data yourself, see [CONTRIBUTING](CONTRIBUTING.md).

```bash
python scripts/build.py          # validate data/ and rebuild docs/
```

## Licence

Data (`data/`, `docs/*.json`): [CC BY 4.0](LICENSE-DATA.md). Code: [MIT](LICENSE).
Basemap: [Natural Earth](https://www.naturalearthdata.com/) (public domain) via
[world-atlas](https://github.com/topojson/world-atlas); D3 and topojson-client are ISC-licensed.
