# korea-bjd-shp-to-csv

이 저장소는 대한민국 법정동 쉐이프파일(.shp)을 처리하고, 이를 법정동 마스터 코드와 병합하는 두 가지 파이썬 유틸리티를 제공합니다.

* 가.  **`bjd_geometry_to_csv.py`**: 쉐이프파일에서 중심좌표, 반경(radius) 등을 추출합니다.
* 나.  **`bjd_csv_to_fulladdress.py`**: 법정동 마스터 파일에 위 좌표를 병합하고, 전체 주소(`full_address`)를 생성합니다.
* 다. **`bjd_csv_API_verification.py`**: 추출된 좌표가 실제 주소와 일치하는지 API로 검증합니다.

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
    * **`radius_km` 계산:** 미터 단위 좌표계(EPSG:5179)로 변환하여 **최소 외접원 반지름**을 계산합니다. 이는 특정 좌표와 법정동 중심지 사이의 거리를 적절히 조정하기 위한 매개변수입니다. 일례로, 특정 좌표에서 가장 가까운 법정동을 구할 때, '중심지와의 거리 - radius_km' 로직을 사용할 수 있습니다.

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
| `radius_km` | **외접원 반지름 (중심지 거리 보정용)** | `2.45` (km) |
| `filename` | 원천 파일명 | `LSMD_...shp` |

---

## 나. bjd_csv_to_fulladdress
**대한민국 법정동 전체 리스트 매핑 스크립트**

이 저장소의 'bjd_geometry_to_csv.py'로 생성된 좌표/반경 데이터 ('bjd_mmddyy_HHMM_result.csv')를, 행정안전부 등에서 제공하는 법정동 코드 마스터 파일 (LSCT_LAWDCD.csv)에 병합(Join)하기 위한 유틸리티입니다.

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
*   **bjd_yymmdd_HHMM_result.csv** 

```bash
python bjd_csv_to_fulladdress.py
```

### 결과물 명세 

* 설명을 위한 예시이며, 실제 데이터와 다릅니다.

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
| `OLD_LAWDCD` | 이전 법정동코드 | `4473033500` |
| `FRST_REGIST_DT` | 최초 등록일 | `20250808` |
| `LAST_UPDT_DT` | 최종 수정일 | `20250808` |
| `COL_ADM_SECT_CD` | 원천시군구코드 | `47900` |
| `SGG_OID` | 원천도형_ID | `149` |


## 다. bjd_csv_API_verification

**브이월드 reverse-geocoding API를 활용한 법정동 CSV 딕셔너리 중심좌표 검증 유틸리티**

이 저장소의 bjd_csv_to_fulladdress로 생성된 CSV 딕셔너리의 중심좌표가, 실제 해당 행정구역(읍면동/리) 내부에 위치하는지 검증하는 스크립트입니다. V-World의 Reverse Geocoding API를 사용하여 좌표를 주소로 변환하고, 이를 원본 법정동 명칭과 대조합니다.

### 주요 기능

1. **좌표 유효성 검증 (Reverse Geocoding):**
   * CSV에 기록된 중심좌표(위도, 경도)를 API에 전송하여 실제 주소(지번/도로명)를 받아옵니다.
   * 추출된 중심점이 실제 행정구역 명칭(리, 읍면동)과 일치하는지 텍스트 매칭을 통해 검증합니다.
   
2. **검증 결과 라벨링 (verified):**
   * **1 (일치):** API가 반환한 주소에 원본 데이터의 '리' 또는 '읍면동' 명칭이 포함된 경우 (신뢰할 수 있는 좌표).
   * **0 (불일치):** 좌표가 가리키는 실제 주소가 원본 법정동과 다른 경우 (주로 도넛 모양, 초승달 모양 등 기형적인 행정구역에서 중심점이 외부에 찍힌 경우).
   * **NULL (확인 불가):** API 오류, 주소 미존재, 혹은 좌표값이 없는 경우.

3. **결과 리포트 생성:**
   * 작업 완료 후, 전체 요청 건수와 일치/불일치 건수를 요약한 txt 리포트를 자동으로 생성합니다.

### 사용법

#### 1. API 키 발급 및 환경 설정
브이월드 오픈API에서 인증키를 발급받아야 합니다.
유틸리티와 같은 경로에 .env 파일을 만들고, 아래와 같이 키를 입력합니다.

```bash
API_KEY={브이월드_인증키_입력}
```

#### 2. 실행
검증할 CSV 파일명은 스크립트 상단의 INPUT_CSV 변수에서 수정할 수 있습니다.

```bash
python bjd_csv_API_verification.py
```

### 결과물 명세

기존 CSV 컬럼 뒤에 아래 두 가지 컬럼이 추가됩니다.

| 컬럼명 | 설명 | 예시 |
| :--- | :--- | :--- |
| center_address | API가 반환한 실제 주소 | 경상북도 예천군 은풍면 시항리 산 12-1 |
| verified | 검증 결과 (1:일치, 0:불일치, 빈칸:확인불가) | 1 |


## 라. 산출 결과물
### `/results/251117`
#### LSCT_LAWDCD_coords_251117.csv
*   브이월드에서 `2025. 11. 17.자 데이터`를 다운로드받아 계산한 결과물입니다. 
*   전체 27,647개 법정동 코드 레코드 중 21,687건의 중심지 좌표와 `radius_km`이 포함되어 있습니다. 이 파일에 포함된 `radius_km`은 과거 로직에 따라 '외접 직사각형 대각선 길이 절반'으로 계산되어 있는 점에 유의 부탁드립니다. 이후 보다 정확한 계산을 위해 '외접원 반지름'으로 대체하였지만, 과거 데이터까지 소급해서 변경하진 않았습니다(변경이 반영된 데이터는 `251130/LSCT_LAWDCD_coords_251130_revised_verified.csv` 참조).
*   나머지 5,960건은 브이월드 2025. 11.자 shp 파일에 지오메트리가 포함되지 않았거나 매핑 오류가 발생하는 등으로 좌표 정보가 누락되었습니다.
*   누락된 5,960건 중 5,636건은 폐쇄된 법정동입니다(DEL_DT에 삭제일 기재). 이를 제외한 324건 중 281건은 도/시군구 단위 상위행정구역이며, 나머지 43건은 아래 목록과 같습니다. 
*   아래 표의 43건은 VWorld에서 제공하는 쉐이프파일(.shp)에는 존재하지 않으나, 행정안전부 법정동 마스터 코드(`LSCT_LAWDCD.csv`)에는 존재하는 43개 법정동 목록입니다.
*   이 데이터는 `bjd_csv_to_fulladdress.py` 스크립트 실행 시, `full_address`는 생성되지만 `center_latitude` 등 좌표값이 `null` (NaN)로 남게 되는 대상입니다.

#### LSCT_LAWDCD_coords_251117_revised.csv
*   위 `LSCT_LAWDCD_coords_251117.csv`에서 '지오메트리 누락 데이터 목록 43건' 등 결측치를 수동으로 보정하고, 법정동별 Exceptions 코드를 라벨링한 데이터입니다. 
*   라벨링 테이블 및 결측치 fill in 로직은 `revision_report_251117.md`에 설명하였습니다.

#### LSCT_LAWDCD_coords_251117_revised_verified.csv
*   위 `LSCT_LAWDCD_coords_251117_revised.csv`의 중심지 좌표를 Vworld API로 reverse-geocoding한 주소(`center_address`), 그리고 해당 주소가 딕셔너리 내 `full_address`와 일치하는지(`verified`) 추가로 검증한 자료입니다.
*   대한민국 법정동코드가 존재하는 총 27,647건의 레코드 중 중심좌표가 수록된 21,701건을 API에 요청하였습니다. 오류 175건을 제외하고 검증 가능한 나머지 21,526건 중 21,367건은 `full_address`와 일치하는 것으로 확인됩니다(정확도 99.26%).
*   `verified=0`인 법정동을 몇 개 선정해 확인해 보니 대부분 도넛, 초승달과 같은 형상이었습니다.

### `/results/251130`
#### LSCT_LAWDCD_coords_251130_revised_verified.csv
*   본 데이터는 2025. 11. 17.자 `LSCT_LAWDCD_coords_251117_revised_verified.csv`에서 `radius_km`만 **지오메트리 최소 외접원 반지름**으로 대체한 것입니다.
*   **법정동 코드, 전체 주소, 중심좌표 등 최종 데이터만 필요하신 분은 이것만 다운받으셔도 됩니다.**


## 라이선스
MIT License
