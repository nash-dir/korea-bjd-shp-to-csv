# -*- coding: utf-8 -*-
"""bjd_csv_to_fulladdress.py 단위 테스트 (full_address 생성 + 파일명 충돌 처리)."""
import pandas as pd

import bjd_csv_to_fulladdress as fa

COMPONENTS = ["SIDO_NM", "SGG_NM", "UMD_NM", "RI_NM"]


def _build(rows):
    return pd.DataFrame(rows, columns=COMPONENTS)


class TestCreateFullAddress:
    def test_joins_all_components(self):
        df = _build([["경상북도", "예천군", "은풍면", "시항리"]])
        out = fa.create_full_address(df, COMPONENTS)
        assert out.loc[0, "full_address"] == "경상북도 예천군 은풍면 시항리"

    def test_skips_nan_components_without_double_space(self):
        # UMD_NM, RI_NM이 NaN → 중간에 공백이 2칸 이상 생기면 안 됨
        df = _build([["서울특별시", "종로구", None, None]])
        out = fa.create_full_address(df, COMPONENTS)
        assert out.loc[0, "full_address"] == "서울특별시 종로구"

    def test_strips_leading_and_trailing_space(self):
        # 앞쪽(SIDO_NM)이 비어 선두 공백이 생기는 경우
        df = _build([[None, "종로구", "청운동", None]])
        out = fa.create_full_address(df, COMPONENTS)
        assert out.loc[0, "full_address"] == "종로구 청운동"

    def test_collapses_internal_blank_components(self):
        # 중간 구성요소만 비어 "A  B" 형태가 되는 경우 → 단일 공백
        df = _build([["서울특별시", None, "청운동", None]])
        out = fa.create_full_address(df, COMPONENTS)
        assert out.loc[0, "full_address"] == "서울특별시 청운동"
        assert "  " not in out.loc[0, "full_address"]

    def test_inserted_right_after_last_component(self):
        df = _build([["경상북도", "예천군", "은풍면", "시항리"]])
        out = fa.create_full_address(df, COMPONENTS)
        cols = list(out.columns)
        # full_address는 마지막 구성요소(RI_NM) 바로 뒤에 위치
        assert cols.index("full_address") == cols.index("RI_NM") + 1

    def test_missing_all_components_returns_unchanged(self):
        df = pd.DataFrame({"OTHER": ["x"]})
        out = fa.create_full_address(df, COMPONENTS)
        assert "full_address" not in out.columns


class TestGetUniqueFilename:
    def test_returns_plain_name_when_absent(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        assert fa.get_unique_filename("out", ".csv") == "out.csv"

    def test_appends_suffix_on_collision(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / "out.csv").write_text("x", encoding="utf-8")
        assert fa.get_unique_filename("out", ".csv") == "out-1.csv"

    def test_increments_until_free(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / "out.csv").write_text("x", encoding="utf-8")
        (tmp_path / "out-1.csv").write_text("x", encoding="utf-8")
        assert fa.get_unique_filename("out", ".csv") == "out-2.csv"
