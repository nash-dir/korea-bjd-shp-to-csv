import geopandas as gpd
import pandas as pd
import numpy as np
from shapely.geometry import Point
import os
import glob
from tqdm import tqdm

# ==========================================
# [설정]
# ==========================================
INPUT_DIR = "C:\projects\korea-bjd-shp-to-csv\input"            # SHP 파일들이 있는 폴더
OUTPUT_DIR = "C:\projects\korea-bjd-shp-to-csv\optimize\output"          # 결과 저장 폴더
FINAL_FILENAME = "ground_truth_5m.csv"
ERROR_FILE = "bjd_251130_0015_error.csv"      # 스킵할 법정동 코드가 담긴 CSV 파일

# 샘플링 설정
TARGET_PER_DONG = 250          # 동네당 약 250개 (21,000개 * 250 ≈ 525만 개)
SHP_ENCODING = 'euc-kr'        # 쉐이프파일 인코딩 (필요시 utf-8 수정)

# ==========================================
# [함수] 고속 샘플링 (이전과 동일)
# ==========================================
def sample_points_in_polygon(poly, n_points):
    """
    폴리곤 내부에 존재하는 n_points 개의 랜덤 좌표를 생성합니다.
    """
    if poly is None or poly.is_empty:
        return []

    minx, miny, maxx, maxy = poly.bounds
    points = []
    
    # 무한 루프 방지용 최대 시도 횟수
    max_attempts = 10
    attempts = 0

    while len(points) < n_points and attempts < max_attempts:
        attempts += 1
        batch_size = (n_points - len(points)) * 3
        
        try:
            rnd_x = np.random.uniform(minx, maxx, batch_size)
            rnd_y = np.random.uniform(miny, maxy, batch_size)
            candidates = [Point(x, y) for x, y in zip(rnd_x, rnd_y)]
            valid_batch = [p for p in candidates if poly.contains(p)]
            points.extend(valid_batch)
        except Exception:
            continue
    
    return points[:n_points]

# ==========================================
# [함수] 블랙리스트 로딩
# ==========================================
def load_banned_ids(error_csv_path):
    """
    errors.csv에서 스킵할 법정동 코드를 읽어와 집합(Set)으로 반환
    """
    if not os.path.exists(error_csv_path):
        print(f"ℹ️ '{error_csv_path}' 파일이 없어 모든 동네를 처리합니다.")
        return set()
    
    try:
        # 첫 번째 컬럼을 ID로 가정하고 읽음 (헤더가 없으면 header=None 옵션 조정 필요)
        # 여기서는 헤더가 있다고 가정 (예: code, reason)
        df = pd.read_csv(error_csv_path, dtype=str)
        if df.empty:
            return set()
        
        # 첫 번째 컬럼의 데이터를 가져옴
        banned = set(df.iloc[:, 0].unique())
        print(f"🚫 {len(banned)}개의 스킵할 법정동 코드를 로드했습니다.")
        return banned
    except Exception as e:
        print(f"⚠️ 에러 파일 로딩 실패: {e}")
        return set()

# ==========================================
# [메인 로직]
# ==========================================
def main():
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)

    # 1. 스킵할 ID 목록 로드
    banned_ids = load_banned_ids(ERROR_FILE)

    # 2. SHP 파일 목록 탐색
    shp_files = glob.glob(os.path.join(INPUT_DIR, "*.shp"))
    if not shp_files:
        print(f"❌ '{INPUT_DIR}' 폴더에 .shp 파일이 없습니다.")
        return

    print(f"📂 총 {len(shp_files)}개의 SHP 파일을 발견했습니다.")
    print(f"🎯 목표: 동네당 {TARGET_PER_DONG}개 포인트 생성")

    generated_csvs = []

    # 3. 파일 순환 처리
    for shp_path in tqdm(shp_files, desc="파일 처리 중"):
        filename = os.path.basename(shp_path)
        temp_csv_path = os.path.join(OUTPUT_DIR, f"temp_{filename}.csv")
        
        try:
            # SHP 로딩
            gdf = gpd.read_file(shp_path, encoding=SHP_ENCODING)
            
            # 좌표계 변환
            if gdf.crs != "EPSG:4326":
                gdf = gdf.to_crs("EPSG:4326")

            file_data = []
            
            # 동네별 샘플링
            for _, row in gdf.iterrows():
                # 컬럼명 확인 (EMD_CD 또는 RI_CD)
                dnid = row.get('EMD_CD') or row.get('RI_CD')
                
                # [필터링 1] ID가 없으면 스킵
                if not dnid: continue
                
                # [필터링 2] 블랙리스트에 있으면 스킵
                if str(dnid) in banned_ids:
                    continue

                poly = row['geometry']
                
                # 샘플링 수행
                samples = sample_points_in_polygon(poly, TARGET_PER_DONG)
                
                for p in samples:
                    file_data.append({
                        'dnid': dnid,
                        'lat': round(p.y, 7),
                        'lon': round(p.x, 7)
                    })
            
            # 임시 파일 저장 (데이터가 있을 때만)
            if file_data:
                df_temp = pd.DataFrame(file_data)
                df_temp.to_csv(temp_csv_path, index=False, encoding='utf-8')
                generated_csvs.append(temp_csv_path)

        except Exception as e:
            print(f"\n⚠️ {filename} 처리 중 오류 발생: {e}")
            continue

    # 4. CSV 병합 및 정리
    if generated_csvs:
        print(f"\ncsv 병합 중... ({len(generated_csvs)}개 파일)")
        
        # 효율적인 병합을 위해 리스트로 모아서 concat
        df_list = [pd.read_csv(f) for f in generated_csvs]
        final_df = pd.concat(df_list, ignore_index=True)
        
        final_path = os.path.join(OUTPUT_DIR, FINAL_FILENAME)
        final_df.to_csv(final_path, index=False, encoding='utf-8')
        
        print(f"🎉 최종 저장 완료: {final_path} (총 {len(final_df):,}개)")

        # 임시 파일 삭제
        print("🧹 임시 파일 청소 중...")
        for f in generated_csvs:
            try:
                os.remove(f)
            except:
                pass
        print("✨ 모든 작업이 완료되었습니다.")
    else:
        print("❌ 생성된 데이터가 없습니다.")

if __name__ == "__main__":
    main()