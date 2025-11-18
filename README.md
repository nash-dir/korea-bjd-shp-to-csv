# korea-bjd-shp-to-csv

이 저장소는 대한민국 법정동 쉐이프파일(.shp)을 처리하고, 이를 법정동 마스터 코드와 병합하는 두 가지 파이썬 유틸리티를 제공합니다.

* 가.  **`bjd_geometry_to_csv.py`**: 쉐이프파일에서 중심좌표, 반경(radius) 등을 추출합니다.
* 나.  **`bjd_csv_to_fulladdress.py`**: 법정동 마스터 파일에 위 좌표를 병합하고, 전체 주소(`full_address`)를 생성합니다.

## 데이터 출처

* **출처:** [브이월드 공간정보 다운로드(회원가입 필요)](https://www.vworld.kr/dtmk/dtmk_ntads_s001.do)
* **카테고리:** 국토관리 > 지역개발
* **데이터명:** 행정구역_리(법정동), 행정구역_읍면동(법정동), 법정동코드

===

## 가. bjd_geometry_to_csv.py
**대한민국 법정동 쉐이프파일(.shp) 전처리 및 CSV 변환 스크립트**

GeoPandas를 이용해 브이월드 등에서 제공하는 법정동(읍면동/리) 쉐이프파일을 읽어, 데이터 분석과 검색에 즉시 활용 가능한 **깔끔한 CSV 파일**로 변환하는 파이썬 유틸리티입니다.

### 주요 기능

1.  **지오메트리 연산:**
    * 법정동의 **중심좌표(위도, 경도)**를 자동으로 추출합니다.
    * **`radius_km` 계산:** 미터 단위 좌표계(EPSG:5179)로 변환하여 외접 사각형의 대각선 절반 길이를 계산합니다. 이는 특정 좌표와 법정동 중심지 사이의 거리를 적절히 조정하기 위한 매개변수입니다. 일례로, 특정 좌표에서 가장 가까운 법정동을 구할 때, '중심지와의 거리 - radius_km' 로직을 사용할 수 있습니다.

2.  **데이터 정제 (Cleansing):**
    * **코드 표준화:** 8자리(읍면동) 코드는 자동으로 '00'을 패딩하여 **10자리 표준 코드**로 변환합니다.
    * **오류 검증:** 코드가 숫자가 아니거나, 법정동명에 한글이 없는 유효하지 않은 데이터를 자동으로 필터링하여 `error.csv`로 분리합니다.
    
3.  **파일 통합:** 
    * 여러 개로 쪼개진 쉐이프파일(.shp)의 정보들을 하나의 CSV 파일로 병합합니다. 원본 추적을 위해 행별로 데이터가 유래한 파일명을 기록합니다. DB에 지오메트리를 업로드할 때 활용해 보세요.


### 사용법

#### 1. 환경 설정
```bash
pip install geopandas pandas tqdm
```

#### 2. 디렉토리 구조 및 실행
다운로드한 `.shp` 파일들을 `input` 폴더에 넣고 스크립트를 실행합니다.

```text
korea-bjd-shp-to-csv/
├── input/                 # 여기에 .shp 파일들을 넣으세요 (LSMD_...)
├── output/                # 결과물이 여기에 생성됩니다
└── bjd_geometry_to_csv.py # 실행 스크립트
```

```bash
python bjd_geometry_to_csv.py
```

### 결과물 명세

생성되는 CSV 파일의 컬럼 구성입니다.

| 컬럼명 | 설명 | 예시 |
| :--- | :--- | :--- |
| `legal_dong_code` | 법정동코드 (10자리 표준) | `4159025321` |
| `legal_dong_tip` | 법정동명 마지막 단위 | `상리` |
| `COL_ADM_SECT_CD` | 원천시군구코드 | `41590` |
| `SGG_OID` | 원천도형_ID | `1410` |
| `center_latitude` | 중심점 위도 (EPSG:4326) | `37.8123...` |
| `center_longitude` | 중심점 경도 (EPSG:4326) | `127.456...` |
| `radius_km` | **외접 직사각형 대각선 길이 절반 (중심지 거리 보정용)** | `2.45` (km) |
| `filename` | 원천 파일명 | `LSMD_...shp` |

---

## 나. bjd_csv_to_fulladdress
**대한민국 법정동 전체 리스트 매핑 스크립트**

이 저장소의 bjd_geometry_to_csv.py로 생성된 좌표/반경 데이터 (bjd_mmddyy_HHMM_result.csv)를, 행정안전부 등에서 제공하는 법정동 코드 마스터 파일 (LSCT_LAWDCD.csv)에 병합(Join)하기 위한 유틸리티입니다.

### 주요 기능

1.  **전체 주소 생성 (full_address):**
    * LSCT_LAWDCD.csv의 'SIDO_NM', 'SGG_NM', 'UMD_NM', 'RI_NM' 컬럼을 조합하여 'full_address'라는 새로운 컬럼을 생성합니다.
    * 주소 중간에 NaN 값이 있어도 안전하게 처리하며, "서울특별시  종로구"처럼 중간에 공백이 2칸 이상 생기거나 " 서울특별시 "처럼 앞뒤에 공백이 생기는 문제를 정규표현식으로 자동 정제합니다.
    * 생성된 full_address 열은 RI_NM 열 바로 뒤에 삽입됩니다.
2.  **좌표 데이터 병합 (Left Join):**
    * 법정동 마스터 파일(LSCT_LAWDCD.csv)을 기준으로, bjd_mmddyy_HHMM_result.csv의 좌표 정보를 left join 합니다.
    * **매칭 키:** LSCT_LAWDCD.csv의 **LAWD_CD** ↔ bjd_mmddyy_HHMM_result.csv의 **legal_dong_code**
    * **중복 처리:** bjd_..._result.csv에 동일한 legal_dong_code가 여러 개 있을 경우, 맨 처음 발견된 1개의 행만 사용합니다.
3.  **파일 통합:** 
    * 결과물은 LSCT_LAWDCD_coords.csv로 저장됩니다.
    * 만약 동일한 이름의 파일이 이미 존재하면, 덮어쓰지 않고 LSCT_LAWDCD_coords-1.csv, LSCT_LAWDCD_coords-2.csv와 같이 자동으로 번호를 붙여 저장합니다.


### 요구 사항
    * Python 3+
    * Pandas 라이브러리 (pip install pandas)


### 사용법

이 스크립트(bjd_csv_to_fulladdress.py)와 아래 파일을 동일한 폴더에 넣고 스크립트를 실행합니다. 파일명은 스크립트 ln.33 DATA_FILE 변수에서 수정 가능합니다.

*   **LSCT_LAWDCD.csv** (법정동 코드 마스터 원본)
*   **bjd_mmyydd_HHMM_result.csv** 

```bash
python bjd_csv_to_fulladdress.py
```

### 결과물 명세

| 컬럼명 | 설명 | 예시 |
| :--- | :--- | :--- |
| `LAWD_CD` | 법정동코드 | `4790043030` |
| `SIDO_NM` | 시도 | `경상북도` |
| `SGG_NM` | 시군구 | `예천군` |
| `UMD_NM` | 읍면동 | `은풍면` |
| `RI_NM` | 리 | `시항리` |
| `full_address` | 전체 주소 | `경상북도 예천군 은풍면 시항리` |
| `CRE_DT` | 등록일 | `20160201` |
| `DEL_DT` | 삭제일 | `20250808` |
| `OLD_LAWDCD` | 이전 법정동코드 | `20250808` |
| `FRST_REGIST_DT` | 최초 등록일 | `20250808` |
| `LAST_UPDT_DT` | 최종 수정일 | `20250808` |
| `COL_ADM_SECT_CD` | 원천시군구코드 | `47900` |
| `SGG_OID` | 원천도형_ID | `149` |


## 다. 산출 결과물
### LSCT_LAWDCD_coords_251117.csv
*   브이월드에서 **2025. 11. 17.자 데이터를 다운로드받아 산출한 결과물**을 함께 업로드해 드립니다. 
*   법정동 코드, 전체 주소, 중심좌표 등 데이터만 필요하신 분은 이것만 다운받으셔도 됩니다.
*   전체 27,647개 법정동 코드 레코드 중 21,687건의 중삼지 좌표와 radius_km이 포함되어 있습니다. 나머지 5,960건은 브이월드 2025. 11.자 shp 파일에 지오메트리가 포함되지 않았거나 매핑 오류가 발생하는 등으로 좌표 정보가 누락되었습니다.
*   누락된 5,960건 중 5,636건은 폐쇄된 법정동입니다(DEL_DT에 삭제일 기재). 이를 제외한 324건 중 281건은 도/시군구 단위 상위행정구역이며, 나머지 43건은 아래 목록과 같습니다. 
*   아래 표의 43건은 VWorld에서 제공하는 쉐이프파일(.shp)에는 존재하지 않으나, 행정안전부 법정동 마스터 코드(`LSCT_LAWDCD.csv`)에는 존재하는 43개 법정동 목록입니다.
*   이 데이터는 `bjd_csv_to_fulladdress.py` 스크립트 실행 시, `full_address`는 생성되지만 `center_latitude` 등 좌표값이 `null` (NaN)로 남게 되는 대상입니다.

### LSCT_LAWDCD_coords__251117_revised.csv
*   위 '**LSCT_LAWDCD_coords_251117.csv**에서 '지오메트리 누락 데이터 목록 43건' 등 결측치를 수동으로 보정하고, 법정동별 Exceptions 코드를 라벨링한 데이터입니다. 
*   법정동 코드, 전체 주소, 중심좌표 등 최종 데이터만 필요하신 분은 이것만 다운받으셔도 됩니다.
*   라벨링 테이블 및 결측치 fill in 로직은 **revision_report_251117.md**에 설명하였습니다.

===

## 라이선스
MIT License
