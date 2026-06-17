# -*- coding: utf-8 -*-
"""bjd_csv_API_verification.py verify_address 라벨링 로직 단위 테스트.

verify_address(row, api_addr) 반환값:
    None : API 결과 없음 / '오류' / '미존재'
    1    : 리(RI) 또는 읍면동(UMD) 명칭이 API 주소에 포함
    0    : 정상 응답이나 명칭 불일치
"""
import bjd_csv_API_verification as ver


class TestVerifyAddress:
    def test_ri_match_returns_1(self):
        row = {"RI_NM": "시항리", "UMD_NM": "은풍면"}
        assert ver.verify_address(row, "경상북도 예천군 은풍면 시항리 산 12-1") == 1

    def test_ri_present_but_not_matching_returns_0(self):
        row = {"RI_NM": "시항리", "UMD_NM": "은풍면"}
        # RI_NM이 존재하므로 RI 기준으로만 판정 → 불일치
        assert ver.verify_address(row, "경상북도 예천군 은풍면 다른리") == 0

    def test_falls_back_to_umd_when_ri_blank(self):
        row = {"RI_NM": "", "UMD_NM": "청운동"}
        assert ver.verify_address(row, "서울특별시 종로구 청운동 1-1") == 1

    def test_umd_mismatch_returns_0(self):
        row = {"RI_NM": "", "UMD_NM": "청운동"}
        assert ver.verify_address(row, "서울특별시 종로구 효자동") == 0

    def test_none_api_addr_returns_none(self):
        row = {"RI_NM": "시항리", "UMD_NM": "은풍면"}
        assert ver.verify_address(row, None) is None

    def test_error_keyword_returns_none(self):
        row = {"RI_NM": "시항리", "UMD_NM": "은풍면"}
        assert ver.verify_address(row, "API오류: TIMEOUT") is None

    def test_not_found_keyword_returns_none(self):
        row = {"RI_NM": "시항리", "UMD_NM": "은풍면"}
        assert ver.verify_address(row, "주소 미존재") is None

    def test_literal_nan_strings_treated_as_blank(self):
        # CSV에서 읽힌 'nan' 문자열은 빈 값으로 취급되어야 한다
        row = {"RI_NM": "nan", "UMD_NM": "청운동"}
        assert ver.verify_address(row, "서울특별시 종로구 청운동") == 1

    def test_both_names_blank_returns_0(self):
        row = {"RI_NM": "", "UMD_NM": ""}
        assert ver.verify_address(row, "어딘가의 주소") == 0
