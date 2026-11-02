# -*- coding: utf-8 -*-
"""
================================================================================
 좌표 병합 CSV에 수작업 보정(revisions/manual_revisions.csv) 적용
================================================================================
[기능]
1. bjd_csv_to_fulladdress.py 결과물(LSCT_LAWDCD_coords_...csv)을 로드합니다.
2. 모든 행에 Exception 라벨을 붙입니다.
   - '1' Historical : 폐지된 법정동 (DEL_DT 기재)
   - '2' Aggregated : 시도·시군구 단위 상위행정구역 (UMD_NM 없음)
   - '0' Valid      : 그 외
3. 보정 명세(manual_revisions.csv)의 행은 명세대로 덮어씁니다.
   - none   : 좌표 없음 (예: 미수복지역)
   - copy   : source 법정동의 중심좌표·반경을 그대로 사용 (예: 행정동 중첩)
   - proxy  : 대체좌표(주민센터 등)를 쓰고, radius_km는 명세 값 또는
              source 법정동들의 radius_km 평균
   - manual : 명세의 중심좌표·반경을 그대로 사용
   copy·proxy의 반경은 실행 시점의 계산값에서 다시 구하므로, 반경 계산 방식이
   바뀌어도 보정 행이 옛 값에 머무르지 않습니다.
4. 결과를 저장합니다 (보정 행의 filename은 'manual_revisions.csv').

[사용법]
python bjd_csv_apply_revisions.py -i LSCT_LAWDCD_coords_YYMMDD.csv -o LSCT_LAWDCD_coords_YYMMDD_revised.csv
================================================================================
"""

import argparse
import os

import pandas as pd

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
REVISIONS_CSV = os.path.join(BASE_DIR, 'revisions', 'manual_revisions.csv')

COORD_COLUMNS = ['center_latitude', 'center_longitude', 'radius_km']
METHODS = ('none', 'copy', 'proxy', 'manual')


def _blank(value):
    return pd.isna(value) or str(value).strip() == ''


def base_labels(df):
    """폐지(1) / 상위행정구역(2) / 정상(0) 라벨을 계산합니다. (순수 함수)"""
    deleted = df['DEL_DT'].notna() & (df['DEL_DT'].astype(str).str.strip() != '')
    aggregated = df['UMD_NM'].isna() | (df['UMD_NM'].astype(str).str.strip() == '')
    labels = pd.Series('0', index=df.index)
    labels[aggregated] = '2'
    labels[deleted] = '1'
    return labels


def apply_revisions(df, spec):
    """
    좌표 병합 DataFrame에 보정 명세를 적용합니다. (순수 함수, 모든 값은 str)

    Returns:
        (보정된 DataFrame, 계산된 좌표를 명세로 덮어쓴 LAWD_CD 목록)
    """
    out = df.copy()
    out['Exception'] = base_labels(out)
    pos = {code: i for i, code in enumerate(out['LAWD_CD'])}
    revised = set(spec['LAWD_CD'])

    def coords_of(code):
        if code not in pos:
            raise ValueError(f"source 법정동이 없습니다: {code}")
        if code in revised:
            raise ValueError(f"source 법정동이 다시 보정 대상입니다(순서 의존): {code}")
        row = out.iloc[pos[code]]
        if _blank(row['center_latitude']):
            raise ValueError(f"source 법정동에 좌표가 없습니다: {code}")
        return row

    overridden = []
    for rev in spec.itertuples(index=False):
        if rev.method not in METHODS:
            raise ValueError(f"알 수 없는 method '{rev.method}': {rev.LAWD_CD}")
        if rev.LAWD_CD not in pos:
            raise ValueError(f"보정 대상 법정동이 없습니다: {rev.LAWD_CD}")
        i = pos[rev.LAWD_CD]
        if not _blank(out.iloc[i]['center_latitude']) and rev.method != 'none':
            overridden.append(rev.LAWD_CD)

        sources = [] if _blank(rev.source) else str(rev.source).split()
        if rev.method == 'none':
            values = [None, None, None]
        elif rev.method == 'copy':
            src = coords_of(sources[0])
            values = [src[c] for c in COORD_COLUMNS]
        else:  # proxy, manual
            if _blank(rev.radius_km):
                radii = pd.to_numeric(pd.Series([coords_of(s)['radius_km'] for s in sources]))
                radius = f"{radii.mean():.3f}"
            else:
                radius = rev.radius_km
            values = [rev.center_latitude, rev.center_longitude, radius]

        for col, value in zip(COORD_COLUMNS, values):
            out.iat[i, out.columns.get_loc(col)] = value
        out.iat[i, out.columns.get_loc('filename')] = (
            None if rev.method == 'none' else 'manual_revisions.csv')
        out.iat[i, out.columns.get_loc('Exception')] = str(rev.Exception)

    return out, overridden


def main(input_csv, output_csv, revisions_csv=REVISIONS_CSV):
    # 코드/좌표 문자열을 그대로 보존하기 위해 전부 str로 읽습니다.
    df = pd.read_csv(input_csv, dtype=str, encoding='utf-8-sig')
    spec = pd.read_csv(revisions_csv, dtype=str, encoding='utf-8-sig')
    out, overridden = apply_revisions(df, spec)
    out.to_csv(output_csv, index=False, encoding='utf-8-sig')

    print(f"[완료] 보정 {len(spec)}건 적용: {output_csv}")
    print("  - Exception 분포: " + ", ".join(
        f"{k}={v}" for k, v in sorted(out['Exception'].value_counts().items())))
    if overridden:
        # 원천 shp가 고쳐져 계산값이 생긴 경우: 명세가 아직 필요한지 검토 대상
        print(f"  - [확인 필요] 계산된 좌표를 명세로 덮어씀: {overridden}")


def build_parser():
    parser = argparse.ArgumentParser(
        description="좌표 병합 CSV에 Exception 라벨과 수작업 보정(manual_revisions.csv)을 적용합니다."
    )
    parser.add_argument("-i", "--input-csv", required=True,
                        help="bjd_csv_to_fulladdress.py 결과물 (LSCT_LAWDCD_coords_...csv)")
    parser.add_argument("-o", "--output-csv", required=True,
                        help="저장할 보정 결과 CSV")
    parser.add_argument("-r", "--revisions-csv", default=REVISIONS_CSV,
                        help="보정 명세 (기본값: revisions/manual_revisions.csv)")
    return parser


if __name__ == "__main__":
    args = build_parser().parse_args()
    main(input_csv=args.input_csv, output_csv=args.output_csv, revisions_csv=args.revisions_csv)
