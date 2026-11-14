import torch
import pandas as pd
import numpy as np
import os
import sys
from tqdm import tqdm

# Dongnae 패키지 경로 (환경에 맞게 수정 가능)
sys.path.append(os.path.join(os.path.dirname(__file__), '../py-core'))
try:
    from dongnae.engine import DongnaeEngine
except ImportError:
    print("❌ dongnae 패키지를 찾을 수 없습니다.")
    sys.exit(1)

# ==========================================
# [설정]
# ==========================================
# 파일 경로 (Windows 경로 역슬래시 문제 방지를 위해 r-string 사용)
GROUND_TRUTH_PATH = r"C:\projects\korea-bjd-shp-to-csv\optimize\output\ground_truth_5m.csv"
ORIGINAL_CSV_PATH = r"C:\projects\korea-bjd-shp-to-csv\optimize\dongnaeKR_251130.csv"
OUTPUT_CSV_PATH = r"C:\projects\korea-bjd-shp-to-csv\optimize\dongnaeKR_251130_optimized.csv"

# [개선된 하이퍼파라미터]
EPOCHS = 200            # 충분히 길게 설정 (조기 종료 믿고 늘림)
LEARNING_RATE = 0.02    # 초기 학습률
DECAY_RATE = 0.95       
MIN_LR = 0.0001         # 최소 학습률 하한선 (0이 되지 않도록 방지)
SHRINK_PENALTY = 1.0    # 침범 패널티
BATCH_SIZE = 200000     # GPU 배치 크기
MIN_RADIUS = 0.05       # 최소 반지름 (50m)

def main():
    # GPU 장치 설정
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"🔥 학습 장치: {device}")
    
    # 1. 원본 데이터 로드 & 텐서 변환 준비
    print("⏳ 엔진 및 데이터 로딩 중...")
    if not os.path.exists(ORIGINAL_CSV_PATH):
        print(f"❌ 원본 CSV 파일을 찾을 수 없습니다: {ORIGINAL_CSV_PATH}")
        sys.exit(1)
        
    engine = DongnaeEngine(ORIGINAL_CSV_PATH)
    
    # 동네 데이터 -> 텐서로 변환
    # dnid를 인덱스(0 ~ N)로 매핑
    dn_ids = [d['dnid'] for d in engine._dongnaes]
    id_to_idx = {dnid: i for i, dnid in enumerate(dn_ids)}
    
    # 중심 좌표 (N_dongnae, 2)
    centers_np = np.array([[d['dnlatitude'], d['dnlongitude']] for d in engine._dongnaes], dtype=np.float32)
    centers = torch.tensor(centers_np, device=device)
    
    # 학습할 반지름 (N_dongnae,)
    radii_np = np.array([d['dnradius'] for d in engine._dongnaes], dtype=np.float32)
    radii = torch.tensor(radii_np, device=device)
    
    # 위도 보정 계수 (Scalar)
    lat_coef = torch.tensor(engine._lat_coef, device=device)
    lon_coef = torch.tensor(engine._lon_coef, device=device)

    # 2. Ground Truth 로드
    if not os.path.exists(GROUND_TRUTH_PATH):
        print(f"❌ Ground Truth 파일을 찾을 수 없습니다: {GROUND_TRUTH_PATH}")
        sys.exit(1)
        
    df_gt = pd.read_csv(GROUND_TRUTH_PATH)
    # dnid 문자열을 정수 인덱스로 변환 (없는 ID는 필터링)
    df_gt['label_idx'] = df_gt['dnid'].map(id_to_idx).fillna(-1).astype(int)
    df_gt = df_gt[df_gt['label_idx'] >= 0] # 유효한 것만
    
    # 전체 데이터 텐서 (N_samples, 2)
    gt_coords = torch.tensor(df_gt[['lat', 'lon']].values, dtype=torch.float32, device=device)
    gt_labels = torch.tensor(df_gt['label_idx'].values, dtype=torch.long, device=device)
    
    num_samples = len(df_gt)
    print(f"✅ 학습 준비 완료: {num_samples:,}개 샘플 / {len(centers):,}개 동네")

    # 3. 학습 루프
    print("\n🚀 GPU 가속 최적화 시작 (v2: Smart Scheduling & Early Stopping)")
    
    current_lr = LEARNING_RATE
    patience = 0       # 조기 종료 카운터
    
    for epoch in range(EPOCHS):
        # 셔플링
        perm = torch.randperm(num_samples, device=device)
        
        total_fp = 0
        total_fn = 0
        total_tp = 0
        
        # 에포크 시작 전 반지름 상태 저장 (변화량 계산용)
        radii_start = radii.clone()
        
        # 배치 처리
        for i in tqdm(range(0, num_samples, BATCH_SIZE), desc=f"Epoch {epoch+1}/{EPOCHS}"):
            indices = perm[i : i + BATCH_SIZE]
            batch_coords = gt_coords[indices] # (B, 2)
            batch_labels = gt_labels[indices] # (B,)
            
            # ---------------------------------------------------------
            # [Step 1] 거리 계산 (Matrix Operation)
            # ---------------------------------------------------------
            
            # A. 정답 동네와의 거리 (Self Distance) - FN 체크용
            true_centers = centers[batch_labels] # (B, 2)
            true_radii = radii[batch_labels]     # (B,)
            
            d_lat = (batch_coords[:, 0] - true_centers[:, 0]) * lat_coef
            d_lon = (batch_coords[:, 1] - true_centers[:, 1]) * lon_coef
            dist_true = torch.sqrt(d_lat**2 + d_lon**2) # (B,)
            
            # FN 조건: dist > radius
            fn_mask = (dist_true - true_radii) > 0
            
            # --- 투표 집계 (Expand) ---
            vote_updates = torch.zeros_like(radii)
            
            ones = torch.ones(fn_mask.sum(), device=device)
            if fn_mask.any():
                vote_updates.scatter_add_(0, batch_labels[fn_mask], ones)
                total_fn += fn_mask.sum().item()
            
            total_tp += (~fn_mask).sum().item()

            # B. 다른 동네와의 거리 (Cross Distance) - FP 체크용
            # 마이크로 배치로 메모리 보호
            micro_batch = 1000 
            
            for j in range(0, len(batch_coords), micro_batch):
                mb_coords = batch_coords[j : j + micro_batch]     # (mb, 2)
                mb_labels = batch_labels[j : j + micro_batch]     # (mb,)
                
                # 브로드캐스팅: (mb, 1, 2) - (1, N, 2)
                diff = mb_coords.unsqueeze(1) - centers.unsqueeze(0)
                diff[:, :, 0] *= lat_coef
                diff[:, :, 1] *= lon_coef
                
                dists = torch.norm(diff, dim=2) # (mb, N)
                
                # 포함 여부 확인
                is_inside = dists < radii.unsqueeze(0)
                
                # 정답(자기 자신) 제외 마스킹
                self_mask = torch.zeros_like(is_inside, dtype=torch.bool)
                self_mask.scatter_(1, mb_labels.unsqueeze(1), True)
                
                # FP 조건: 범위 안임 AND 정답 아님
                fp_mask = is_inside & (~self_mask)
                
                if fp_mask.any():
                    fp_indices = torch.nonzero(fp_mask, as_tuple=True)[1]
                    
                    # --- 투표 집계 (Shrink) ---
                    # [수정] 완화된 SHRINK_PENALTY (1.5) 적용
                    penalty_vals = torch.full((len(fp_indices),), -SHRINK_PENALTY, device=device)
                    vote_updates.scatter_add_(0, fp_indices, penalty_vals)
                    
                    total_fp += len(fp_indices)

            # ---------------------------------------------------------
            # [Step 2] 파라미터(반지름) 업데이트
            # ---------------------------------------------------------
            delta = vote_updates * current_lr * 0.001
            delta = torch.clamp(delta, -0.5, 0.5)
            
            radii += delta
            radii = torch.clamp(radii, min=MIN_RADIUS)

        # 에포크 종료 후 통계 계산
        # 변화량 계산 (L1 Norm 평균)
        epoch_change = torch.abs(radii - radii_start).mean().item()
        
        print(f"   📊 Stats: TP={total_tp:,}, FN={total_fn:,}, FP={total_fp:,}")
        print(f"   🌊 Avg Change: {epoch_change:.6f} km")
        
        # [개선 1] 학습률 스케줄링 (Min LR 적용 & 천천히 감소)
        current_lr = max(MIN_LR, current_lr * DECAY_RATE)
        print(f"   📉 Next LR: {current_lr:.6f}")

        # [개선 2] 조기 종료 (Early Stopping) 체크
        # 10cm(0.0001km) 미만 변화가 10번 연속 지속되면 종료
        if epoch_change < 0.0001: 
            patience += 1
            print(f"   ☕ 변화 미미함 ({patience}/10)")
            if patience >= 10:
                print("\n🛑 조기 종료: 최적점에 도달했습니다 (Early Stopping Triggered).")
                break
        else:
            patience = 0

    # 4. 결과 저장 (CPU로 이동)
    print("\n💾 결과 저장 중...")
    optimized_radii = radii.cpu().numpy()
    
    # 엔진 객체 업데이트
    for i, r in enumerate(optimized_radii):
        engine._dongnaes[i]['dnradius'] = float(round(r, 4))
    
    # CSV 저장
    df_result = pd.DataFrame(engine._dongnaes)
    cols = ['dnid', 'dnname', 'dnlatitude', 'dnlongitude', 'dnradius']
    df_result[cols].to_csv(OUTPUT_CSV_PATH, index=False, encoding='utf-8-sig')
    print(f"🎉 완료! {OUTPUT_CSV_PATH}")

if __name__ == "__main__":
    main()