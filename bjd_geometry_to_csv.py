# -*- coding: utf-8 -*-
"""
================================================================================
 한국 법정동 쉐이프파일(SHP) -> CSV 일괄 변환 스크립트
================================================================================
[기능]
1. 'input' 폴더 내의 모든 .shp 파일을 순회하며 읽어옵니다.
2. 쉐이프파일의 테이블정의서(주석 참고)에 따라 컬럼명을 표준화하여 매핑합니다.
3. 지오메트리(도형) 정보를 이용해 중심점(위경도), 미터(EPSG:5179) 기준 외접 사각형 대각선 절반 길이(radius_km)를 계산합니다. 'radius_km'은 특정 좌표부터 법정동 중심점까지의 거리를 조정하기 위한 보정값입니다.
4. 'output/temp_...'로 시작하는 임시 CSV를 파일별로 생성합니다.
5. 모든 임시 CSV를 하나로 병합하여 'output' 폴더에 최종 결과물(result.csv, error.csv)을 저장합니다.
6. 임시 CSV 파일들을 삭제합니다.

[오류 검증 로직 (후처리)]
- (정상처리) 8자리 법정동코드(동)는 뒷자리에 00 패딩을 추가해 10자리로 자동 변환합니다.
- (오류처리) 법정동코드가 8자리 또는 10자리 정수가 아니면 'error.csv'로 분리합니다.
- (오류처리) 법정동명(tip)에 한글이 포함되지 않으면 'error.csv'로 분리합니다.

[필요 라이브러리]
pip install geopandas pandas tqdm

[권장 디렉토리 구조]
- (현재 디렉토리)/
  |- bjd_geometry_to_csv.py (본 스크립트)
  |- input/
  |  |- LSMD_ADM_SECT_RI_... .shp (및 관련 파일들)
  |  |- LSMD_ADM_SECT_UMD_... .shp (및 관련 파일들)
  |- output/
     |- (임시) temp_... .csv
     |- (최종) bjd_251117_2141_result.csv
     |- (최종) bjd_251117_2141_error.csv
================================================================================
"""
import geopandas as gpd
import pandas as pd
import os
import glob
import re  # 정규표현식(Regex) 라이브러리
from tqdm import tqdm  # 진행률 표시 라이브러리
from datetime import datetime  # 파일명 생성을 위한 시간 라이브러리

# ===========================================================
# [설정 영역]
# ===========================================================

# 1. 경로 설정
BASE_DIR = os.getcwd()  # 현재 스크립트가 실행되는 디렉토리
INPUT_DIR = os.path.join(BASE_DIR, 'input')    # 쉐이프파일이 위치한 폴더
OUTPUT_DIR = os.path.join(BASE_DIR, 'output')  # 결과물이 저장될 폴더

# 2. 쉐이프파일 인코딩 설정
SHP_ENCODING = 'euc-kr'

# 3. 컬럼명 매핑 후보군
CODE_CANDIDATES = ['RI_CD', 'EMD_CD']
NAME_CANDIDATES = ['RI_NM', 'EMD_NM']
SE_CANDIDATES = ['COL_ADM_SE']
SGG_CANDIDATES = ['SGG_OID']

# ===========================================================
# [데이터 소스]
# 브이월드 공간정보 다운로드 # https://www.vworld.kr/dtmk/dtmk_ntads_s001.do
# 전체 법정동코드 : 국토관리 > 지역개발 > 경계법정동코드
# 경계도면 : 국토관리 > 지역개발 > 행정구역_리(법정동), 행정구역_읍면동(법정동)
# ===========================================================

# [테이블 정의서]

## 행정구역_리(법정동) LSMD_ADM_SECT_RI
# 컬럼ID	컬럼명	타입	길이(Byte)
# RI_CD	리코드	VARCHAR2	10
# RI_NM	리명	VARCHAR2	20
# SGG_OID	원천도형_ID	INTEGER	22
# COL_ADM_SECT_CD	원천시군구코드	VARCHAR2	5 (shf 파일상 'COL_ADM_SE' 키)
# OBJECTID	도형_ID	INTEGER	22
# SHAPE_AREA	도형면적	DOUBLE	22
# SHAPE_LEN	도형길이	DOUBLE	22

## 행정구역_읍면동(법정동) LSMD_ADM_SECT_UMD
# 컬럼ID	컬럼명	타입	길이(Byte)
# EMD_CD	읍면동코드	VARCHAR2	8
# EMD_NM	읍면동명	VARCHAR2	20
# SGG_OID	원천도형_ID	INTEGER	22
# COL_ADM_SECT_CD	원천시군구코드	VARCHAR2	5 (shf 파일상 'COL_ADM_SE' 키)
# OBJECTID	도형_ID	INTEGER	22
# SHAPE_AREA	도형면적	DOUBLE	22
# SHAPE_LEN	도형길이	DOUBLE	22
# ===========================================================


def find_column(columns, candidates):
    """
    DataFrame의 컬럼 리스트(columns) 중에서
    후보군(candidates)에 일치하는 첫 번째 컬럼명을 찾아 반환합니다.
    """
    for cand in candidates:
        if cand in columns:
            return cand
    return None  # 후보군에 해당하는 컬럼이 하나도 없으면 None 반환


def post_process_and_save(final_df, output_dir, final_filename, error_filename):
    """
    [후처리] 최종 병합된 데이터프레임을 검증하고, 정상/오류 파일로 분리 저장합니다.
    """
    print("\n[3단계] 최종 데이터 후처리 및 검증 시작...")

    # --- 1. 검증용 정규표현식(Regex) 준비 ---
    # 한글이 1글자라도 포함되어 있는지 (자음/모음 포함)
    hangul_pattern = re.compile(r'[ㄱ-ㅎㅏ-ㅣ가-힣]')
    # '8자리 또는 10자리'의 숫자로만 구성되어 있는지
    code_pattern_8_10 = re.compile(r'^\d{8}$|^\d{10}$')
    # '정확히 8자리' 숫자인지 (00 패딩 대상)
    code_pattern_8 = re.compile(r'^\d{8}$')

    # --- 2. 안정성을 위해 타입 변환 및 공백 제거 ---
    final_df['legal_dong_code'] = final_df['legal_dong_code'].astype(str).str.strip()
    final_df['legal_dong_tip'] = final_df['legal_dong_tip'].astype(str).str.strip()

    error_rows = []      # 오류 데이터를 담을 리스트
    clean_indices = []   # 정상 데이터의 인덱스 번호를 담을 리스트

    # --- 3. 데이터 검증 (한 줄씩 순회) ---
    for index, row in tqdm(final_df.iterrows(), total=len(final_df), desc="데이터 검증"):
        code = row['legal_dong_code']
        tip = row['legal_dong_tip']
        is_error = False

        # [검증 1] 법정동코드 형식 (8자리 또는 10자리 숫자)
        if not code_pattern_8_10.match(code):
            row['error_reason'] = '법정동코드 형식이 8자리 또는 10자리 숫자가 아님'
            is_error = True

        # [검증 2] 법정동명(tip) 한글 포함 여부
        if not is_error and not hangul_pattern.search(tip):
            row['error_reason'] = '법정동명(tip)에 한글이 포함되지 않음'
            is_error = True

        # --- 4. 분리 및 8자리 코드 패딩 ---
        if is_error:
            error_rows.append(row)
        else:
            clean_indices.append(index)
            # [정상 처리] 8자리 코드(읍면동)일 경우, 뒤에 '00'을 추가하여 10자리로 표준화
            if code_pattern_8.match(code):
                final_df.at[index, 'legal_dong_code'] = code + '00'

    # --- 5. 최종 데이터프레임 분리 및 저장 ---
    clean_df = final_df.loc[clean_indices].copy()

    if 'error_reason' in clean_df.columns:
        clean_df = clean_df.drop(columns=['error_reason'])

    # 'OUTPUT_DIR'에 정상 데이터와 오류 데이터를 저장
    final_path = os.path.join(output_dir, final_filename)
    clean_df.to_csv(final_path, index=False, encoding='utf-8-sig')
    print(f"\n[성공] {len(clean_df)}건의 정상 데이터를 '{final_filename}'에 저장했습니다.")

    if error_rows:
        error_df = pd.DataFrame(error_rows)
        error_path = os.path.join(output_dir, error_filename)
        error_df.to_csv(error_path, index=False, encoding='utf-8-sig')
        print(f"[오류] {len(error_df)}건의 오류 데이터를 '{error_filename}'에 저장했습니다.")
    else:
        print("[정보] 오류 데이터가 발견되지 않았습니다.")


def process_shapefiles():
    """
    메인 실행 함수. input 폴더의 shp 파일을 읽어 처리하고 output에 저장합니다.
    """
    # --- 0. 준비 단계 ---
    
    # output 폴더가 없을 경우 생성
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    # 동적 파일명 생성을 위한 타임스탬프 yymmdd_HHMM
    TIMESTAMP = datetime.now().strftime('%y%m%d_%H%M')
    FINAL_FILENAME_DYN = f"bjd_{TIMESTAMP}_result.csv"
    ERROR_FILENAME_DYN = f"bjd_{TIMESTAMP}_error.csv"

    # 'input' 폴더에서 .shp 파일 목록 가져오기
    shp_list = glob.glob(os.path.join(INPUT_DIR, "*.shp"))
    
    if not shp_list:
        print(f"[경고] 'input' 폴더에 .shp 파일이 없습니다: {INPUT_DIR}")
        return

    print(f"총 {len(shp_list)}개의 SHP 파일을 발견했습니다.")
    print("==================================================")
    
    generated_csvs = []  # 개별 생성된 임시 CSV 경로 리스트

    # ==================================================
    # [1단계] 개별 쉐이프파일 처리 및 임시 CSV 생성
    # ==================================================
    print(f"[1단계] 개별 파일 처리 및 지오메트리 연산 시작...")
    for file_path in tqdm(shp_list, desc="개별 파일 처리"):
        file_name = os.path.basename(file_path)
        # 임시 파일은 'output' 폴더에 저장
        output_csv_path = os.path.join(OUTPUT_DIR, f"temp_{os.path.splitext(file_name)[0]}.csv")
        
        try:
            # 1. 파일 로드 (요청하신 'euc-kr' 인코딩 사용)
            gdf = gpd.read_file(file_path, encoding=SHP_ENCODING)
            
            # 2. 키 매핑 (표준화)
            code_col = find_column(gdf.columns, CODE_CANDIDATES)
            name_col = find_column(gdf.columns, NAME_CANDIDATES)
            se_col = find_column(gdf.columns, SE_CANDIDATES)
            sgg_col = find_column(gdf.columns, SGG_CANDIDATES)

            if not code_col or not name_col:
                print(f"\n[경고] {file_name}에서 필수 컬럼(코드/명칭)을 찾지 못해 건너뜁니다.")
                continue
                
            # 3. 지오메트리 연산
            # (1) 좌표계 변환 (EPSG:5179 - 미터 단위)
            gdf_5179 = gdf.to_crs(epsg=5179)
            
            # (2) 외접원(Minimum Bounding Circle) 반지름 (radius_km) 계산
            # minimum_bounding_circle()은 외접원을 폴리곤 형태로 반환합니다.
            # 따라서 원의 면적 공식(A = πr²)을 이용해 반지름을 역산합니다: r = sqrt(A / π)
            mbc_geometry = gdf_5179.geometry.minimum_bounding_circle()
            radius_m = (mbc_geometry.area / 3.141592653589793) ** 0.5
            radius_km = radius_m / 1000  # 미터(m)를 킬로미터(km)로 변환
            
            # (3) 중심점(Centroid) 계산 및 변환 (EPSG:4326 - 위/경도)
            centroids = gdf_5179.geometry.centroid.to_crs(epsg=4326)
            
            # 4. 데이터프레임 조립 (테이블정의서 기반)
            df_result = pd.DataFrame()
            
            df_result['legal_dong_code'] = gdf[code_col]
            df_result['legal_dong_tip'] = gdf[name_col]
            
            # 'COL_ADM_SE' -> 'COL_ADM_SECT_CD'로 매핑
            df_result['COL_ADM_SECT_CD'] = gdf[se_col] if se_col else None
            df_result['SGG_OID'] = gdf[sgg_col] if sgg_col else None
            
            df_result['center_latitude'] = centroids.y
            df_result['center_longitude'] = centroids.x
            df_result['radius_km'] = radius_km.round(3) # km 단위 (소수점 3째자리)
            df_result['filename'] = file_name # 원본 파일명 (데이터 리니지)
            
            # 5. 개별 임시 CSV 저장
            df_result.to_csv(output_csv_path, index=False, encoding='utf-8-sig')
            generated_csvs.append(output_csv_path) # 병합을 위해 경로 저장
            
        except Exception as e:
            print(f"\n[오류!!] {file_name} 처리 중 예외 발생: {e}")
            continue

    # ==================================================
    # [2단계] 최종 병합
    # ==================================================
    if generated_csvs:
        print("\n[2단계] 개별 CSV 파일 병합 시작...")
        
        # dtype='str': 코드가 숫자로 변환(예: '00123' -> 123)되는 것을 방지
        df_list = [pd.read_csv(f, dtype=str) for f in generated_csvs]
        
        if df_list:
            final_df = pd.concat(df_list, ignore_index=True)
            
            # [3단계] 후처리 함수 호출
            # 동적 파일명과 'OUTPUT_DIR' 경로 전달
            post_process_and_save(final_df, OUTPUT_DIR, FINAL_FILENAME_DYN, ERROR_FILENAME_DYN)
            
            # 4. 임시 파일 삭제
            print("\n[4단계] 임시 파일 삭제 중...")
            for f in tqdm(generated_csvs, desc="임시 파일 정리"):
                try:
                    os.remove(f)
                except Exception as e:
                    print(f"\n[경고] {f} 삭제 실패: {e}")
            print("모든 작업이 완료되었습니다.")
        else:
            print("병합할 데이터가 없습니다.")
    else:
        print("처리된 CSV 파일이 없어 병합을 건너뜁니다.")


if __name__ == "__main__":
    process_shapefiles()
