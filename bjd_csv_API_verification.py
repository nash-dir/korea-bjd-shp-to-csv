import argparse
import os
import time
from datetime import datetime

import pandas as pd

# requests, tqdm, dotenv 등 실행 전용 의존성은 실제 실행 함수 내부에서 지연(lazy) import 합니다.
# 덕분에 순수 함수(verify_address)는 pandas만으로 import/테스트할 수 있습니다.

# ===========================================================
# [설정 영역] (CLI 기본값)
# ===========================================================
INPUT_CSV = "LSCT_LAWDCD_coords_251117_revised.csv"   # 원본 파일
OUTPUT_CSV = "LSCT_LAWDCD_with_verified_address.csv"  # 결과 CSV 파일
BATCH_SIZE = 100                                      # 중간 저장 단위
REQUEST_DELAY = 0.05                                  # API 요청 간격 (초)
# ===========================================================

def get_vworld_address(lat, lon, api_key):
    """
    VWorld API를 통해 좌표 -> 주소(도로명/지번) 변환
    """
    import requests

    if pd.isna(lat) or pd.isna(lon):
        return None

    url = "https://api.vworld.kr/req/address?"
    params = {
        "service": "address",
        "request": "getaddress",
        "crs": "epsg:4326",
        "point": f"{lon},{lat}",
        "format": "json",
        "type": "both",
        "zipcode": "false",
        "simple": "false",
        "key": api_key
    }

    try:
        response = requests.get(url, params=params, timeout=5)
        if response.status_code == 200:
            data = response.json()
            status = data.get('response', {}).get('status')
            if status == 'OK':
                results = data.get('response', {}).get('result', [])
                if results:
                    return results[0].get('text')
            elif status == 'NOT_FOUND':
                return "주소 미존재"
            else:
                return f"API오류: {status}"
        return f"HTTP오류: {response.status_code}"
    except Exception as e:
        return f"통신오류: {str(e)}"

def verify_address(row, api_addr):
    """
    [검증 로직 3단 분리]
    Returns:
        None (NULL): API 결과가 없거나 '오류', '미존재'인 경우
        1: 리(RI) 또는 읍면동(UMD) 명칭이 API 주소에 포함된 경우
        0: API 응답은 정상이나, 명칭이 매칭되지 않는 경우
    """
    if pd.isna(api_addr):
        return None

    str_api = str(api_addr).strip()

    # '오류' 또는 '미존재' 키워드가 포함되면 NULL 처리
    if "오류" in str_api or "미존재" in str_api:
        return None

    # 타겟 명칭 준비
    ri_nm = str(row.get('RI_NM', '')).strip()
    umd_nm = str(row.get('UMD_NM', '')).strip()
    
    if ri_nm.lower() == 'nan':
        ri_nm = ''
    if umd_nm.lower() == 'nan':
        umd_nm = ''

    # 매칭 로직
    if ri_nm:
        return 1 if ri_nm in str_api else 0
    elif umd_nm:
        return 1 if umd_nm in str_api else 0
    
    return 0

def main(input_csv=INPUT_CSV, output_csv=OUTPUT_CSV, batch_size=BATCH_SIZE,
         request_delay=REQUEST_DELAY):
    # 실행 전용 의존성 lazy import
    from dotenv import load_dotenv
    from tqdm import tqdm

    # 1. 환경 변수 로드
    load_dotenv()
    vworld_key = os.getenv("API_KEY")

    if not vworld_key:
        print("[오류] 'API_KEY' 환경 변수가 없습니다. .env 파일을 확인하세요.")
        return

    # 2. 데이터 로드
    if not os.path.exists(input_csv):
        print(f"[오류] 입력 파일이 존재하지 않습니다: {input_csv}")
        return

    df = pd.read_csv(input_csv, dtype={'legal_dong_code': str})
    
    # 3. 통계 카운터 초기화
    cnt_total = len(df)      # 총 레코드 수
    cnt_requests = 0         # API 요청 시도 횟수
    cnt_errors = 0           # API 오류/미존재 횟수 (verified가 None인 경우)
    cnt_matched = 0          # 일치 확인 횟수 (verified가 1인 경우)

    print(f"[시작] 총 {cnt_total}건의 데이터 처리를 시작합니다.")

    # 4. 결과 파일 초기화
    output_columns = df.columns.tolist() + ['center_address', 'verified']
    pd.DataFrame(columns=output_columns).to_csv(output_csv, index=False, encoding='utf-8-sig')

    buffer = []

    # 5. 메인 루프
    for idx, row in tqdm(df.iterrows(), total=cnt_total, desc="진행 중", unit="건"):
        
        lat = row['center_latitude']
        lon = row['center_longitude']
        
        # (A) 좌표 존재 시 API 호출
        if pd.notna(lat) and pd.notna(lon):
            cnt_requests += 1 # 요청 카운트 증가
            
            api_addr = get_vworld_address(lat, lon, vworld_key)
            is_verified = verify_address(row, api_addr)
            
            # 검증 결과에 따른 카운트 집계
            if is_verified is None:
                cnt_errors += 1
            elif is_verified == 1:
                cnt_matched += 1
            
            time.sleep(request_delay)
        
        # (B) 좌표 결측 시
        else:
            api_addr = None
            is_verified = None # 좌표 없으면 NULL 처리

        row_dict = row.to_dict()
        row_dict['center_address'] = api_addr
        row_dict['verified'] = is_verified
        
        buffer.append(row_dict)

        # (C) 배치 저장
        if len(buffer) >= batch_size:
            batch_df = pd.DataFrame(buffer)
            batch_df.to_csv(output_csv, index=False, header=False, mode='a', encoding='utf-8-sig')
            buffer = []

    # 6. 잔여 데이터 저장
    if buffer:
        batch_df = pd.DataFrame(buffer)
        batch_df.to_csv(output_csv, index=False, header=False, mode='a', encoding='utf-8-sig')

    # 7. 최종 리포트 생성 및 저장
    # (요청하신 포맷: 총 0건 레코드 중 0건 요청, 0건 오류, 0건 중 0건 일치 확인)
    cnt_valid_responses = cnt_requests - cnt_errors # 정상 응답 건수
    
    timestamp = datetime.now().strftime("%y%m%d_%H%M")
    report_filename = f"result_{timestamp}.txt"
    
    report_text = (
        f"총 {cnt_total}건 레코드 중 {cnt_requests}건 요청, "
        f"{cnt_errors}건 오류, "
        f"{cnt_valid_responses}건 중 {cnt_matched}건 일치 확인"
    )

    with open(report_filename, "w", encoding="utf-8") as f:
        f.write(report_text)

    print("\n[완료] 작업 종료.")
    print(f" - 결과 데이터: {output_csv}")
    print(f" - 결과 리포트: {report_filename}")
    print(f" - 내용: {report_text}")

def build_parser():
    """CLI 인자 파서. 기본값은 기존 인파일 설정 상수와 동일합니다(기존 동작 보존)."""
    parser = argparse.ArgumentParser(
        description="VWorld reverse-geocoding API로 법정동 CSV의 중심좌표를 검증합니다."
    )
    parser.add_argument(
        "-i", "--input-csv", default=INPUT_CSV,
        help="검증할 원본 CSV (기본값: LSCT_LAWDCD_coords_251117_revised.csv)",
    )
    parser.add_argument(
        "-o", "--output-csv", default=OUTPUT_CSV,
        help="결과 CSV (기본값: LSCT_LAWDCD_with_verified_address.csv)",
    )
    parser.add_argument(
        "--batch-size", type=int, default=BATCH_SIZE,
        help="중간 저장 단위 (기본값: 100)",
    )
    parser.add_argument(
        "--request-delay", type=float, default=REQUEST_DELAY,
        help="API 요청 간격(초) (기본값: 0.05)",
    )
    return parser


if __name__ == "__main__":
    args = build_parser().parse_args()
    main(
        input_csv=args.input_csv,
        output_csv=args.output_csv,
        batch_size=args.batch_size,
        request_delay=args.request_delay,
    )
