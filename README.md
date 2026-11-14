# korea-bjd-shp-to-csv

이 저장소는 대한민국 법정동 쉐이프파일(.shp)을 처리하고, 이를 법정동 마스터 코드와 병합·검증하고 dongnae 엔진용 데이터로 내보내는 다섯 가지 파이썬 유틸리티를 제공합니다.

* 가.  **`bjd_geometry_to_csv.py`**: 쉐이프파일에서 중심좌표, 반경(radius) 등을 추출합니다.
* 나.  **`bjd_csv_to_fulladdress.py`**: 법정동 마스터 파일에 위 좌표를 병합하고, 전체 주소(`full_address`)를 생성합니다.
* 다. **`bjd_csv_API_verification.py`**: 추출된 좌표가 실제 주소와 일치하는지 API로 검증합니다.
* 라. **`bjd_csv_apply_revisions.py`**: Exception 라벨을 붙이고, shp로 구할 수 없는 법정동의 수작업 보정을 명세 파일에서 적용합니다.
* 마. **`bjd_csv_to_dongnae.py`**: 보정 결과를 [dongnae](https://github.com/nash-dir/dongnae) 엔진용 CSV로 변환합니다(폐지 법정동 제외).

## 분석 대상 데이터

* **출처:** [브이월드 공간정보 다운로드(회원가입 필요)](https://www.vworld.kr/dtmk/dtmk_ntads_s001.do)
* **카테고리:** 국토관리 > 지역개발
* **데이터명:** 행정구역_리(법정동), 행정구역_읍면동(법정동), 법정동코드

## 라이선스
- **코드:** MIT (LICENSE 참조).
- **데이터:** 국토교통부 브이월드 홈페이지의 각 분석 대상 데이터 항목은 배포조건이 `CC BY-NC-ND`로 기재되어 있습니다.  
  - 본 저장소는 분석 대상 데이터를 통계적으로 분석한 '법정동별 행정구역 중심좌표, 최소 외접원 반지름' 등만 포함하며, 분석 대상인 경계 도형(.shp)을 포함하지 않습니다.
  - 지도상에 표현되는 자연적·인문적 현상은 사실 그 자체로서 저작권의 보호대상이 아니며, 표현방식과 취사선택의 창작성만 보호받을 수 있습니다(대법원 2010. 4. 15. 선고 2009도14298 판결 취지 참조).

===

## 가. bjd_geometry_to_csv.py
**대한민국 법정동 쉐이프파일(.shp) 전처리 및 CSV 변환 스크립트**

GeoPandas를 이용해 브이월드 등에서 제공하는 법정동(읍면동/리) 쉐이프파일을 읽어, 데이터 분석과 검색에 즉시 활용 가능한 **깔끔한 CSV 파일**로 변환하는 파이썬 유틸리티입니다.

### 주요 기능

1.  **지오메트리 연산:**
    * 법정동의 **중심좌표(위도, 경도)**를 자동으로 추출합니다.
    * **중심점:** 무게중심(centroid)을 씁니다. 단일 폴리곤인데 무게중심이 도형 밖에 찍히는 경우(도넛·초승달 형상)에는 도형 내부가 보장되는 대표점(`representative_point`)을 씁니다.
    * **떨어진 조각 제거:** 브이월드 원천 shp 일부 도형에는 본체와 같은 경도에서 위도만 약 0.9°(≈100km) 밀린 작은 조각이 붙어 있습니다(예: 하동군 하동읍 읍내리, 군산시 개사동). 본체에서 80km 이상 떨어져 있고 면적이 전체의 5% 미만인 조각은 계산에서 제외하고, 실행 로그에 `[보정]`으로 남깁니다. 실제 도서 지역(옹진·신안·여수 등)의 섬은 본체와의 간격이 70km 미만이라 유지됩니다.
    * **`radius_km` 계산:** 미터 단위 좌표계(EPSG:5179)로 변환하여 **최소 외접원 반지름**을 계산합니다(`shapely.minimum_bounding_radius`). 이는 특정 좌표와 법정동 중심지 사이의 거리를 적절히 조정하기 위한 매개변수입니다. 일례로, 특정 좌표에서 가장 가까운 법정동을 구할 때, '중심지와의 거리 - radius_km' 로직을 사용할 수 있습니다.

2.  **데이터 정제 (Cleansing):**
    * **코드 표준화:** 8자리(읍면동) 코드는 자동으로 '00'을 패딩하여 **10자리 표준 코드**로 변환합니다.
    * **오류 검증:** 코드가 숫자가 아니거나, 법정동명에 한글이 없는 유효하지 않은 데이터를 자동으로 필터링하여 `error.csv`로 분리합니다.
    
3.  **파일 통합:** 
    * 여러 개로 쪼개진 쉐이프파일(.shp)의 정보들을 하나의 CSV 파일로 병합합니다. 원본 추적을 위해 행별로 데이터가 유래한 파일명을 기록합니다. DB에 지오메트리를 업로드할 때 활용해 보세요.


### 사용법

#### 1. 환경 설정
```bash
pip install -r requirements.txt
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
# 기본값(input/ → output/, euc-kr)으로 실행
python bjd_geometry_to_csv.py

# 입력/출력 폴더나 인코딩을 바꾸려면 CLI 옵션을 사용합니다
python bjd_geometry_to_csv.py --input-dir ./input --output-dir ./output --encoding euc-kr
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
| `radius_km` | **최소 외접원 반지름 (중심지 거리 보정용)** | `2.45` (km) |
| `filename` | 원천 파일명 | `LSMD_...shp` |

---

## 나. bjd_csv_to_fulladdress
**대한민국 법정동 전체 리스트 매핑 스크립트**

이 저장소의 'bjd_geometry_to_csv.py'로 생성된 좌표/반경 데이터 ('bjd_yymmdd_HHMM_result.csv')를, 행정안전부 등에서 제공하는 법정동 코드 마스터 파일 (LSCT_LAWDCD.csv)에 병합(Join)하기 위한 유틸리티입니다.

### 주요 기능

1.  **전체 주소 생성 (full_address):**
    * LSCT_LAWDCD.csv의 'SIDO_NM', 'SGG_NM', 'UMD_NM', 'RI_NM' 컬럼을 조합하여 'full_address'라는 새로운 컬럼을 생성합니다.
    * 주소 중간에 NaN 값이 있어도 안전하게 처리하며, "서울특별시  종로구"처럼 중간에 공백이 2칸 이상 생기거나 " 서울특별시 "처럼 앞뒤에 공백이 생기는 문제를 정규표현식으로 자동 정제합니다.
    * 생성된 full_address 열은 RI_NM 열 바로 뒤에 삽입됩니다.
2.  **좌표 데이터 병합 (Left Join):**
    * 법정동 마스터 파일(LSCT_LAWDCD.csv)을 기준으로, bjd_yymmdd_HHMM_result.csv의 좌표 정보를 left join 합니다.
    * **매칭 키:** LSCT_LAWDCD.csv의 **LAWD_CD** ↔ bjd_yymmdd_HHMM_result.csv의 **legal_dong_code**
    * **중복 처리:** bjd_..._result.csv에 동일한 legal_dong_code가 여러 개 있을 경우, 맨 처음 발견된 1개의 행만 사용합니다.
3.  **파일 통합:** 
    * 결과물은 LSCT_LAWDCD_coords.csv로 저장됩니다.
    * 만약 동일한 이름의 파일이 이미 존재하면, 덮어쓰지 않고 LSCT_LAWDCD_coords-1.csv, LSCT_LAWDCD_coords-2.csv와 같이 자동으로 번호를 붙여 저장합니다.


### 요구 사항
    * Python 3+
    * Pandas 라이브러리 (pip install pandas)


### 사용법

이 스크립트(bjd_csv_to_fulladdress.py)와 아래 파일을 동일한 폴더에 넣고 스크립트를 실행합니다.

*   **LSCT_LAWDCD.csv** (법정동 코드 마스터 원본)
*   **bjd_yymmdd_HHMM_result.csv** 

```bash
# 기본 파일명으로 실행
python bjd_csv_to_fulladdress.py

# 파일명을 직접 지정 (--data-file 등은 -h 로 전체 옵션 확인)
python bjd_csv_to_fulladdress.py --base-file LSCT_LAWDCD.csv --data-file bjd_251117_2212_result.csv
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

이 저장소의 bjd_csv_to_fulladdress로 생성된 CSV 딕셔너리의 중심좌표가, 실제 해당 행정구역(읍면동/리) 내부에 위치하는지 검증하는 스크립트입니다. 브이월드의 Reverse Geocoding API를 사용하여 좌표를 주소로 변환하고, 이를 원본 법정동 명칭과 대조합니다.

### 주요 기능

1. **좌표 유효성 검증 (Reverse Geocoding):**
   * CSV에 기록된 중심좌표(위도, 경도)를 API에 전송하여 실제 주소(지번/도로명)를 받아옵니다.
   * 추출된 중심점이 실제 행정구역 명칭(리, 읍면동)과 일치하는지 텍스트 매칭을 통해 검증합니다.
   
2. **검증 결과 라벨링 (verified):**
   * **1 (일치):** API가 반환한 주소에 원본 데이터의 '리' 또는 '읍면동' 명칭이 포함된 경우 (신뢰할 수 있는 좌표).
   * **0 (불일치):** 좌표가 가리키는 실제 주소가 원본 법정동과 다른 경우 (주로 도넛 모양, 초승달 모양 등 기형적인 행정구역에서 중심점이 외부에 찍힌 경우).
   * **NULL (확인 불가):** API 오류, 주소 미존재, 혹은 좌표값이 없는 경우.

3. **판정 방식:**
   * 지번 주소만 요청합니다(`type=parcel`). 도로명 주소에는 리 명칭이 없어 올바른 좌표도 불일치로 판정되기 때문입니다.
   * 명칭은 공백 기준 토큰 단위로 비교합니다('상리'가 '신상리'에 일치하는 오탐 방지).
   * 통신오류는 최대 3회 재시도하고, 오류 칸에는 예외 종류만 기록합니다(요청 URL에 포함된 API 키가 결과 CSV에 남지 않도록).

4. **결과 리포트 생성:**
   * 작업 완료 후, 전체 요청 건수와 일치/불일치 건수를 요약한 txt 리포트를 자동으로 생성합니다.

### 사용법

#### 1. API 키 발급 및 환경 설정
브이월드 오픈API에서 인증키를 발급받아야 합니다.
유틸리티와 같은 경로에 .env 파일을 만들고, 아래와 같이 키를 입력합니다.

```bash
API_KEY={브이월드_인증키_입력}
```

#### 2. 실행
검증할 CSV 파일명 등은 CLI 옵션으로 지정합니다(전체 옵션은 `-h` 참고).

```bash
# 기본 파일명으로 실행
python bjd_csv_API_verification.py

# 입력/출력 CSV를 직접 지정
python bjd_csv_API_verification.py --input-csv LSCT_LAWDCD_coords_251117_revised.csv --output-csv result.csv
```

### 결과물 명세

기존 CSV 컬럼 뒤에 아래 두 가지 컬럼이 추가됩니다.

| 컬럼명 | 설명 | 예시 |
| :--- | :--- | :--- |
| center_address | API가 반환한 실제 주소 | 경상북도 예천군 은풍면 시항리 산 12-1 |
| verified | 검증 결과 (1:일치, 0:불일치, 빈칸:확인불가) | 1 |


## 라. bjd_csv_apply_revisions

**Exception 라벨 + 수작업 보정 적용 유틸리티**

shp만으로는 좌표를 얻을 수 없거나 부정확한 법정동(미수복지역, 행정동 중첩, 도형 누락 등 43건)을 [`revisions/manual_revisions.csv`](revisions/manual_revisions.csv) 명세대로 보정하고, 모든 행에 `Exception` 라벨을 붙입니다. 라벨 정의와 보정 사유는 [`revision_report_251117.md`](results/251117/revision_report_251117.md)에 있습니다.

* 라벨: 폐지 법정동(`DEL_DT` 기재)은 `1`, 시도·시군구 단위는 `2`, 나머지는 `0`. 명세의 행은 명세의 라벨(`3`·`4`·`5` 등).
* 명세의 `method`:

| method | 동작 | 예 |
| :--- | :--- | :--- |
| `none` | 좌표 없음 | 미수복지역 29건 |
| `copy` | `source` 법정동의 중심좌표·반경을 그대로 사용 | 해남읍 부호리 → 내사리 |
| `proxy` | 대체좌표(주민센터 등) + 명세의 `radius_km`, 비어 있으면 `source` 법정동들의 반경 평균 | 마포구 서교동 |
| `manual` | 명세의 중심좌표·반경을 그대로 사용 | 남이면 척산리 |

* `copy`·`proxy`의 반경은 실행할 때의 계산값에서 다시 구하므로, 반경 계산 방식이 바뀌어도 보정 행이 옛 값에 머무르지 않습니다.
* 명세가 shp에서 계산된 좌표를 덮어쓰게 되면(원천 데이터가 고쳐진 경우) `[확인 필요]`로 알려 줍니다.

```bash
python bjd_csv_apply_revisions.py -i results/261102/LSCT_LAWDCD_coords_261102.csv -o results/261102/LSCT_LAWDCD_coords_261102_revised.csv
```

## 마. bjd_csv_to_dongnae

**보정 결과 → dongnae 엔진용 CSV 변환 유틸리티**

`bjd_csv_apply_revisions.py` 결과물을 dongnae 스키마(`dnid`, `dnname`, `dnlatitude`, `dnlongitude`, `dnradius`)로 변환합니다.

* 좌표가 없는 행과 **폐지된 법정동(`DEL_DT` 기재)** 은 제외합니다. 구 코드 shp(예: 2024. 1. 개편 전 `LSMD_ADM_SECT_RI_45_202401`)가 `input/`에 남아 있으면 폐지 코드에도 좌표가 붙어, 같은 지역이 신·구 코드로 중복되기 때문입니다.

```bash
python bjd_csv_to_dongnae.py -i results/261102/LSCT_LAWDCD_coords_261102_revised.csv -o results/261102/dongnaeKR_261102.csv
```

## 바. 산출 결과물
### `/results/251117`
#### LSCT_LAWDCD_coords_251117.csv
*   브이월드에서 `2025. 11. 17.자 데이터`를 다운로드받아 계산한 결과물입니다. 
*   전체 27,647개 법정동 코드 레코드 중 21,687건의 중심지 좌표와 `radius_km`이 포함되어 있습니다. 이 파일에 포함된 `radius_km`은 과거 로직에 따라 '외접 직사각형 대각선 길이 절반'으로 계산되어 있는 점에 유의 부탁드립니다. 이후 보다 정확한 계산을 위해 '외접원 반지름'으로 대체하였지만, 과거 데이터까지 소급해서 변경하진 않았습니다(변경이 반영된 데이터는 `251130/LSCT_LAWDCD_coords_251130_revised_verified.csv` 참조).
*   나머지 5,960건은 브이월드 2025. 11.자 shp 파일에 지오메트리가 포함되지 않았거나 매핑 오류가 발생하는 등으로 좌표 정보가 누락되었습니다.
*   누락된 5,960건 중 5,636건은 폐쇄된 법정동입니다(DEL_DT에 삭제일 기재). 이를 제외한 324건 중 281건은 도/시군구 단위 상위행정구역이며, 나머지 43건은 아래 목록과 같습니다. 
*   아래 표의 43건은 브이월드에서 제공하는 쉐이프파일(.shp)에는 존재하지 않으나, 행정안전부 법정동 마스터 코드(`LSCT_LAWDCD.csv`)에는 존재하는 43개 법정동 목록입니다.
*   이 데이터는 `bjd_csv_to_fulladdress.py` 스크립트 실행 시, `full_address`는 생성되지만 `center_latitude` 등 좌표값이 `null` (NaN)로 남게 되는 대상입니다.

#### LSCT_LAWDCD_coords_251117_revised.csv
*   위 `LSCT_LAWDCD_coords_251117.csv`에서 '지오메트리 누락 데이터 목록 43건' 등 결측치를 수동으로 보정하고, 법정동별 Exceptions 코드를 라벨링한 데이터입니다. 
*   라벨링 테이블 및 결측치 fill in 로직은 `revision_report_251117.md`에 설명하였습니다.

#### LSCT_LAWDCD_coords_251117_revised_verified.csv
*   위 `LSCT_LAWDCD_coords_251117_revised.csv`의 중심지 좌표를 브이월드 API로 reverse-geocoding한 주소(`center_address`), 그리고 해당 주소가 딕셔너리 내 `full_address`와 일치하는지(`verified`) 추가로 검증한 자료입니다.
*   대한민국 법정동코드가 존재하는 총 27,647건의 레코드 중 중심좌표가 수록된 21,701건을 API에 요청하였습니다. 오류 175건을 제외하고 검증 가능한 나머지 21,526건 중 21,367건은 `full_address`와 일치하는 것으로 확인됩니다(정확도 99.26%).
*   `verified=0`인 법정동을 몇 개 선정해 확인해 보니 대부분 도넛, 초승달과 같은 형상이었습니다.

### `/results/251130`
#### LSCT_LAWDCD_coords_251130.csv
*   `LSCT_LAWDCD_coords_251117.csv`(보정·검증 전 base)에서 `radius_km`만 **최소 외접원 반지름**으로 대체한 파일입니다. 결측치 수동 보정과 API 검증은 반영되지 않았습니다(`Exception`·`center_address`·`verified` 컬럼 없음).
#### LSCT_LAWDCD_coords_251130_revised_verified.csv
*   본 데이터는 2025. 11. 17.자 `LSCT_LAWDCD_coords_251117_revised_verified.csv`에서 `radius_km`만 **지오메트리 최소 외접원 반지름**으로 대체한 것입니다.
*   ⚠️ 이 파일의 좌표·반경에는 아래 `261102`에서 보정한 원천 데이터 오류(떨어진 조각으로 반경이 50km 이상 부풀려진 7건 등)가 남아 있습니다. 또한 폐지된 전라북도(45) 리 1,463건에 좌표가 붙어 있으며 `Exception=0`으로 라벨되어 있고(`DEL_DT=20240117`), 수작업 보정 11건의 반경이 `251117`의 옛 계산식 값 그대로이고, 척산리 반경(1.526)은 도형과 맞지 않습니다. 자세한 내용은 `261102/revision_report_261102.md` 참조.

### `/results/261102`
같은 원천 데이터(브이월드 2025. 11.자 shp, 전북 리는 2024. 1.자 포함)를 보정된 파이프라인으로 다시 계산한 결과물입니다.

#### LSCT_LAWDCD_coords_261102.csv
*   `bjd_geometry_to_csv.py`(떨어진 조각 제거, 도형 내부 중심점, 정확한 외접원 반지름) → `bjd_csv_to_fulladdress.py`로 생성한 병합 결과입니다. 수작업 보정·API 검증은 반영되지 않았습니다.
#### LSCT_LAWDCD_coords_261102_revised.csv
*   위 파일에 `bjd_csv_apply_revisions.py`로 Exception 라벨과 수작업 보정 43건을 적용한 결과입니다. 이전 대비 바뀐 값(보정 행의 반경, 척산리 반경, 폐지 전북 리 라벨)은 [`revision_report_261102.md`](results/261102/revision_report_261102.md)에 정리했습니다. API 검증은 다시 하지 않았습니다.
*   **법정동 코드, 전체 주소, 중심좌표 등 최종 데이터만 필요하신 분은 이것만 다운받으셔도 됩니다.**
#### dongnaeKR_261102.csv
*   위 파일을 `bjd_csv_to_dongnae.py`로 변환한 dongnae 엔진용 데이터(20,238건)입니다. 폐지 법정동 1,463건은 제외했습니다.
*   이전 dongnae-kr 데이터(`dongnaeKR_251130.csv`) 대비, ground truth(법정동 폴리곤 내부 무작위 좌표) 약 2만 점 표본 기준:

| | 이전(251130) | 261102 |
| :--- | :--- | :--- |
| Top-1 (해당 법정동 또는 상위 읍면동 일치) | 58.2% | **69.6%** |
| Top-3 (해당 법정동 정확히 포함) | 65.2% | **74.9%** |

*   표본은 법정동마다 같은 개수의 점을 뽑은 것이라 면적·인구 가중치가 없습니다. dongnae README의 브이월드 API 기준 벤치마크와는 평가 방식이 달라 수치를 직접 비교할 수 없습니다.


## 사. optimize — 정확도 평가와 반경 조정(실험)

`optimize/`에는 dongnae 데이터의 정확도를 재고, 반경을 조정해 보는 스크립트가 있습니다. dongnae 엔진이 필요합니다(`pip install -e ".[optimize]"` 또는 `pip install "dongnae>=0.3.0" numpy`). 리포지토리 루트에서 `python -m`으로 실행합니다. 결과물은 `optimize/output/`(gitignore)에 저장됩니다.

| 스크립트 | 하는 일 |
| :--- | :--- |
| `optimize.generate_ground_truth` | shp 폴리곤마다 내부 무작위 좌표를 뽑아 정답 라벨(10자리 법정동 코드)을 붙입니다. 떨어진 조각은 제외하고, 미터 좌표계에서 균일하게 뽑습니다. 법정동당 50개 기준 약 108만 개, 십여 초. |
| `optimize.evaluate` | dongnae CSV 하나 이상의 Top-1(정답 코드 또는 상위 읍면동)·Top-3(정답 코드 포함) 정확도를 잽니다. 여러 CSV를 줄 때는 모든 CSV에 있는 코드의 지점만 써서 분모를 맞춥니다. |
| `optimize.optimize_radius` | ground truth로 반경을 투표식으로 조정합니다(실험용). 결과는 반드시 `evaluate`로 원본과 비교하십시오. |

```bash
python -m optimize.generate_ground_truth -i input -o optimize/output/ground_truth.csv
python -m optimize.evaluate results/261102/dongnaeKR_261102.csv
python -m optimize.optimize_radius -d results/261102/dongnaeKR_261102.csv -o optimize/output/optimized.csv
```

* 2025년에 쓰던 이전 스크립트(`generate_ground_truth_multi.py`, `optimize_dnradius*.py`)와 그 산출물은 `optimize/legacy/`(gitignore)로 옮겼습니다. 이전 ground truth는 읍면동 코드를 8자리로 저장해 dongnae의 10자리 코드와 매칭되지 않았고, 그래서 읍면동 지점이 평가·최적화에서 빠졌습니다. CUDA 버전은 코드를 정수로 읽어 문자열 코드와 매칭되지 않았습니다. 이전 최적화 결과(`dongnaeKR_251130_optimized*.csv`)는 배포된 적이 없습니다.
* 반경 조정의 한계: 상위 읍면동의 원은 하위 리 지점을 항상 포함하므로, 현재 투표 규칙에서는 침범(FP) 표가 대부분 상위 읍면동에 몰립니다. 계층 구조를 정리하기 전에는 큰 개선을 기대하기 어렵습니다.
* 참고(2026. 11.): `261102` 데이터에 ground truth 10%로 3 epoch(기본 학습률) 돌린 결과, 같은 표본 기준 Top-1 69.37% → 69.38%, Top-3 74.83% → 74.87%로 사실상 변화가 없었습니다.

## 개발 / 테스트

순수 함수(컬럼 매핑, 코드 패딩, 떨어진 조각 제거, 중심점, 주소 정제, 검증 라벨링, 수작업 보정 적용, dongnae 변환, ground truth 샘플링·채점·반경 갱신) 위주의 단위 테스트가 `tests/`에 있습니다.
무거운 의존성(geopandas 등)은 실행 함수 내부에서 lazy import 되므로, 린트/테스트에는 `pandas`, `shapely`, `requests`만 있으면 됩니다.

```bash
pip install pandas numpy shapely requests pytest ruff==0.15.9
ruff check .
pytest
```

CI(`.github/workflows/ci.yml`)에서 push/PR 시 `ruff`와 `pytest`를 자동 실행합니다.
