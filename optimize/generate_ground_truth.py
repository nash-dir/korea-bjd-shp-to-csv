# -*- coding: utf-8 -*-
"""
================================================================================
 법정동 폴리곤 내부 무작위 좌표(ground truth) 생성
================================================================================
[기능]
1. input 폴더의 법정동 shp(RI/UMD)를 읽어, 법정동마다 폴리곤 내부의 무작위 좌표를
   --per-dong개씩 뽑습니다. 각 좌표의 정답 라벨은 그 법정동 코드입니다.
2. bjd_geometry_to_csv.py와 같은 기준으로 정리합니다.
   - 코드는 10자리 표준 코드(8자리 읍면동 코드에 '00' 패딩). dongnae 데이터의 dnid와
     같아야 평가·최적화에서 매칭됩니다.
   - 떨어진 조각(원천 데이터 오류)은 샘플링에서 제외합니다.
3. 미터 좌표계(EPSG:5179)에서 균일하게 뽑은 뒤 위경도(EPSG:4326)로 저장합니다.
   --seed가 같으면 결과도 같습니다.

[사용법]
python -m optimize.generate_ground_truth -i input -o optimize/output/ground_truth.csv
================================================================================
"""

import argparse
import glob
import os
import re

import numpy as np
import pandas as pd

from bjd_geometry_to_csv import (
    CODE_CANDIDATES,
    SHP_ENCODING,
    drop_stray_parts,
    find_column,
    pad_code,
)

_CODE_PATTERN = re.compile(r'^\d{8}$|^\d{10}$')
MAX_ROUNDS = 20  # 폴리곤 면적이 bbox에 비해 아주 작을 때의 무한 루프 방지


def sample_points(geom, n, rng):
    """
    폴리곤 내부의 균일 무작위 좌표 n개를 (x, y) 배열로 반환합니다. (순수 함수)
    bbox에서 뽑아 내부만 남기는 rejection sampling이며, MAX_ROUNDS 안에 다 못 채우면
    채운 만큼만 반환합니다.
    """
    import shapely

    if geom is None or geom.is_empty or n <= 0:
        return np.empty((0, 2))
    shapely.prepare(geom)
    minx, miny, maxx, maxy = geom.bounds
    # 폴리곤이 bbox를 차지하는 비율만큼 넉넉히 뽑는다
    fill = max(geom.area / max((maxx - minx) * (maxy - miny), 1e-12), 0.01)
    found = []
    have = 0
    for _ in range(MAX_ROUNDS):
        batch = int((n - have) / fill * 1.2) + 16
        x = rng.uniform(minx, maxx, batch)
        y = rng.uniform(miny, maxy, batch)
        inside = shapely.contains_xy(geom, x, y)
        found.append(np.column_stack([x[inside], y[inside]]))
        have += int(inside.sum())
        if have >= n:
            break
    return np.concatenate(found)[:n]


def generate(input_dir, per_dong, seed, encoding=SHP_ENCODING):
    """input_dir의 모든 shp에서 ground truth DataFrame(dnid, lat, lon)을 만듭니다."""
    import geopandas as gpd
    from tqdm import tqdm

    rng = np.random.default_rng(seed)
    frames = []
    skipped = 0
    for path in tqdm(sorted(glob.glob(os.path.join(input_dir, '*.shp'))), desc="shp"):
        gdf = gpd.read_file(path, encoding=encoding).to_crs(epsg=5179)
        code_col = find_column(gdf.columns, CODE_CANDIDATES)
        if not code_col:
            print(f"\n[경고] {os.path.basename(path)}: 코드 컬럼이 없어 건너뜁니다.")
            continue
        for code, geom in zip(gdf[code_col].astype(str).str.strip(), gdf.geometry):
            if not _CODE_PATTERN.match(code):
                skipped += 1
                continue
            cleaned, _ = drop_stray_parts(geom)
            xy = sample_points(cleaned, per_dong, rng)
            if len(xy):
                frames.append(pd.DataFrame({'dnid': pad_code(code), 'x': xy[:, 0], 'y': xy[:, 1]}))

    df = pd.concat(frames, ignore_index=True)
    pts = gpd.GeoSeries(gpd.points_from_xy(df['x'], df['y']), crs=5179).to_crs(epsg=4326)
    out = pd.DataFrame({'dnid': df['dnid'], 'lat': pts.y.round(7), 'lon': pts.x.round(7)})
    return out, skipped


def main(input_dir, output_csv, per_dong, seed):
    out, skipped = generate(input_dir, per_dong, seed)
    os.makedirs(os.path.dirname(os.path.abspath(output_csv)), exist_ok=True)
    out.to_csv(output_csv, index=False, encoding='utf-8')
    print(f"[완료] {out['dnid'].nunique():,}개 법정동, {len(out):,}개 좌표: {output_csv}")
    if skipped:
        print(f"  - 코드 형식 오류로 제외한 도형: {skipped}건")


def build_parser():
    parser = argparse.ArgumentParser(description="법정동 폴리곤 내부 무작위 좌표(ground truth)를 생성합니다.")
    parser.add_argument("-i", "--input-dir", default="input", help="shp 폴더 (기본값: input)")
    parser.add_argument("-o", "--output-csv", default="optimize/output/ground_truth.csv",
                        help="저장 경로 (기본값: optimize/output/ground_truth.csv)")
    parser.add_argument("-n", "--per-dong", type=int, default=50, help="법정동당 좌표 수 (기본값: 50)")
    parser.add_argument("--seed", type=int, default=0, help="난수 시드 (기본값: 0)")
    return parser


if __name__ == "__main__":
    args = build_parser().parse_args()
    main(args.input_dir, args.output_csv, args.per_dong, args.seed)
