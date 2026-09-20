#!/usr/bin/env python3
"""QC diagnostic: estimate potential (anchor, positive, negative) triplets.

The comparison-pair dataset trains a similarity model from pairwise
judgments, not explicit triplets, but it is useful to know how many valid
triplets could in principle be derived from it (e.g. for a future
triplet-loss experiment or as a sanity check on how richly connected the
pair graph is). Reports three increasingly strict definitions of
"positive":

  Strategy 1 (layer-based):    positive = same layer;      negative = different layer AND different city
  Strategy 2 (city-based):     positive = same city;       negative = different city
  Strategy 3 (strict hierarchy): positive = same layer AND same city; negative = anything else

For each strategy, an anchor contributes len(positives) * len(negatives)
potential triplets.
"""

import argparse
import csv
import json
from pathlib import Path
from collections import defaultdict


def load_pairs(pairs_file: Path):
    with open(pairs_file, 'r') as f:
        return list(csv.DictReader(f))


def build_sample_graph(pairs):
    """Build, for each image, the set of other images it is paired with, bucketed by relationship type."""
    connections = defaultdict(lambda: {
        'same_layer_same_city': set(),
        'same_layer_diff_city': set(),
        'diff_layer_same_city': set(),
        'diff_layer_diff_city': set(),
    })
    sample_metadata = {}

    for pair in pairs:
        img1, img2 = pair['img1_path'], pair['img2_path']
        city1, city2 = pair['city1'], pair['city2']
        layer1, layer2 = pair['layer1'], pair['layer2']

        sample_metadata[img1] = {'city': city1, 'layer': layer1}
        sample_metadata[img2] = {'city': city2, 'layer': layer2}

        same_city, same_layer = (city1 == city2), (layer1 == layer2)
        if same_layer and same_city:
            rel_type = 'same_layer_same_city'
        elif same_layer and not same_city:
            rel_type = 'same_layer_diff_city'
        elif not same_layer and same_city:
            rel_type = 'diff_layer_same_city'
        else:
            rel_type = 'diff_layer_diff_city'

        connections[img1][rel_type].add(img2)
        connections[img2][rel_type].add(img1)

    return connections, sample_metadata


def analyze_triplets(connections, sample_metadata):
    print("\n" + "=" * 80)
    print("TRIPLET ANALYSIS")
    print("=" * 80)

    # Strategy 1: layer-based.
    print("\nStrategy 1: layer-based triplets")
    print("  positive = same layer (same or different city)")
    print("  negative = different layer AND different city")

    triplet_count_s1, anchors_with_triplets_s1 = 0, 0
    triplets_by_layer_s1 = defaultdict(int)
    for anchor, conns in connections.items():
        positives = conns['same_layer_same_city'] | conns['same_layer_diff_city']
        negatives = conns['diff_layer_diff_city']
        if positives and negatives:
            anchors_with_triplets_s1 += 1
            n = len(positives) * len(negatives)
            triplet_count_s1 += n
            triplets_by_layer_s1[sample_metadata[anchor]['layer']] += n

    print(f"\n  Anchors with valid triplets: {anchors_with_triplets_s1}")
    print(f"  Total potential triplets: {triplet_count_s1:,}")
    if anchors_with_triplets_s1:
        print(f"  Average triplets per anchor: {triplet_count_s1 / anchors_with_triplets_s1:.1f}")
    print("\n  Triplets per layer:")
    for layer in sorted(triplets_by_layer_s1.keys(), key=int):
        print(f"    Layer {layer}: {triplets_by_layer_s1[layer]:,}")

    # Strategy 2: city-based.
    print("\n" + "-" * 80)
    print("\nStrategy 2: city-based triplets")
    print("  positive = same city (same or different layer)")
    print("  negative = different city (same or different layer)")

    triplet_count_s2, anchors_with_triplets_s2 = 0, 0
    triplets_by_city_s2 = defaultdict(int)
    for anchor, conns in connections.items():
        positives = conns['same_layer_same_city'] | conns['diff_layer_same_city']
        negatives = conns['same_layer_diff_city'] | conns['diff_layer_diff_city']
        if positives and negatives:
            anchors_with_triplets_s2 += 1
            n = len(positives) * len(negatives)
            triplet_count_s2 += n
            triplets_by_city_s2[sample_metadata[anchor]['city']] += n

    print(f"\n  Anchors with valid triplets: {anchors_with_triplets_s2}")
    print(f"  Total potential triplets: {triplet_count_s2:,}")
    if anchors_with_triplets_s2:
        print(f"  Average triplets per anchor: {triplet_count_s2 / anchors_with_triplets_s2:.1f}")
    print("\n  Top 10 cities by triplet count:")
    for i, (city, count) in enumerate(sorted(triplets_by_city_s2.items(), key=lambda x: x[1], reverse=True)[:10], 1):
        print(f"    {i:2d}. {city:20s}: {count:,}")

    # Strategy 3: strict hierarchy.
    print("\n" + "-" * 80)
    print("\nStrategy 3: strict-hierarchy triplets")
    print("  positive = same layer AND same city")
    print("  negative = different layer OR different city")

    triplet_count_s3, anchors_with_triplets_s3 = 0, 0
    for anchor, conns in connections.items():
        positives = conns['same_layer_same_city']
        negatives = conns['same_layer_diff_city'] | conns['diff_layer_same_city'] | conns['diff_layer_diff_city']
        if positives and negatives:
            anchors_with_triplets_s3 += 1
            triplet_count_s3 += len(positives) * len(negatives)

    print(f"\n  Anchors with valid triplets: {anchors_with_triplets_s3}")
    print(f"  Total potential triplets: {triplet_count_s3:,}")
    if anchors_with_triplets_s3:
        print(f"  Average triplets per anchor: {triplet_count_s3 / anchors_with_triplets_s3:.1f}")

    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"\nTotal unique samples in dataset: {len(connections)}")
    print("\nPotential triplets by strategy:")
    print(f"  Strategy 1 (layer-based):      {triplet_count_s1:>12,}")
    print(f"  Strategy 2 (city-based):       {triplet_count_s2:>12,}")
    print(f"  Strategy 3 (strict hierarchy): {triplet_count_s3:>12,}")

    return {
        'total_samples': len(connections),
        'strategy1_layer_based': {
            'total_triplets': triplet_count_s1, 'anchors_with_triplets': anchors_with_triplets_s1,
            'triplets_by_layer': dict(triplets_by_layer_s1),
        },
        'strategy2_city_based': {
            'total_triplets': triplet_count_s2, 'anchors_with_triplets': anchors_with_triplets_s2,
            'triplets_by_city': dict(triplets_by_city_s2),
        },
        'strategy3_strict': {'total_triplets': triplet_count_s3, 'anchors_with_triplets': anchors_with_triplets_s3},
    }


def main():
    parser = argparse.ArgumentParser(description='Estimate potential similarity-learning triplets in the pair dataset')
    parser.add_argument('--pairs', type=Path, default=Path('../outputs/comparison_pairs.csv'))
    parser.add_argument('--output', type=Path, default=Path('../outputs/triplet_analysis.json'))
    args = parser.parse_args()

    print("=" * 80)
    print("TRIPLET ANALYSIS FOR METRIC LEARNING")
    print("=" * 80)

    pairs = load_pairs(args.pairs)
    print(f"\nTotal pairs loaded: {len(pairs)}")

    connections, sample_metadata = build_sample_graph(pairs)
    print(f"Total unique samples: {len(connections)}")

    results = analyze_triplets(connections, sample_metadata)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, 'w') as f:
        json.dump(results, f, indent=2)

    print(f"\nAnalysis complete. Results saved to: {args.output}")


if __name__ == "__main__":
    main()
