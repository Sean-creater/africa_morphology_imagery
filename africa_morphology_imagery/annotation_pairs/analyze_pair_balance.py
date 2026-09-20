#!/usr/bin/env python3
"""QC diagnostic: detailed balance analysis of the generated comparison pairs.

Runs after `05_validate_pairs.py`'s pass/fail checks to give a fuller
picture of the pair network's structure: city participation, layer
participation, all 28 pairwise layer-combination counts, per-city layer
distribution unevenness, and pair-type same-city/different-city splits.
Useful for spotting subtler imbalances than the go/no-go checks in step 5
catch (e.g. one city dominating a particular layer combination).
"""

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path


def load_pairs(pairs_file: Path):
    with open(pairs_file, 'r') as f:
        return list(csv.DictReader(f))


def analyze_city_participation(pairs):
    print("\n" + "=" * 80)
    print("CITY PARTICIPATION ANALYSIS")
    print("=" * 80)

    city_counts = defaultdict(int)
    city_pair_types = defaultdict(lambda: defaultdict(int))

    for pair in pairs:
        city1, city2, ptype = pair['city1'], pair['city2'], pair['pair_type']
        city_counts[city1] += 1
        city_counts[city2] += 1
        city_pair_types[city1][ptype] += 1
        city_pair_types[city2][ptype] += 1

    sorted_cities = sorted(city_counts.items(), key=lambda x: x[1], reverse=True)
    avg = sum(city_counts.values()) / len(sorted_cities)

    print(f"\nTotal cities: {len(sorted_cities)}")
    print(f"Average participation: {avg:.1f}")
    print(f"Min participation: {sorted_cities[-1][1]}")
    print(f"Max participation: {sorted_cities[0][1]}")
    print(f"Std dev: {(sum((v - avg) ** 2 for v in city_counts.values()) / len(sorted_cities)) ** 0.5:.1f}")

    print("\nTop 10 cities:")
    for i, (city, count) in enumerate(sorted_cities[:10], 1):
        print(f"  {i:2d}. {city:20s}: {count:4d} pairs")

    print("\nBottom 10 cities:")
    for i, (city, count) in enumerate(sorted_cities[-10:], 1):
        print(f"  {i:2d}. {city:20s}: {count:4d} pairs")

    print("\nParticipation distribution:")
    for low, high in [(0, 150), (150, 200), (200, 250), (250, 300), (300, 400), (400, 500)]:
        count = sum(1 for c in city_counts.values() if low <= c < high)
        print(f"  {low:3d}-{high:3d}: {count:2d} cities")

    return {
        'city_counts': dict(city_counts),
        'city_pair_types': {k: dict(v) for k, v in city_pair_types.items()},
        'sorted_cities': sorted_cities,
    }


def analyze_layer_participation(pairs):
    print("\n" + "=" * 80)
    print("LAYER PARTICIPATION ANALYSIS")
    print("=" * 80)

    layer_counts = defaultdict(int)
    layer_pair_types = defaultdict(lambda: defaultdict(int))

    for pair in pairs:
        layer1, layer2, ptype = pair['layer1'], pair['layer2'], pair['pair_type']
        layer_counts[layer1] += 1
        layer_counts[layer2] += 1
        layer_pair_types[layer1][ptype] += 1
        layer_pair_types[layer2][ptype] += 1

    total = sum(layer_counts.values())
    avg = total / 8

    print(f"\nTotal participations: {total}")
    print(f"Average per layer: {avg:.1f}")
    print("\nLayer participation:")
    for layer in sorted(layer_counts.keys(), key=int):
        count = layer_counts[layer]
        diff = count - avg
        status = "OK" if abs(diff) < avg * 0.15 else "WARN"
        print(f"  [{status}] layer {layer}: {count:4d} ({count / total * 100:5.1f}%, diff: {diff:+6.1f})")

    print(f"\n{'Layer':<6} {'AA-same':<10} {'AA-cross':<10} {'AR-same':<10} {'AR-cross':<10} {'RR':<10}")
    print("-" * 70)
    for layer in sorted(layer_counts.keys(), key=int):
        aa_same = layer_pair_types[layer].get('anchor_anchor_same_layer', 0)
        aa_cross = layer_pair_types[layer].get('anchor_anchor_cross_layer', 0)
        ar_same = (layer_pair_types[layer].get('anchor_rep_same_layer_same_city', 0)
                   + layer_pair_types[layer].get('anchor_rep_same_layer_diff_city', 0))
        ar_cross = (layer_pair_types[layer].get('anchor_rep_cross_layer_same_city', 0)
                    + layer_pair_types[layer].get('anchor_rep_cross_layer_diff_city', 0))
        rr = (layer_pair_types[layer].get('rep_rep_within_city', 0)
              + layer_pair_types[layer].get('rep_rep_between_cities', 0))
        print(f"L{layer}     {aa_same:<10} {aa_cross:<10} {ar_same:<10} {ar_cross:<10} {rr:<10}")

    return {'layer_counts': dict(layer_counts), 'layer_pair_types': {k: dict(v) for k, v in layer_pair_types.items()}}


def analyze_layer_combinations(pairs):
    print("\n" + "=" * 80)
    print("LAYER COMBINATION ANALYSIS")
    print("=" * 80)

    layer_combo_counts = defaultdict(int)
    for pair in pairs:
        l1, l2 = sorted([pair['layer1'], pair['layer2']])
        layer_combo_counts[f"{l1}-{l2}"] += 1

    print("\nSame-layer pairs:")
    same_layer_total = 0
    for i in range(8):
        count = layer_combo_counts[f"{i}-{i}"]
        same_layer_total += count
        print(f"  Layer {i}-{i}: {count:4d} pairs")
    print(f"  Total same-layer: {same_layer_total}")

    print("\nCross-layer pairs (all 28 combinations):")
    print(f"{'Combo':<8} {'Count':<8} {'Combo':<8} {'Count':<8} {'Combo':<8} {'Count':<8} {'Combo':<8} {'Count':<8}")
    print("-" * 80)

    cross_layer_combos = [(f"{i}-{j}", layer_combo_counts[f"{i}-{j}"]) for i in range(8) for j in range(i + 1, 8)]
    for idx in range(0, len(cross_layer_combos), 4):
        row = cross_layer_combos[idx:idx + 4]
        print("  " + "".join(f"{combo:<8} {count:<8} " for combo, count in row))

    cross_layer_total = sum(count for _, count in cross_layer_combos)
    avg_cross = cross_layer_total / len(cross_layer_combos)
    print(f"\n  Total cross-layer: {cross_layer_total}")
    print(f"  Average per combo: {avg_cross:.1f}")

    print("\nCross-layer combinations > 20% above average:")
    for combo, count in cross_layer_combos:
        if count > avg_cross * 1.2:
            print(f"  {combo}: {count:4d} (+{(count - avg_cross) / avg_cross * 100:+5.1f}%)")

    print("\nCross-layer combinations > 20% below average:")
    for combo, count in cross_layer_combos:
        if count < avg_cross * 0.8:
            print(f"  {combo}: {count:4d} ({(count - avg_cross) / avg_cross * 100:+5.1f}%)")

    return {
        'layer_combo_counts': dict(layer_combo_counts),
        'same_layer_total': same_layer_total,
        'cross_layer_total': cross_layer_total,
        'cross_layer_avg': avg_cross,
    }


def analyze_city_layer_interaction(pairs):
    print("\n" + "=" * 80)
    print("CITY-LAYER INTERACTION ANALYSIS")
    print("=" * 80)

    city_layer_counts = defaultdict(lambda: defaultdict(int))
    for pair in pairs:
        city_layer_counts[pair['city1']][pair['layer1']] += 1
        city_layer_counts[pair['city2']][pair['layer2']] += 1

    print("\nCities with most uneven layer distribution (top 10):")
    city_layer_variance = []
    for city, layer_dist in city_layer_counts.items():
        if not layer_dist:
            continue
        counts = list(layer_dist.values())
        avg = sum(counts) / len(counts)
        variance = sum((c - avg) ** 2 for c in counts) / len(counts)
        city_layer_variance.append((city, variance, len(layer_dist), dict(layer_dist)))
    city_layer_variance.sort(key=lambda x: x[1], reverse=True)

    for i, (city, var, n_layers, dist) in enumerate(city_layer_variance[:10], 1):
        print(f"  {i:2d}. {city:20s}: variance={var:6.1f}, layers={n_layers}")
        layer_str = ", ".join(f"L{l}:{c}" for l, c in sorted(dist.items(), key=lambda x: int(x[0])))
        print(f"      {layer_str}")

    return {'city_layer_counts': {k: dict(v) for k, v in city_layer_counts.items()}}


def analyze_pair_type_distribution(pairs):
    print("\n" + "=" * 80)
    print("PAIR TYPE DISTRIBUTION")
    print("=" * 80)

    type_counts = defaultdict(int)
    type_same_diff = defaultdict(lambda: {'same_city': 0, 'diff_city': 0})

    for pair in pairs:
        ptype = pair['pair_type']
        type_counts[ptype] += 1
        key = 'same_city' if pair['city1'] == pair['city2'] else 'diff_city'
        type_same_diff[ptype][key] += 1

    total = sum(type_counts.values())
    print("\nPair type counts:")
    for ptype in sorted(type_counts.keys()):
        count = type_counts[ptype]
        print(f"  {ptype:40s}: {count:4d} ({count / total * 100:5.1f}%)")

    print("\nSame-city vs different-city breakdown:")
    for ptype in sorted(type_counts.keys()):
        same, diff = type_same_diff[ptype]['same_city'], type_same_diff[ptype]['diff_city']
        total_type = same + diff
        if total_type > 0:
            print(f"  {ptype:40s}: same={same:4d} ({same / total_type * 100:5.1f}%), "
                  f"diff={diff:4d} ({diff / total_type * 100:5.1f}%)")

    return {'type_counts': dict(type_counts), 'type_same_diff': {k: dict(v) for k, v in type_same_diff.items()}}


def main():
    parser = argparse.ArgumentParser(description='Detailed balance analysis of generated comparison pairs')
    parser.add_argument('--pairs', type=Path, default=Path('../outputs/comparison_pairs.csv'))
    parser.add_argument('--output', type=Path, default=Path('../outputs/balance_analysis.json'))
    args = parser.parse_args()

    print("=" * 80)
    print("PAIR BALANCE ANALYSIS")
    print("=" * 80)

    pairs = load_pairs(args.pairs)
    print(f"\nTotal pairs loaded: {len(pairs)}")

    results = {
        'total_pairs': len(pairs),
        'city_analysis': analyze_city_participation(pairs),
        'layer_analysis': analyze_layer_participation(pairs),
        'combo_analysis': analyze_layer_combinations(pairs),
        'interaction_analysis': analyze_city_layer_interaction(pairs),
        'type_analysis': analyze_pair_type_distribution(pairs),
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, 'w') as f:
        json.dump(results, f, indent=2)

    print(f"\nAnalysis complete. Results saved to: {args.output}")


if __name__ == "__main__":
    main()
