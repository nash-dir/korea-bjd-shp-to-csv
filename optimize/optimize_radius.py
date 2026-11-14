# -*- coding: utf-8 -*-
"""
================================================================================
 ground truth로 dongnae 반경(dnradius) 미세 조정 (실험용)
================================================================================
[기능]
ground truth 지점마다 투표해 반경을 조금씩 늘리거나 줄입니다.
  - 확장: 지점이 정답 법정동의 원(중심거리 - 반경 <= 0) 밖에 있으면 정답 법정동 +1
  - 축소: 정답이 아닌 법정동의 원 안에 있으면 그 법정동 -shrink_penalty
epoch마다 투표 합계 x 학습률만큼 반경을 바꾸고(1회 최대 ±0.5km, 최소 MIN_RADIUS),
학습률은 epoch마다 0.8배로 줄입니다.

[주의]
- 결과는 반드시 optimize.evaluate로 원본과 비교한 뒤에만 쓰십시오. 상위 읍면동의 원은
  하위 리 지점을 항상 포함하므로, 축소 투표가 읍면동 반경을 계속 줄이는 경향이 있습니다.
- dongnae 엔진(pip install "dongnae>=0.3.0")이 필요합니다.

[사용법]
python -m optimize.optimize_radius -d results/261102/dongnaeKR_261102.csv -o optimize/output/optimized.csv
================================================================================
"""

import argparse
import os
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor

import numpy as np
import pandas as pd

from optimize.evaluate import DEFAULT_GT, load_ground_truth

MIN_RADIUS = 0.05     # km
MAX_STEP = 0.5        # km, epoch당 최대 변화량
VOTE_SCALE = 0.001    # 투표 1표가 학습률 1.0에서 바꾸는 반경(km)
LR_DECAY = 0.8


def vote_point(engine, true_id, lat, lon, shrink_penalty, votes):
    """지점 하나의 확장/축소 투표를 votes(dict)에 더합니다. 반환: 'fn'·'fp' 건수."""
    stats = {'fn': 0, 'fp': 0}
    target = engine.get(true_id)
    if target is None:
        return stats
    if engine._dongnae_dist(lat, lon, target) > 0:
        votes[true_id] += 1.0
        stats['fn'] += 1
    for cand in engine.nearest(lat, lon, k=5, radius_km=10.0):
        if cand['dnid'] != true_id and cand['distance'] <= 0:
            votes[cand['dnid']] -= shrink_penalty
            stats['fp'] += 1
    return stats


def apply_votes(radii, votes, lr):
    """
    radii({dnid: km})에 투표를 반영한 새 dict를 반환합니다. (순수 함수)
    변화량은 투표 x lr x VOTE_SCALE, ±MAX_STEP으로 자르고 MIN_RADIUS 아래로는 내리지 않습니다.
    """
    out = dict(radii)
    for dnid, vote in votes.items():
        if dnid not in out:
            continue
        delta = max(-MAX_STEP, min(MAX_STEP, vote * lr * VOTE_SCALE))
        out[dnid] = round(max(MIN_RADIUS, out[dnid] + delta), 4)
    return out


def _work(args):
    engine, chunk, shrink_penalty = args
    votes = defaultdict(float)
    stats = {'fn': 0, 'fp': 0}
    for row in chunk.itertuples(index=False):
        s = vote_point(engine, row.dnid, row.lat, row.lon, shrink_penalty, votes)
        stats['fn'] += s['fn']
        stats['fp'] += s['fp']
    return votes, stats


def main(dataset, ground_truth, output_csv, epochs, lr, shrink_penalty, sample_frac, seed, workers):
    from dongnae import DongnaeEngine

    engine = DongnaeEngine(dataset)
    gt = load_ground_truth(ground_truth, sample_frac, seed)
    gt = gt[gt['dnid'].isin(engine._id_map)]
    print(f"[준비] 노드 {len(engine._dongnaes):,}개, 지점 {len(gt):,}개, 프로세스 {workers}개")

    radii = {d['dnid']: d['dnradius'] for d in engine._dongnaes}
    rng = np.random.default_rng(seed)
    for epoch in range(1, epochs + 1):
        order = rng.permutation(len(gt))
        chunks = [gt.iloc[idx] for idx in np.array_split(order, workers)]
        votes = defaultdict(float)
        stats = {'fn': 0, 'fp': 0}
        with ProcessPoolExecutor(max_workers=workers) as pool:
            for v, s in pool.map(_work, [(engine, c, shrink_penalty) for c in chunks]):
                for k, x in v.items():
                    votes[k] += x
                stats['fn'] += s['fn']
                stats['fp'] += s['fp']

        new = apply_votes(radii, votes, lr)
        changed = sum(1 for k in new if new[k] != radii[k])
        radii = new
        for d in engine._dongnaes:
            d['dnradius'] = radii[d['dnid']]
        print(f"[epoch {epoch}/{epochs}] FN={stats['fn']:,} FP={stats['fp']:,} 변경 {changed:,}개 lr={lr:.5f}")
        lr *= LR_DECAY

    # 원본의 다른 컬럼은 문자열 그대로 두고 dnradius만 바꿉니다.
    out = pd.read_csv(dataset, dtype=str, encoding='utf-8-sig')
    out['dnradius'] = out['dnid'].map(radii).map(lambda r: f"{r:.4f}".rstrip('0').rstrip('.'))
    os.makedirs(os.path.dirname(os.path.abspath(output_csv)), exist_ok=True)
    out.to_csv(output_csv, index=False, encoding='utf-8-sig')
    print(f"[완료] {output_csv}  (optimize.evaluate로 원본과 비교하세요)")


def build_parser():
    parser = argparse.ArgumentParser(description="ground truth로 dongnae 반경을 조정합니다 (실험용).")
    parser.add_argument("-d", "--dataset", required=True, help="원본 dongnae CSV")
    parser.add_argument("-o", "--output-csv", required=True, help="조정된 dongnae CSV 저장 경로")
    parser.add_argument("-g", "--ground-truth", default=DEFAULT_GT,
                        help=f"ground truth CSV (기본값: {DEFAULT_GT})")
    parser.add_argument("--epochs", type=int, default=5)
    parser.add_argument("--lr", type=float, default=0.005, help="초기 학습률 (기본값: 0.005)")
    parser.add_argument("--shrink-penalty", type=float, default=1.0,
                        help="축소 투표 가중치 (기본값: 1.0, 확장과 동일)")
    parser.add_argument("--sample-frac", type=float, default=1.0, help="사용할 ground truth 비율")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--workers", type=int, default=os.cpu_count() or 1)
    return parser


if __name__ == "__main__":
    args = build_parser().parse_args()
    main(args.dataset, args.ground_truth, args.output_csv, args.epochs, args.lr,
         args.shrink_penalty, args.sample_frac, args.seed, args.workers)
