# -*- coding: utf-8 -*-
"""bjd_csv_to_dongnae.py 단위 테스트 (dongnae 스키마 변환 + 폐지/결측 제외)."""
import pandas as pd
import pytest

import bjd_csv_to_dongnae as dn

COLUMNS = ["LAWD_CD", "full_address", "DEL_DT", "center_latitude", "center_longitude", "radius_km"]


def _build(rows):
    return pd.DataFrame(rows, columns=COLUMNS)


class TestToDongnae:
    def test_maps_columns(self):
        out, _ = dn.to_dongnae(_build([["4790043030", "경상북도 예천군 은풍면 시항리", None,
                                         "36.74154188", "128.4656243", "1.576"]]))
        assert list(out.columns) == ["dnid", "dnname", "dnlatitude", "dnlongitude", "dnradius"]
        assert out.iloc[0].tolist() == ["4790043030", "경상북도 예천군 은풍면 시항리",
                                        "36.74154188", "128.4656243", "1.576"]

    def test_drops_deleted_even_with_coords(self):
        out, stats = dn.to_dongnae(_build([
            ["4513039022", "전라북도 군산시 옥도면 연도리", "20240117", "35.9", "126.4", "1.0"],
            ["5213039022", "전북특별자치도 군산시 옥도면 연도리", None, "35.9", "126.4", "1.0"],
        ]))
        assert out["dnid"].tolist() == ["5213039022"]
        assert stats["deleted_with_coords"] == 1

    def test_blank_del_dt_is_not_deleted(self):
        out, _ = dn.to_dongnae(_build([["1111010100", "서울특별시 종로구 청운동", "  ", "37.5", "126.9", "0.5"]]))
        assert len(out) == 1

    def test_drops_rows_without_coords(self):
        out, stats = dn.to_dongnae(_build([["1100000000", "서울특별시", None, None, None, None]]))
        assert out.empty
        assert stats["no_coords"] == 1

    def test_duplicate_dnid_raises(self):
        row = ["1111010100", "서울특별시 종로구 청운동", None, "37.5", "126.9", "0.5"]
        with pytest.raises(ValueError, match="중복"):
            dn.to_dongnae(_build([row, row]))

    def test_missing_column_raises(self):
        with pytest.raises(ValueError, match="DEL_DT"):
            dn.to_dongnae(_build([]).drop(columns=["DEL_DT"]))


class TestFillMissingCoords:
    def test_fills_only_missing_rows(self):
        df = _build([
            ["5011033022", "제주특별자치도 제주시 우도면 서광리", None, None, None, None],
            ["1111010100", "서울특별시 종로구 청운동", None, "37.5", "126.9", "0.5"],
        ])
        fallback = _build([
            ["5011033022", "제주특별자치도 제주시 우도면 서광리", None, "33.5", "126.9", "2.0"],
            ["1111010100", "서울특별시 종로구 청운동", None, "0", "0", "9"],
        ])
        out, filled = dn.fill_missing_coords(df, fallback)
        assert filled == 1
        assert out.loc[0, ["center_latitude", "center_longitude", "radius_km"]].tolist() == ["33.5", "126.9", "2.0"]
        # 새 결과에 이미 좌표가 있는 행은 덮어쓰지 않는다
        assert out.loc[1, "center_latitude"] == "37.5"

    def test_fallback_without_coords_is_ignored(self):
        df = _build([["4100000000", "경기도", None, None, None, None]])
        out, filled = dn.fill_missing_coords(df, df)
        assert filled == 0
        assert out["center_latitude"].isna().all()
