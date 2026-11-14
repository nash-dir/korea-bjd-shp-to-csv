# -*- coding: utf-8 -*-
"""
================================================================================
 dongnae 데이터 정확도 평가 (ground truth 기준)
================================================================================
[기능]
1. ground truth(법정동 폴리곤 내부 무작위 좌표)에서 표본을 뽑아, 각 dongnae CSV로
   nearest(k=3)를 돌려 맞혔는지 셉니다.
   - Top-1 : 1위가 정답 코드이거나 그 상위 읍면동(코드 앞 8자리 + '00')
   - Top-3 : 3위 안에 정답 코드가 정확히 포함
   상위 읍면동 노드와 하위 리 노드가 함께 들어 있어, 리 지점의 1위는 대개 상위
   읍면동이 됩니다. 그래서 Top-1은 상위 읍면동까지 정답으로 셉니다.
2. 여러 CSV를 비교할 때는 모든 CSV에 있는 코드의 지점만 씁니다(분모를 같게).
   폐지 코드처럼 일부 CSV에만 있는 코드의 지점은 제외되고, 건수가 출력됩니다.
3. 표본은 법정동마다 같은 개수의 점에서 뽑으므로 면적·인구 가중치가 없습니다.

[사용법]
python -m optimize.evaluate results/261102/dongnaeKR_261102.csv other.csv
================================================================================
"""

import argparse

import pandas as pd

DEFAULT_GT = 'optimize/output/ground_truth.csv'


def parent_code(code):
    """리 코드의 상위 읍면동 코드 (예: 4885025021 -> 4885025000). (순수 함수)"""
    return code[:8] + '00'


def judge(true_id, ranked_ids):
    """
    nearest 결과(ranked_ids, 가까운 순)를 채점합니다. (순수 함수)

    Returns:
        (top1_hit, top3_hit)
    """
    top1 = bool(ranked_ids) and ranked_ids[0] in (true_id, parent_code(true_id))
    top3 = true_id in ranked_ids[:3]
    return top1, top3


def load_ground_truth(path, sample_frac, seed):
    gt = pd.read_csv(path, dtype={'dnid': str})
    # 예전 형식(8자리 읍면동 코드)도 받아 줍니다.
    gt['dnid'] = gt['dnid'].where(gt['dnid'].str.len() == 10, gt['dnid'] + '00')
    if sample_frac < 1:
        gt = gt.sample(frac=sample_frac, random_state=seed)
    return gt.reset_index(drop=True)


def evaluate(engines, gt):
    """
    engines: {이름: DongnaeEngine}. 모든 엔진에 있는 코드의 지점만 채점합니다.

    Returns:
        ({이름: (top1, top3)}, 채점한 지점 수, 제외한 지점 수)
    """
    common = set.intersection(*({d['dnid'] for d in e._dongnaes} for e in engines.values()))
    used = gt[gt['dnid'].isin(common)]
    scores = {}
    for name, engine in engines.items():
        hit1 = hit3 = 0
        for row in used.itertuples(index=False):
            ranked = [d['dnid'] for d in engine.nearest(row.lat, row.lon, k=3)]
            t1, t3 = judge(row.dnid, ranked)
            hit1 += t1
            hit3 += t3
        n = len(used)
        scores[name] = (hit1 / n, hit3 / n)
    return scores, len(used), len(gt) - len(used)


def main(datasets, ground_truth, sample_frac, seed):
    from dongnae import DongnaeEngine

    gt = load_ground_truth(ground_truth, sample_frac, seed)
    engines = {path: DongnaeEngine(path) for path in datasets}
    scores, used, dropped = evaluate(engines, gt)

    print(f"[평가] 표본 {used:,}개 지점 (공통 코드가 아니어서 제외: {dropped:,}개)")
    for path, (top1, top3) in scores.items():
        print(f"  Top-1 {top1:6.2%}  Top-3 {top3:6.2%}  {path}")


def build_parser():
    parser = argparse.ArgumentParser(description="dongnae CSV의 정확도를 ground truth로 평가합니다.")
    parser.add_argument("datasets", nargs="+", help="평가할 dongnae CSV (여러 개면 비교)")
    parser.add_argument("-g", "--ground-truth", default=DEFAULT_GT,
                        help=f"ground truth CSV (기본값: {DEFAULT_GT})")
    parser.add_argument("--sample-frac", type=float, default=0.02,
                        help="평가에 쓸 ground truth 비율 (기본값: 0.02)")
    parser.add_argument("--seed", type=int, default=0, help="표본 추출 시드 (기본값: 0)")
    return parser


if __name__ == "__main__":
    args = build_parser().parse_args()
    main(args.datasets, args.ground_truth, args.sample_frac, args.seed)
