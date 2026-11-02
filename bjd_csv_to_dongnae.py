# -*- coding: utf-8 -*-
"""
================================================================================
 좌표 병합 CSV(LSCT_LAWDCD_coords_...) -> dongnae 엔진용 CSV 변환
================================================================================
[기능]
1. bjd_csv_to_fulladdress.py 결과물(LSCT_LAWDCD_coords_...csv)을 로드합니다.
2. 다음 행은 제외합니다.
   - 중심좌표가 없는 행 (지오메트리 없음, 상위행정구역 등)
   - 폐지된 법정동 (DEL_DT 기재). 구 코드 shp가 input에 남아 있으면 폐지 코드에도
     좌표가 붙는데(예: 2024. 1. 전라북도(45) -> 전북특별자치도(52) 개편), 이를
     그대로 내보내면 같은 지역이 신·구 코드로 중복됩니다.
3. dongnae 스키마(dnid, dnname, dnlatitude, dnlongitude, dnradius)로 저장합니다.
   - dnid = LAWD_CD, dnname = full_address, dnradius = radius_km
4. (선택) --fallback-csv: 새로 계산한 결과에 좌표가 없는 행은 이전 결과물(예: 수동 보정된
   ..._revised_verified.csv)의 좌표로 채웁니다. shp에 지오메트리가 없어 수동 입력한
   행(Exception 4·5 등)을 재생성 때마다 잃지 않기 위함입니다.

[사용법]
python bjd_csv_to_dongnae.py -i LSCT_LAWDCD_coords_YYMMDD.csv -o dongnaeKR_YYMMDD.csv
python bjd_csv_to_dongnae.py -i LSCT_LAWDCD_coords_YYMMDD.csv -o dongnaeKR_YYMMDD.csv -f 이전_revised_verified.csv
================================================================================
"""

import argparse

import pandas as pd

# --fallback-csv로 채우는 좌표 컬럼
COORD_COLUMNS = ['center_latitude', 'center_longitude', 'radius_km']

# 입력 컬럼 -> dongnae 컬럼
COLUMN_MAP = {
    'LAWD_CD': 'dnid',
    'full_address': 'dnname',
    'center_latitude': 'dnlatitude',
    'center_longitude': 'dnlongitude',
    'radius_km': 'dnradius',
}


def fill_missing_coords(df, fallback):
    """
    df에서 좌표가 없는 행을 fallback(같은 LAWD_CD)의 좌표로 채웁니다. (순수 함수)

    Returns:
        (채워진 DataFrame, 채운 건수)
    """
    fb = fallback.dropna(subset=['center_latitude']).drop_duplicates('LAWD_CD').set_index('LAWD_CD')
    out = df.copy()
    target = out['center_latitude'].isna() & out['LAWD_CD'].isin(fb.index)
    for col in COORD_COLUMNS:
        out.loc[target, col] = out.loc[target, 'LAWD_CD'].map(fb[col]).values
    return out, int(target.sum())


def to_dongnae(df):
    """
    좌표 병합 DataFrame을 dongnae 스키마로 변환합니다. (순수 함수)

    Returns:
        (dongnae DataFrame, 제외 사유별 건수 dict)
    """
    missing = [col for col in [*COLUMN_MAP, 'DEL_DT'] if col not in df.columns]
    if missing:
        raise ValueError(f"입력에 필수 컬럼이 없습니다: {missing}")

    has_coords = df['center_latitude'].notna() & df['center_longitude'].notna()
    deleted = df['DEL_DT'].notna() & (df['DEL_DT'].astype(str).str.strip() != '')

    keep = has_coords & ~deleted
    stats = {
        'no_coords': int((~has_coords).sum()),
        'deleted_with_coords': int((has_coords & deleted).sum()),
    }

    out = df.loc[keep, list(COLUMN_MAP)].rename(columns=COLUMN_MAP)

    dup = out['dnid'].duplicated(keep=False)
    if dup.any():
        raise ValueError(f"dnid 중복 {int(dup.sum())}건: {out.loc[dup, 'dnid'].unique()[:5].tolist()}")

    return out.reset_index(drop=True), stats


def main(input_csv, output_csv, fallback_csv=None):
    # 코드/좌표 문자열을 그대로 보존하기 위해 전부 str로 읽습니다(반올림·지수표기 방지).
    df = pd.read_csv(input_csv, dtype=str, encoding='utf-8-sig')
    filled = 0
    if fallback_csv:
        fallback = pd.read_csv(fallback_csv, dtype=str, encoding='utf-8-sig')
        df, filled = fill_missing_coords(df, fallback)
    out, stats = to_dongnae(df)
    out.to_csv(output_csv, index=False, encoding='utf-8-sig')

    print(f"[완료] {len(out)}건 저장: {output_csv}")
    if fallback_csv:
        print(f"  - 이전 결과물 좌표로 채움: {filled}건")
    print(f"  - 제외(좌표 없음): {stats['no_coords']}건")
    print(f"  - 제외(폐지 법정동인데 좌표 있음): {stats['deleted_with_coords']}건")


def build_parser():
    parser = argparse.ArgumentParser(
        description="좌표 병합 CSV를 dongnae 엔진용 CSV(dnid, dnname, dnlatitude, dnlongitude, dnradius)로 변환합니다."
    )
    parser.add_argument("-i", "--input-csv", required=True,
                        help="bjd_csv_to_fulladdress.py 결과물 (LSCT_LAWDCD_coords_...csv)")
    parser.add_argument("-o", "--output-csv", required=True,
                        help="저장할 dongnae CSV 경로")
    parser.add_argument("-f", "--fallback-csv", default=None,
                        help="좌표가 없는 행을 채울 이전 결과물 (예: 수동 보정된 ..._revised_verified.csv)")
    return parser


if __name__ == "__main__":
    args = build_parser().parse_args()
    main(input_csv=args.input_csv, output_csv=args.output_csv, fallback_csv=args.fallback_csv)
