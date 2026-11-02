# -*- coding: utf-8 -*-
"""bjd_csv_apply_revisions.py 단위 테스트 (Exception 라벨 + 보정 명세 적용)."""
import pandas as pd
import pytest

import bjd_csv_apply_revisions as rv

COLUMNS = ["LAWD_CD", "UMD_NM", "DEL_DT", "center_latitude", "center_longitude", "radius_km", "filename"]
SPEC_COLUMNS = ["LAWD_CD", "full_address", "Exception", "method", "source",
                "center_latitude", "center_longitude", "radius_km", "note"]


def _df(rows):
    return pd.DataFrame(rows, columns=COLUMNS)


def _spec(rows):
    return pd.DataFrame(rows, columns=SPEC_COLUMNS)


def _row(out, code):
    return out.set_index("LAWD_CD").loc[code]


BASE = [
    ["4100000000", None, None, None, None, None, None],                     # 시도: Aggregated
    ["4513039022", "옥도면", "20240117", "35.9", "126.4", "1.0", "RI_45.shp"],  # 폐지: Historical
    ["4682025032", "해남읍", None, "34.5", "126.5", "3.636", "RI_46.shp"],     # donor
    ["4682025038", "해남읍", None, None, None, None, None],                   # copy 대상
    ["5011031021", "한경면", None, "33.3", "126.2", "2.0", "RI_50.shp"],
    ["5011031022", "한경면", None, "33.3", "126.2", "3.0", "RI_50.shp"],
    ["5011031031", "한경면", None, None, None, None, None],                   # proxy 대상
]


class TestBaseLabels:
    def test_labels(self):
        out, _ = rv.apply_revisions(_df(BASE), _spec([]))
        assert _row(out, "4100000000")["Exception"] == "2"
        assert _row(out, "4513039022")["Exception"] == "1"   # 좌표가 있어도 폐지면 1
        assert _row(out, "4682025032")["Exception"] == "0"


class TestApplyRevisions:
    def test_copy_uses_current_donor_values(self):
        spec = _spec([["4682025038", "", "4", "copy", "4682025032", "", "", "", ""]])
        out, _ = rv.apply_revisions(_df(BASE), spec)
        row = _row(out, "4682025038")
        assert row[["center_latitude", "center_longitude", "radius_km"]].tolist() == ["34.5", "126.5", "3.636"]
        assert row["Exception"] == "4"
        assert row["filename"] == "manual_revisions.csv"

    def test_proxy_mean_radius(self):
        spec = _spec([["5011031031", "", "5", "proxy", "5011031021 5011031022", "33.29", "126.23", "", ""]])
        out, _ = rv.apply_revisions(_df(BASE), spec)
        row = _row(out, "5011031031")
        assert row[["center_latitude", "center_longitude", "radius_km"]].tolist() == ["33.29", "126.23", "2.500"]

    def test_proxy_literal_radius(self):
        spec = _spec([["5011031031", "", "5", "proxy", "", "33.29", "126.23", "5.2", ""]])
        out, _ = rv.apply_revisions(_df(BASE), spec)
        assert _row(out, "5011031031")["radius_km"] == "5.2"

    def test_none_clears_coords(self):
        spec = _spec([["4682025032", "", "3", "none", "", "", "", "", ""]])
        out, overridden = rv.apply_revisions(_df(BASE), spec)
        row = _row(out, "4682025032")
        assert row[["center_latitude", "radius_km"]].isna().all()
        assert row["Exception"] == "3"
        assert overridden == []

    def test_reports_overridden_computed_coords(self):
        spec = _spec([["4682025032", "", "5", "manual", "", "1", "2", "3", ""]])
        _, overridden = rv.apply_revisions(_df(BASE), spec)
        assert overridden == ["4682025032"]

    def test_source_without_coords_raises(self):
        spec = _spec([["4682025038", "", "4", "copy", "4100000000", "", "", "", ""]])
        with pytest.raises(ValueError, match="좌표가 없습니다"):
            rv.apply_revisions(_df(BASE), spec)

    def test_chained_source_raises(self):
        spec = _spec([
            ["4682025038", "", "4", "copy", "5011031031", "", "", "", ""],
            ["5011031031", "", "5", "manual", "", "1", "2", "3", ""],
        ])
        with pytest.raises(ValueError, match="다시 보정 대상"):
            rv.apply_revisions(_df(BASE), spec)

    def test_unknown_method_raises(self):
        spec = _spec([["4682025038", "", "4", "guess", "", "", "", "", ""]])
        with pytest.raises(ValueError, match="method"):
            rv.apply_revisions(_df(BASE), spec)


class TestShippedSpec:
    def test_spec_is_well_formed(self):
        spec = pd.read_csv(rv.REVISIONS_CSV, dtype=str, encoding="utf-8-sig")
        assert spec["LAWD_CD"].is_unique
        assert set(spec["method"]) <= set(rv.METHODS)
        assert spec["Exception"].value_counts().to_dict() == {"3": 29, "5": 7, "4": 6, "0": 1}
