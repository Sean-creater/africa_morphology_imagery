# Africa Morphology Imagery

Constructs an image dataset for training and human-annotating an urban
morphology embedding model, from African cities' 250 m hexagonal grid cells.
For a stratified sample of grid cells per city, this downloads Sentinel-2
satellite imagery and renders three PNG visualization styles: building/road
outline only; satellite with a low-contrast black/dark-gray overlay
(`png_integrated`); and satellite with a high-contrast cyan/magenta overlay
(`png_integrated_CyanMagenta`), then builds an anchor-based pairwise
comparison dataset used to collect human similarity judgments. In the study
this dataset was collected for, the annotation pairs were rendered and
judged using `png_integrated` — the same style used as model input — rather
than the higher-contrast `png_integrated_CyanMagenta` style; both are
produced by this pipeline and either can be used for annotation.

## Upstream dependency

This pipeline reads per-city 250 m hexagonal grid cells with morphology
metrics already computed, produced by the companion
[`africa_morphology_metrics`](https://github.com/Sean-creater/africa_morphology_metrics)
pipeline. It does not compute morphology metrics itself and does not run
that pipeline; prepare its output first.

Expected input schema (a per-city grid shapefile plus a small CSV of
per-city file paths):

- **Per-city hex grid shapefile** (`{City}_grid_250m_hex_enriched_metrics_v15.shp`
  or equivalent): one row per 250 m hexagonal grid cell, with a `GridID`
  column and, for the sampling stage specifically, these three morphology
  columns:
  - `Mean_Squar` - mean building squareness (building shape regularity)
  - `BldgStrAM` - building-to-street alignment
  - `StrOrientS` - street orientation diversity (Shannon entropy of street bearings)
- **A city/path reference CSV** (see `data/reference/SampleCityPath.csv` for
  the schema actually used): `City, Country, Buildings_Path, Highways_Path,
  Grid_Path, All_Files_Present` — building-footprint and road-network vector
  files per city (also companion-pipeline outputs), used by the rendering
  stage to clip buildings/roads to each sampled cell.

## Downstream use

The rendered images and comparison-pair dataset feed a separate embedding
model training and comparison study (teacher/student similarity learning
from the human annotations collected over these pairs). That work is a
distinct, not-yet-published project; this repository does not depend on it
and stops at producing the image dataset and pair list.

## Pipeline stages

| # | Stage | Module | Input | Output |
|---|-------|--------|-------|--------|
| 1 | Candidate cell selection | `sampling.py` (`candidates` subcommand) | Per-city full hex grid shapefiles | `{City}_sampled_cells.shp` per city (uniform-random subset, capped at 200 cells) |
| 2 | Morphology-stratified sampling | `sampling.py` (`stratify` subcommand) | Stage 1 shapefiles | `SampleGridCell.csv`, `SamplingStatistics.csv` |
| 3 | Satellite imagery download | `satellite_download.py` | Stage 2 output + Earth Engine | `png_satellite_imagery/{City}/{GridID}.png` |
| 4 | Rendering | `render.py` | Stage 2 output, building/road vectors, satellite imagery | `png_street+building/`, `png_integrated/`, `png_integrated_CyanMagenta/` |
| 5 | Annotation-pair construction | `annotation_pairs/01`-`06` | `png_integrated/` | `comparison_pairs.csv`, `labeling_data/` |

Stages 1-2 are two passes of the same sampling problem, not independent
alternatives: Stage 1 draws a manageable uniform-random candidate pool per
city (so later stages don't need to hold every city's full grid in memory),
and Stage 2 reads that candidate pool and re-samples it by morphology so the
final dataset actually covers the range of building/street form rather than
whatever a uniform draw happened to include.

## Sampling methodology (`sampling.py`)

Stage 2 stratifies each city's candidate cells along three morphology
dimensions (`Mean_Squar`, `BldgStrAM`, `StrOrientS`), splitting each at its
city-specific median into low/high and combining the three binary splits
into 8 strata (IDs 0-7). Samples are drawn from each stratum in proportion
to its size, so rare morphological combinations are represented without
letting them dominate. The total number of cells drawn per city depends on
city size:

| Size category | Total grid cells | Quota |
|---|---|---|
| small | <= 500 | 55 |
| medium | 501 - 3000 | 115 |
| large | > 3000 | 180 |

(capped at the city's candidate-cell count if smaller). Across the sample
run recorded in `data/reference/SamplingStatistics.csv`, this drew 5,674
cells from 47 cities (156,378 total candidate cells, ~3.6% overall rate).

## Satellite imagery (`satellite_download.py`)

Downloads a cloud-filtered median RGB composite from Google Earth Engine's
`COPERNICUS/S2_SR_HARMONIZED` (Sentinel-2 Surface Reflectance, Harmonized)
collection for each sampled cell, masking cloud/cloud-shadow/cirrus pixels
via the Scene Classification Layer before compositing, then scaling
reflectance to 8-bit RGB.

**Authentication**: reads Earth Engine credentials from whatever the
environment already has via the standard interactive
`ee.Authenticate(auth_mode='notebook')` flow (or an already-configured
`~/.config/earthengine/` credential cache) — this code never reads or
embeds a service-account key file. `ee.Initialize()` (optionally with a
`--project-id`) is called directly; if it fails because the user has never
authenticated, the code prints the standard interactive authentication
command rather than falling back to any credential file.

## Rendering (`render.py`)

Clips each city's buildings and roads to every sampled hexagonal cell and
renders three PNG styles per cell:

1. **`png_street+building/{City}/{GridID}.png`** - white hexagon
   background, buildings (black) and roads (dark gray) only, no satellite
   imagery. A lightweight reference render that needs no Earth Engine
   access.
2. **`png_integrated/{City}/{GridID}.png`** - Sentinel-2 satellite
   background with a muted black-building/dark-gray-road overlay
   (DINOv2/DINOv3-style): the low-contrast overlay leaves satellite texture
   as the dominant visual signal. This is the style used both as model
   input and, in the study this pipeline was built for, as the human
   annotation image (see `annotation_pairs/`) — the same rendered image
   served both purposes there.
3. **`png_integrated_CyanMagenta/{City}/{GridID}.png`** - the same
   satellite background with a saturated cyan-building/magenta-road overlay
   instead, for cases where a higher-contrast, easier-to-read overlay is
   preferred for human annotation over matching the model-input style
   exactly.

Rendering decisions, and why they matter:

- **20 m buffer on satellite downloads.** Earth Engine's per-region GeoTIFF
  export can blur or clip pixels at the requested region's edge. Each
  satellite tile is downloaded for the hexagon buffered outward by 20 m,
  then the rendered axis limits are cropped back down to the exact hexagon
  bounding box — so the pixels that end up visible always come from the
  interior of the downloaded tile, never its own edge.
- **Antialiasing disabled** on the vector overlay layers, so building and
  road edges stay crisp, single-color pixels instead of being blurred into
  intermediate colors against the satellite background — both a cleaner
  training signal and more legible annotation images.
- **Z-order: satellite below roads below buildings.** Buildings are drawn
  on top of roads because that is what a true top-down view looks like
  (a building fully occludes any road beneath its footprint); drawing roads
  on top would show road lines cutting through buildings that don't exist
  in reality.
- **Road width 3.5** in the satellite-backed styles (vs. 1.5 in the
  satellite-free style), because a thin line becomes nearly invisible once
  it has to compete with real satellite texture.
- **Hexagon alpha mask applied after rendering**, not before: the vector
  overlay and satellite backdrop are rendered onto a full bounding-box
  canvas first, and only then is a rasterio-derived hexagon mask used to
  zero the alpha channel outside the true hexagon boundary. Masking before
  rendering would reintroduce the same edge artifacts the 20 m buffer
  strategy exists to avoid.

## Annotation-pair construction (`annotation_pairs/`)

A numbered pipeline (`01_build_city_index.py` through
`06_prepare_for_labeling.py`, run via `annotation_pairs/run_pipeline.sh`)
that builds a 5000-pair anchor-based comparison dataset for human
similarity annotation: ~480-720 per-city representative cells and 240
strictly layer-balanced global anchor cells (30 per morphological layer)
form a densely cross-connected pair network, giving efficient annotation
coverage without needing to compare all pairs of the full rendered set. See
`africa_morphology_imagery/annotation_pairs/README.md` for the full design
and per-type pair-count breakdown, and its `analyze_pair_balance.py` /
`analyze_triplets.py` for post-hoc QC diagnostics on the generated pairs.

## Installation

```bash
conda env create -f environment.yml
conda activate africa_morphology_imagery
# or: pip install -r requirements.txt
pip install -e .   # optional, for `import africa_morphology_imagery`
```

Google Earth Engine access additionally requires a one-time interactive
authentication (`python -c "import ee; ee.Authenticate(auth_mode='notebook')"`)
with a personal Google account registered for Earth Engine use, before
`satellite_download.py` or `render.py` (without `--no-satellite`) can run.

## Usage

```bash
# Stage 1: candidate cell selection
python -m africa_morphology_imagery.sampling candidates \
    --cities-csv data/reference/SampleCityPath.csv \
    --grid-glob-template "/path/to/{country}/{city}/Output/{city}_grid_250m_hex_enriched_metrics_v15.shp" \
    --output-shp-dir /path/to/output/shp

# Stage 2: morphology-stratified sampling
python -m africa_morphology_imagery.sampling stratify \
    --shp-dir /path/to/output/shp \
    --city-path-csv data/reference/SampleCityPath.csv \
    --output-csv /path/to/output/SampleGridCell.csv \
    --output-stats-csv /path/to/output/SamplingStatistics.csv

# Stage 3+4: satellite download + rendering (render.py downloads satellite imagery internally per cell)
python -m africa_morphology_imagery.render \
    --city-path-csv data/reference/SampleCityPath.csv \
    --grid-cells-dir /path/to/output/shp \
    --metadata-csv /path/to/output/SampleGridCell.csv \
    --output-dir /path/to/output/images

# Stage 5: annotation pairs
cd africa_morphology_imagery/annotation_pairs
bash run_pipeline.sh /path/to/output/images/png_integrated
```

`satellite_download.py` can also be run standalone to pre-populate an
imagery cache; see its `--help`.

## Output schema

### `SampleGridCell.csv` (Stage 2 output; see `data/reference/` for a real example)

| Column | Meaning |
|---|---|
| `GridID` | Unique cell identifier |
| `City`, `Country` | |
| `CRS` | Cell geometry's coordinate reference system |
| `Center_X`, `Center_Y` | Cell centroid, in `CRS` units |
| `Stratum_ID` | Combined 0-7 morphology stratum |
| `Stratum_Shape`, `Stratum_Alignment`, `Stratum_Diversity` | Per-dimension low(0)/high(1) split |
| `Mean_Squar`, `BldgStrAM`, `StrOrientS` | Raw morphology values |

### Rendered image directories

```
{output-dir}/
  png_street+building/{City}/{GridID}[_{StratumID}].png
  png_integrated/{City}/{GridID}[_{StratumID}].png
  png_integrated_CyanMagenta/{City}/{GridID}[_{StratumID}].png
  png_satellite_imagery/{City}/{GridID}.png   # raw satellite cache, if kept
```

See `data/example/images/` for a handful of real (non-synthetic) images
across all three styles, from one small city (Apam, Ghana).

### `comparison_pairs.csv` (annotation-pair output)

Columns: `pair_id, img1_path, img2_path, pair_type, layer1, layer2, city1,
city2, is_anchor_pair`. See `data/example/annotation_pair/` for one real
example pair, and `annotation_pairs/README.md` for the full pair-type
breakdown.

## Repository layout

```
africa_morphology_imagery/
  README.md
  environment.yml / requirements.txt
  pyproject.toml
  africa_morphology_imagery/
    sampling.py              # Stages 1-2: candidate selection + stratified sampling
    satellite_download.py    # Stage 3: Sentinel-2 download via Earth Engine
    render.py                # Stage 4: the 3 rendered PNG styles
    annotation_pairs/        # Stage 5: numbered anchor-based pair-generation pipeline
  data/
    reference/                # small durable config: city lists, sampling statistics
    example/                  # a handful of real example images + one annotation pair
```

## License

No LICENSE file is included. The source `Dataset_construction` project this
was extracted from does not carry one either, so none is asserted here;
add one before distributing this code further.
