# -*- coding: utf-8 -*-
"""
================================================================================
 법정동 코드 마스터(LSCT_LAWDCD.csv)에 좌표 데이터(bjd_..._result.csv) 병합
================================================================================
[기능]
1. 'LSCT_LAWDCD.csv' (법정동 전체 코드)를 기본 데이터로 로드합니다.
   - (예외처리) 정부 데이터 특성상 'euc-kr' 인코딩일 수 있으므로, 'utf-8-sig' 실패 시
     'euc-kr'로 자동 재시도합니다.
2. [v2] 'SIDO_NM', 'SGG_NM', 'UMD_NM', 'RI_NM' 컬럼을 조합하여 'full_address' 컬럼을 생성합니다.
   - NaN 값을 제외하고 텍스트를 조합하며, 중간의 연속 공백/앞뒤 공백을 제거합니다.
   - 생성된 'full_address' 컬럼을 'RI_NM' 열 바로 뒤로 이동시킵니다.
3. 'bjd_251117_2212_result.csv' (좌표 데이터)를 추가 데이터로 로드합니다.
4. 좌표 데이터에서 'legal_dong_code' 기준 중복이 있다면 첫 번째 행만 남깁니다.
5. 'LSCT_LAWDCD.csv'를 기준으로 Left Join을 수행합니다.
   - (매칭 키) 'LAWD_CD' (좌) == 'legal_dong_code' (우)
6. 결과물을 'LSCT_LAWDCD_coords.csv'로 저장합니다.
   - (파일명 처리) 동일 파일명 존재 시 'LSCT_LAWDCD_coords-1.csv', 
     'LSCT_LAWDCD_coords-2.csv' ... 와 같이 숫자를 붙여 저장합니다.
================================================================================
"""

import pandas as pd
import os
import re

# --- 설정 영역 ---

# 1. 기본(좌측)이 될 법정동 코드 전체 파일
BASE_FILE = 'LSCT_LAWDCD.csv'

# 2. Join(우측)할 좌표 데이터 파일 (사용자가 업로드한 파일명 기준)
DATA_FILE = 'bjd_251117_2212_result.csv'

# 3. 저장될 결과 파일명 (확장자 제외)
OUTPUT_NAME = 'LSCT_LAWDCD_coords'

# 4. DATA_FILE에서 가져올 컬럼 목록
# (SGG_OID 포함, 요청하신 6개 컬럼 + 매칭키 1개)
COLUMNS_TO_JOIN = [
    'legal_dong_code',
    'COL_ADM_SECT_CD',
    'center_latitude',
    'center_longitude',
    'radius_km',
    'filename',
    'SGG_OID'
]

# 5. [v2] 'full_address'를 구성할 컬럼 순서
ADDRESS_COMPONENTS = ['SIDO_NM', 'SGG_NM', 'UMD_NM', 'RI_NM']

# --- ---

def get_unique_filename(base_name, extension):
    """
    저장할 파일명을 확인하고, 중복 시 '-n' 형식의 접미사를 붙여 반환합니다.
    (예: 'file.csv' -> 'file-1.csv' -> 'file-2.csv')
    """
    counter = 1
    # 첫 번째 시도는 -1이 아닌 오리지널 파일명
    output_path = f"{base_name}{extension}"
    
    # 파일이 존재할 경우에만 -n 접미사 시작
    if os.path.exists(output_path):
        while True:
            output_path = f"{base_name}-{counter}{extension}"
            if not os.path.exists(output_path):
                break
            counter += 1
        
    return output_path

def create_full_address(df_base, components):
    """
    [v2] df_base에서 주소 구성요소 컬럼을 조합하여 'full_address'를 생성하고 삽입합니다.
    """
    print(f"  > 'full_address' 생성 작업 시작...")
    
    # 1. df_base에 존재하는 주소 구성요소 컬럼만 필터링
    existing_components = [col for col in components if col in df_base.columns]
    
    if not existing_components:
        print(f"  > (경고) 'full_address' 생성을 위한 주소 컬럼({components})이(가) 없습니다.")
        return df_base # 원본 반환

    print(f"  > (정보) 주소 조합 대상: {existing_components}")

    # 2. NaN 값을 빈 문자열('')로 채우고, 각 컬럼을 문자열(str)로 변환
    df_temp_address = df_base[existing_components].fillna('').astype(str)

    # 3. 각 행(axis=1)에 대해 ' '.join 수행
    #    (예: "서울특별시", "", "종로동", "") -> "서울특별시  종로동 "
    temp_address_series = df_temp_address.apply(' '.join, axis=1)

    # 4. 정규표현식으로 공백 정리
    #   - r'\s+': 1개 이상의 연속된 공백(스페이스, 탭 등)을
    #   - ' ': 스페이스 1개로 치환 (예: "A  B" -> "A B")
    #   - .str.strip(): 문자열 양 끝의 공백 제거 (예: " A B " -> "A B")
    df_base['full_address'] = temp_address_series.str.replace(r'\s+', ' ', regex=True).str.strip()

    # 5. 'full_address' 컬럼을 마지막 주소 구성요소 컬럼 뒤로 이동
    try:
        last_component_col = existing_components[-1]
        last_col_idx = df_base.columns.get_loc(last_component_col) + 1
        
        # 'full_address' 컬럼을 pop (삭제하며 데이터 추출)
        full_address_data = df_base.pop('full_address')
        
        # 원하는 위치(last_col_idx)에 삽입
        df_base.insert(last_col_idx, 'full_address', full_address_data)
        
        print(f"  > 'full_address' 생성 완료 및 '{last_component_col}' 뒤로 이동 완료.")
    
    except Exception as e:
        print(f"  > (경고) 'full_address' 컬럼 이동 중 오류 발생: {e}")
        # 오류 발생 시, 'full_address'는 맨 뒤에 남아있음
        
    return df_base


def main():
    """
    메인 실행 함수
    """
    print("[1/5] 스크립트 실행 시작...")

    # --- 1. 필수 파일 존재 여부 확인 ---
    if not os.path.exists(BASE_FILE):
        print(f"[오류] 기본 파일 '{BASE_FILE}'을(를) 찾을 수 없습니다.")
        print("스크립트와 같은 폴더에 파일이 있는지 확인해주세요.")
        return

    if not os.path.exists(DATA_FILE):
        print(f"[오류] 좌표 데이터 파일 '{DATA_FILE}'을(를) 찾을 수 없습니다.")
        print("스크립트와 같은 폴더에 파일이 있는지 확인해주세요.")
        return

    try:
        # --- 2. 데이터 로드 (BASE_FILE) ---
        print(f"[2/5] '{BASE_FILE}' 로드 중...")
        
        # 법정동 코드는 '0'으로 시작할 수 있으므로 반드시 'str'로 읽어야 함
        try:
            # 기본 'utf-8-sig'로 시도
            df_base = pd.read_csv(BASE_FILE, dtype={'LAWD_CD': str}, encoding='utf-8-sig')
        except UnicodeDecodeError:
            # 실패 시 'euc-kr'로 재시도 (공공데이터는 euc-kr이 많음)
            print(f"  > (정보) utf-8-sig 읽기 실패. 'euc-kr' 인코딩으로 재시도합니다.")
            df_base = pd.read_csv(BASE_FILE, dtype={'LAWD_CD': str}, encoding='euc-kr')

        print(f"  > '{BASE_FILE}' 로드 완료. (총 {len(df_base)}건)")

        # --- 2-1. [v2] full_address 생성 로직 호출 ---
        df_base = create_full_address(df_base, ADDRESS_COMPONENTS)

        # --- 2-2. 데이터 로드 (DATA_FILE) ---
        print(f"[2/5] '{DATA_FILE}' 로드 중...")
        # 좌표 파일은 'bjd_geometry_to_csv.py'에서 'utf-8-sig'로 저장했으므로 인코딩 고정
        df_data = pd.read_csv(DATA_FILE, 
                              dtype={'legal_dong_code': str}, 
                              encoding='utf-8-sig')
        
        # --- 3. 좌표 데이터 준비 (컬럼 선택 및 중복 제거) ---
        print("[3/5] 좌표 데이터 처리 (중복 제거)...")
        
        # 3a. 요청된 컬럼이 모두 있는지 확인
        missing_cols = [col for col in COLUMNS_TO_JOIN if col not in df_data.columns]
        if missing_cols:
            print(f"[오류] '{DATA_FILE}'에 다음 필수 컬럼이 없습니다: {missing_cols}")
            return

        # 3b. 필요한 컬럼만 선택
        df_data_to_join = df_data[COLUMNS_TO_JOIN].copy()
        
        # 3c. 'legal_dong_code' 기준 중복 제거 (첫 번째 행만 남김)
        initial_count = len(df_data_to_join)
        df_data_to_join = df_data_to_join.drop_duplicates(
            subset=['legal_dong_code'], 
            keep='first'
        )
        print(f"  > 중복 제거 완료. (유효 좌표 {initial_count}건 -> 고유 {len(df_data_to_join)}건)")

        # --- 4. 데이터 병합 (Left Join) ---
        print("[4/5] 데이터 병합 (Left Join)...")
        
        df_merged = pd.merge(
            df_base,                 # (좌) 법정동 마스터 (full_address 포함)
            df_data_to_join,         # (우) 좌표 데이터 (중복 제거됨)
            left_on='LAWD_CD',       # (좌) 기준 키
            right_on='legal_dong_code', # (우) 매칭 키
            how='left'               # (방식) Left Join
        )

        # 병합 후 불필요해진 우측 키 컬럼('legal_dong_code') 삭제
        if 'legal_dong_code' in df_merged.columns:
            df_merged = df_merged.drop(columns=['legal_dong_code'])

        # --- 5. 결과 저장 ---
        output_file = get_unique_filename(OUTPUT_NAME, '.csv')
        print(f"[5/5] 결과 저장 중: '{output_file}'")

        # Excel에서 바로 열 수 있도록 'utf-8-sig'로 저장
        df_merged.to_csv(output_file, index=False, encoding='utf-8-sig')

        print("\n==================================================")
        print(f"[작업 완료]")
        print(f"'{output_file}' 파일에 총 {len(df_merged)}건의 데이터가 저장되었습니다.")
        
        # Join 성공/실패 요약
        matched_count = df_merged['center_latitude'].notna().sum()
        unmatched_count = df_merged['center_latitude'].isna().sum()
        
        print(f"  - 좌표가 매칭된 행 (Join 성공): {matched_count}건")
        print(f"  - 좌표가 없는 행 (Join 실패): {unmatched_count}건")
        print("==================================================")

    except Exception as e:
        print(f"\n[치명적 오류] 처리 중 예외가 발생했습니다: {e}")
        import traceback
        traceback.print_exc()

# 스크립트 직접 실행 시 main() 함수 호출
if __name__ == "__main__":
    main()
