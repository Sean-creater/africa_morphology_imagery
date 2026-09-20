# Anchor-Based Comparison-Pair Generation

Generates 5000 image pairs for human urban-morphology similarity annotation,
using an anchor-based sampling strategy over the rendered `png_integrated`
cells from `render.py`.

## Design Philosophy

Instead of uniform sampling across all rendered grid cells, this uses a
two-tier structure:

1. **City representatives (~480-720 cells)**: selected from each city,
   allocated across 8 morphological layers (0-7) in proportion to a fixed
   target layer distribution.
2. **Global anchors (240 cells)**: a subset of representatives forming the
   "skeleton" of the morphological space — 30 anchors per layer, with a
   target regional balance (North/West/East/Central/Southern Africa) within
   each layer.

This design gives:
- High information density (anchors participate in many pairs each)
- Structural propagation through a densely-connected anchor network
- Computational feasibility (5000 pairs instead of the ~10^11 possible
  pairs over the full rendered set)
- Geographic and morphological balance

"Layer" here is the same 8-way morphology stratum (`Stratum_ID`, 0-7)
computed by `sampling.py`'s stratified sampling stage, encoded as the last
underscore-separated token in each rendered filename
(e.g. `GHA_0063_000107_5.png` -> layer 5).

## Pipeline Steps

### 1. Build city index (`01_build_city_index.py`)

Scans each city's `png_integrated/{City}/*.png` files and groups them by
layer. Output: `outputs/city_index.json`,
`{city: {layer: [file_path, ...]}}`.

### 2. Select city representatives (`02_select_representatives.py`)

Selects up to 12 representatives per city (fewer for very small cities),
allocated across layers proportional to a fixed target distribution rather
than equally, so that a city's naturally sparser layers don't get
artificially inflated relative to its denser ones. Output:
`outputs/city_representatives.json`.

### 3. Select global anchors (`03_select_anchors.py`)

Selects 240 anchors: exactly 30 per layer, with a target regional split
within each layer (North Africa 6, West Africa 7, East Africa 8, Central
Africa 4, Southern Africa 5). Output: `outputs/global_anchors.json`.

### 4. Generate comparison pairs (`04_generate_pairs.py`)

Creates 5000 pairs across three types:

- **Type 1: Anchor x Anchor (2400 pairs)**
  - 1a. Same-layer (960 = 8 layers x 120/layer, forced equal): 70%
    cross-city / 30% same-city.
  - 1b. Cross-layer (1440 = 28 layer combinations, ~35-70 pairs/combination
    depending on how many anchors each layer has).
- **Type 2: Anchor x Representative (1800 pairs)**
  - Same layer, same city (450); same layer, different city (450);
    cross layer, same city (450); cross layer, different city (450).
- **Type 3: Representative x Representative (800 pairs)**
  - Within-city (400): captures intra-city gradients.
  - Between-cities (400): adds network flexibility, avoids rigid structure.

All pairs are globally deduplicated (order-independent) as they are
generated. Output: `outputs/comparison_pairs.csv`, columns `pair_id,
img1_path, img2_path, pair_type, layer1, layer2, city1, city2,
is_anchor_pair`.

### 5. Validate pairs (`05_validate_pairs.py`)

Checks total count, per-type distribution, layer/city balance, duplicate
pairs, and (on a sample) that referenced image files exist.

### 6. Prepare for labeling (`06_prepare_for_labeling.py`)

Packages pairs for an annotation interface: one folder per pair containing
both images, grouped into fixed-size batches (200 pairs/batch) as JSON,
plus a master index and an annotator-facing README with the 1-5 similarity
scale.

## Usage

```bash
cd africa_morphology_imagery/annotation_pairs
bash run_pipeline.sh /path/to/png_integrated
```

or step by step:

```bash
python3 01_build_city_index.py --png-dir /path/to/png_integrated
python3 02_select_representatives.py
python3 03_select_anchors.py
python3 04_generate_pairs.py
python3 05_validate_pairs.py
python3 06_prepare_for_labeling.py
```

Each script also accepts `--help` for its input/output path overrides; by
default they read/write relative to `../outputs/` and `../city_list.txt`.

## QC Diagnostics

- `analyze_pair_balance.py`: city/layer participation, all 28 layer-combo
  counts, per-city layer-distribution unevenness, pair-type same/diff-city
  splits.
- `analyze_triplets.py`: estimates how many (anchor, positive, negative)
  triplets could be derived from the pair graph under three increasingly
  strict similarity definitions — informational only, not required for the
  pairwise-annotation pipeline itself.

## Requirements

Python 3.7+, standard library only (no third-party dependencies for this
subpackage).

## Notes

- Random seed 42 throughout, for reproducibility.
- Cities with a missing or not-yet-rendered `png_integrated` directory are
  skipped gracefully; downstream targets are not automatically rescaled to
  compensate, so a materially incomplete city set will under-shoot the pair
  count targets (step 5 flags deviations bigger than ~150 pairs from the
  5000 target).
- Small deviations from per-type targets are normal artifacts of pool
  exhaustion (e.g. very small pools can't always hit their exact quota);
  step 5's validation checks flag deviations worth investigating rather
  than treating any deviation as an error.
