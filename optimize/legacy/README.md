# optimize/legacy — 2025년 반경 최적화 실험 (사용 중지)

2025. 11.에 `dongnaeKR_251130.csv`의 반경을 ground truth로 조정해 보던 스크립트입니다.
기록용으로만 남겨 두며, **실행하지 마십시오.** 현재 스크립트는 상위 폴더의
`generate_ground_truth.py` · `evaluate.py` · `optimize_radius.py`입니다.

| 파일 | 내용 | 알려진 문제 |
| :--- | :--- | :--- |
| `generate_ground_truth_multi.py` | 법정동당 250개, 총 약 525만 개 ground truth 생성 | 읍면동 코드를 8자리로 저장해 dongnae의 10자리 `dnid`와 매칭되지 않음. 떨어진 조각(원천 데이터 오류)에서도 샘플링 |
| `optimize_dnradius.py` | CPU 멀티프로세스 투표식 반경 조정 | 위 ground truth 때문에 읍면동 지점이 전부 건너뛰어짐 |
| `optimize_dnradius_cuda.py`, `optimize_dnradius_cuda2.py` | PyTorch GPU 버전 | ground truth를 dtype 지정 없이 읽어 코드가 정수가 되고, 문자열 `dnid`와 매칭되지 않음 |

* 모든 스크립트에 작성자 PC의 절대 경로가 하드코딩되어 있고, 엔진을 `../py-core`에서 불러오도록 되어 있어 이 저장소에서는 그대로 실행되지 않습니다.
* 이 스크립트들의 결과물(`dongnaeKR_251130_optimized*.csv`)은 배포된 적이 없습니다.
* 생성된 ground truth와 결과 CSV는 저장소에 포함하지 않습니다. ground truth는 폴리곤 내부 좌표를 촘촘히 담고 있어 경계 도형을 사실상 재현할 수 있으므로, 원천 데이터(브이월드, CC BY-NC-ND)의 배포 조건상 공개하지 않습니다.
