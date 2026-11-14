import torch
import pandas as pd
import numpy as np
import os
import sys
from tqdm import tqdm

# Dongnae 패키지 경로
sys.path.append(os.path.join(os.path.dirname(__file__), '../py-core'))
try:
    from dongnae.engine import DongnaeEngine
except ImportError:
    print("❌ dongnae 패키지를 찾을 수 없습니다.")
    sys.exit(1)

# ==========================================
# [설정]
# ==========================================
# 경로 설정 (Windows 호환)
GROUND_TRUTH_PATH = r"C:\projects\korea-bjd-shp-to-csv\optimize\output\ground_truth_5m.csv"
ORIGINAL_CSV_PATH = r"C:\projects\korea-bjd-shp-to-csv\optimize\dongnaeKR_251130.csv"
OUTPUT_CSV_PATH = r"C:\projects\korea-bjd-shp-to-csv\optimize\dongnaeKR_251130_optimized_neutral.csv"

# [최종 튜닝된 하이퍼파라미터: Statistical Neutrality]
EPOCHS = 300            # 중립적 경계를 찾기 위해 충분한 시간 부여 (수렴할 때까지)
LEARNING_RATE = 0.02    # 초기 탐색 속도 확보
DECAY_RATE = 0.99       # 아주 천천히 감소시켜서 정밀하게 수렴 유도
MIN_LR = 0.0001         # 학습 종료 방지
BATCH_SIZE = 200000     # GPU 배치 크기
MIN_RADIUS = 0.05       # 최소 50m

# [핵심 변경] 중립 패널티 적용
# 1.0 : FP(침범)와 FN(놓침)을 동등하게 처벌 -> 기하학적/통계적 최적 경계 도출
# 목적: Geocoding 정확도와 Event 커버리지 사이의 'Golden Balance'
SHRINK_PENALTY = 1.0    

def main():
    # GPU 장치 설정
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"🔥 학습 장치: {device}")
    
    # 1. 데이터 로드
    print("⏳ 엔진 및 데이터 로딩 중...")
    if not os.path.exists(ORIGINAL_CSV_PATH):
        print(f"❌ 원본 CSV 없음: {ORIGINAL_CSV_PATH}")
        sys.exit(1)
        
    engine = DongnaeEngine(ORIGINAL_CSV_PATH)
    
    # 데이터 -> 텐서 변환
    dn_ids = [d['dnid'] for d in engine._dongnaes]
    id_to_idx = {dnid: i for i, dnid in enumerate(dn_ids)}
    
    centers_np = np.array([[d['dnlatitude'], d['dnlongitude']] for d in engine._dongnaes], dtype=np.float32)
    centers = torch.tensor(centers_np, device=device)
    
    radii_np = np.array([d['dnradius'] for d in engine._dongnaes], dtype=np.float32)
    radii = torch.tensor(radii_np, device=device)
    
    lat_coef = torch.tensor(engine._lat_coef, device=device)
    lon_coef = torch.tensor(engine._lon_coef, device=device)

    # 2. Ground Truth 로드
    if not os.path.exists(GROUND_TRUTH_PATH):
        print(f"❌ 정답지 파일 없음: {GROUND_TRUTH_PATH}")
        sys.exit(1)
        
    df_gt = pd.read_csv(GROUND_TRUTH_PATH)
    df_gt['label_idx'] = df_gt['dnid'].map(id_to_idx).fillna(-1).astype(int)
    df_gt = df_gt[df_gt['label_idx'] >= 0]
    
    gt_coords = torch.tensor(df_gt[['lat', 'lon']].values, dtype=torch.float32, device=device)
    gt_labels = torch.tensor(df_gt['label_idx'].values, dtype=torch.long, device=device)
    
    num_samples = len(df_gt)
    print(f"✅ 준비 완료: {num_samples:,}개 샘플 학습 시작")

    # 3. 학습 루프
    print("\n🚀 GPU 최적화 시작 (Mode: Statistical Neutrality)")
    
    current_lr = LEARNING_RATE
    patience = 0
    best_change = float('inf')
    
    for epoch in range(EPOCHS):
        perm = torch.randperm(num_samples, device=device)
        
        total_fp = 0
        total_fn = 0
        total_tp = 0
        
        radii_start = radii.clone()
        
        for i in tqdm(range(0, num_samples, BATCH_SIZE), desc=f"Ep {epoch+1}"):
            indices = perm[i : i + BATCH_SIZE]
            b_coords = gt_coords[indices]
            b_labels = gt_labels[indices]
            
            # [Step 1] 거리 계산
            true_centers = centers[b_labels]
            true_radii = radii[b_labels]
            
            d_lat = (b_coords[:, 0] - true_centers[:, 0]) * lat_coef
            d_lon = (b_coords[:, 1] - true_centers[:, 1]) * lon_coef
            dist_true = torch.sqrt(d_lat**2 + d_lon**2)
            
            # FN 체크
            fn_mask = (dist_true - true_radii) > 0
            
            # 투표 (Expand)
            vote_updates = torch.zeros_like(radii)
            ones = torch.ones(fn_mask.sum(), device=device)
            if fn_mask.any():
                vote_updates.scatter_add_(0, b_labels[fn_mask], ones)
                total_fn += fn_mask.sum().item()
            
            total_tp += (~fn_mask).sum().item()

            # FP 체크 (Micro-batch)
            micro_batch = 2000 # 메모리 여유 있으면 늘려도 됨
            
            for j in range(0, len(b_coords), micro_batch):
                mb_coords = b_coords[j : j + micro_batch]
                mb_labels = b_labels[j : j + micro_batch]
                
                diff = mb_coords.unsqueeze(1) - centers.unsqueeze(0)
                diff[:, :, 0] *= lat_coef
                diff[:, :, 1] *= lon_coef
                
                dists = torch.norm(diff, dim=2)
                
                is_inside = dists < radii.unsqueeze(0)
                
                self_mask = torch.zeros_like(is_inside, dtype=torch.bool)
                self_mask.scatter_(1, mb_labels.unsqueeze(1), True)
                
                fp_mask = is_inside & (~self_mask)
                
                if fp_mask.any():
                    fp_indices = torch.nonzero(fp_mask, as_tuple=True)[1]
                    # Shrink Vote (Penalty 1.0 적용)
                    penalty_vals = torch.full((len(fp_indices),), -SHRINK_PENALTY, device=device)
                    vote_updates.scatter_add_(0, fp_indices, penalty_vals)
                    total_fp += len(fp_indices)

            # [Step 2] 업데이트
            delta = vote_updates * current_lr * 0.001
            delta = torch.clamp(delta, -0.5, 0.5)
            
            radii += delta
            radii = torch.clamp(radii, min=MIN_RADIUS)

        # 통계 및 스케줄링
        epoch_change = torch.abs(radii - radii_start).mean().item()
        
        print(f"   📊 TP={total_tp:,} | FN={total_fn:,} | FP={total_fp:,}")
        print(f"   🌊 Change: {epoch_change:.6f} km | LR: {current_lr:.6f}")
        
        current_lr = max(MIN_LR, current_lr * DECAY_RATE)

        # 조기 종료 (Early Stopping)
        # 변화량이 5cm(0.00005) 미만으로 떨어지면 카운트
        if epoch_change < 0.00005:
            patience += 1
            if patience >= 15: # 15번 참음 (충분히 수렴 확인)
                print("\n🛑 수렴 완료 (Converged). 학습을 종료합니다.")
                break
        else:
            patience = 0

    # 4. 저장
    print("\n💾 결과 저장 중...")
    optimized_radii = radii.cpu().numpy()
    
    for i, r in enumerate(optimized_radii):
        engine._dongnaes[i]['dnradius'] = float(round(r, 4))
    
    df_result = pd.DataFrame(engine._dongnaes)
    # 필요한 컬럼만 깔끔하게 저장
    cols = ['dnid', 'dnname', 'dnlatitude', 'dnlongitude', 'dnradius']
    df_result[cols].to_csv(OUTPUT_CSV_PATH, index=False, encoding='utf-8-sig')
    print(f"🎉 완료! {OUTPUT_CSV_PATH}")

if __name__ == "__main__":
    main()