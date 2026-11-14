import pandas as pd
import numpy as np
import os
import sys
import multiprocessing
from concurrent.futures import ProcessPoolExecutor, as_completed
from tqdm import tqdm
from collections import defaultdict

# Dongnae 패키지 경로 추가
sys.path.append(os.path.join(os.path.dirname(__file__), '../py-core'))
try:
    from dongnae.engine import DongnaeEngine
except ImportError:
    print("❌ dongnae 패키지를 찾을 수 없습니다. 경로를 확인해주세요.")
    sys.exit(1)

# ==========================================
# [설정]
# ==========================================
GROUND_TRUTH_PATH = r"C:\projects\korea-bjd-shp-to-csv\optimize\output\ground_truth_5m.csv"
ORIGINAL_CSV_PATH = r"C:\projects\korea-bjd-shp-to-csv\optimize\dongnaeKR_251130.csv"
OUTPUT_CSV_PATH = r"C:\projects\korea-bjd-shp-to-csv\optimize\dongnaeKR_251130_optimized.csv"

# 학습 하이퍼파라미터
EPOCHS = 5
LEARNING_RATE = 0.005
SHRINK_PENALTY = 2.0
MIN_RADIUS = 0.05
# 배치 사이즈는 이제 '청크 사이즈'로 대체됨 (프로세스당 할당량)

# ==========================================
# [워커 함수] 각 프로세스가 수행할 작업
# ==========================================
def process_chunk(chunk_df, engine, shrink_penalty):
    """
    할당받은 데이터 청크(chunk_df)에 대해 투표를 진행하고 결과를 반환합니다.
    """
    local_votes = defaultdict(float)
    local_stats = {'fp': 0, 'fn': 0, 'tp': 0}
    
    # DataFrame 순회
    # (iterrows보다 itertuples가 빠름)
    for row in chunk_df.itertuples(index=False):
        # row 순서: dnid, lat, lon (read_csv 시 컬럼 순서 유의)
        true_dnid = row.dnid
        lat, lon = row.lat, row.lon
        
        target_dn = engine.get(true_dnid)
        if not target_dn: continue

        # 1. 내 땅 지키기 (False Negative Check)
        dist_target = engine._dongnae_dist(lat, lon, target_dn)
        
        if dist_target > 0:
            local_votes[true_dnid] += 1.0  # Expand
            local_stats['fn'] += 1
        else:
            local_stats['tp'] += 1

        # 2. 남의 땅 침범 체크 (False Positive Check)
        # engine.nearest는 내부적으로 Spatial Indexing(BBox)을 하므로 빠름
        candidates = engine.nearest(lat, lon, k=5, radius_km=10.0)
        
        for cand in candidates:
            cand_id = cand['dnid']
            if cand_id == true_dnid: continue
                
            # 만약 다른 동네가 이 점을 포함한다고 하면?
            if cand['distance'] <= 0:
                local_votes[cand_id] -= (1.0 * shrink_penalty) # Shrink
                local_stats['fp'] += 1
                
    return local_votes, local_stats

# ==========================================
# [메인 로직]
# ==========================================
def main():
    # Windows/macOS의 'spawn' 방식 멀티프로세싱을 위해 global 변수 재선언
    global LEARNING_RATE
    
    # CPU 코어 수 확인
    num_workers = multiprocessing.cpu_count()
    print(f"🔥 CPU 코어 {num_workers}개를 사용하여 병렬 처리를 시작합니다.")

    print("⏳ 데이터 로딩 중...")
    
    # 1. 엔진 초기화
    engine = DongnaeEngine(ORIGINAL_CSV_PATH)
    # dnid -> list index 매핑
    dn_map = {dn['dnid']: i for i, dn in enumerate(engine._dongnaes)}
    print(f"✅ 엔진 로드 완료: {len(engine._dongnaes)}개 동네")

    # 2. Ground Truth 로드
    df_gt = pd.read_csv(GROUND_TRUTH_PATH, dtype={'dnid': str, 'lat': float, 'lon': float})
    print(f"✅ Ground Truth 로드 완료: {len(df_gt):,}개 포인트")

    # 3. 학습 루프
    print("\n🚀 병렬 최적화 시작")
    
    for epoch in range(EPOCHS):
        print(f"\n[Epoch {epoch+1}/{EPOCHS}]")
        
        # 데이터 셔플링
        df_shuffled = df_gt.sample(frac=1).reset_index(drop=True)
        
        # 데이터를 워커 수만큼 쪼개기 (Chunking)
        chunks = np.array_split(df_shuffled, num_workers)
        
        total_votes = defaultdict(float)
        total_stats = {'fp': 0, 'fn': 0, 'tp': 0}
        
        # --- 병렬 처리 구간 ---
        with ProcessPoolExecutor(max_workers=num_workers) as executor:
            # 각 워커에게 (데이터청크, 현재엔진상태, 패널티) 전달
            # 주의: engine 객체가 각 프로세스로 복사(Pickling)되어 전달됨
            futures = [
                executor.submit(process_chunk, chunk, engine, SHRINK_PENALTY) 
                for chunk in chunks
            ]
            
            # 결과 취합 (tqdm으로 진행률 표시)
            for future in tqdm(as_completed(futures), total=num_workers, desc="Processing"):
                try:
                    l_votes, l_stats = future.result()
                    
                    # 투표 합산
                    for k, v in l_votes.items():
                        total_votes[k] += v
                        
                    # 통계 합산
                    for k, v in l_stats.items():
                        total_stats[k] += v
                        
                except Exception as e:
                    print(f"⚠️ 워커 에러 발생: {e}")

        # --- 파라미터 업데이트 (메인 프로세스에서 수행) ---
        updated_count = 0
        sum_change = 0.0
        
        for dnid, net_vote in total_votes.items():
            if dnid not in dn_map: continue
            idx = dn_map[dnid]
            dn = engine._dongnaes[idx]
            
            old_radius = dn['dnradius']
            
            # 변경량 계산
            delta = net_vote * LEARNING_RATE * 0.001
            delta = max(-0.5, min(0.5, delta)) # Clamping
            
            new_radius = max(MIN_RADIUS, old_radius + delta)
            
            # 엔진 상태 업데이트 (다음 에포크에 반영됨)
            engine._dongnaes[idx]['dnradius'] = round(new_radius, 4)
            
            if abs(new_radius - old_radius) > 0.0001:
                updated_count += 1
                sum_change += abs(delta)

        # 에포크 리포트
        avg_change = sum_change / updated_count if updated_count else 0
        print(f"   👉 Update: {updated_count:,}개 동네 반경 조정됨 (평균 변화: {avg_change:.4f}km)")
        print(f"   👉 Stats : TP={total_stats['tp']:,}, FN(놓침)={total_stats['fn']:,}, FP(침범)={total_stats['fp']:,}")
        
        # 학습률 감쇠
        LEARNING_RATE *= 0.8
        print(f"   👉 Next LR: {LEARNING_RATE:.5f}")

    # 4. 결과 저장
    print("\n💾 최적화된 CSV 저장 중...")
    df_result = pd.DataFrame(engine._dongnaes)
    cols = ['dnid', 'dnname', 'dnlatitude', 'dnlongitude', 'dnradius']
    df_result = df_result[cols]
    
    df_result.to_csv(OUTPUT_CSV_PATH, index=False, encoding='utf-8-sig')
    print(f"🎉 완료! 저장 경로: {OUTPUT_CSV_PATH}")

if __name__ == "__main__":
    # Windows/macOS에서는 필수
    multiprocessing.freeze_support()
    main()