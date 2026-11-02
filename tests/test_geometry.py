# -*- coding: utf-8 -*-
"""bjd_geometry_to_csv.py 순수 함수 단위 테스트.

geopandas는 process_shapefiles() 내부에서 lazy import 되므로,
이 모듈은 geopandas 없이도 import/테스트할 수 있다.
"""
import bjd_geometry_to_csv as geo


class TestFindColumn:
    def test_returns_first_matching_candidate(self):
        cols = ["EMD_CD", "EMD_NM", "SGG_OID"]
        # RI_CD는 없고 EMD_CD가 있으므로 EMD_CD 반환
        assert geo.find_column(cols, ["RI_CD", "EMD_CD"]) == "EMD_CD"

    def test_candidate_order_takes_priority(self):
        cols = ["RI_CD", "EMD_CD"]
        # 두 후보가 모두 있으면 후보 리스트의 순서가 우선
        assert geo.find_column(cols, ["RI_CD", "EMD_CD"]) == "RI_CD"

    def test_returns_none_when_no_match(self):
        assert geo.find_column(["FOO", "BAR"], ["RI_CD", "EMD_CD"]) is None

    def test_empty_columns(self):
        assert geo.find_column([], ["RI_CD"]) is None


class TestPadCode:
    def test_pads_8_digit_to_10(self):
        # 8자리(읍면동) 코드는 뒤에 '00'을 붙여 10자리로 표준화
        assert geo.pad_code("41590253") == "4159025300"

    def test_leaves_10_digit_unchanged(self):
        assert geo.pad_code("4159025321") == "4159025321"

    def test_leaves_invalid_length_unchanged(self):
        # 패딩 대상(정확히 8자리)이 아니면 그대로 둔다
        assert geo.pad_code("12345") == "12345"
        assert geo.pad_code("123456789") == "123456789"

    def test_non_numeric_unchanged(self):
        assert geo.pad_code("abcd1234") == "abcd1234"


class TestValidateCodeAndTip:
    def test_valid_10_digit_with_hangul(self):
        assert geo.validate_code_and_tip("4159025321", "상리") is None

    def test_valid_8_digit_with_hangul(self):
        assert geo.validate_code_and_tip("41590253", "종로동") is None

    def test_invalid_code_length(self):
        reason = geo.validate_code_and_tip("12345", "상리")
        assert reason is not None
        assert "8자리 또는 10자리" in reason

    def test_non_numeric_code(self):
        reason = geo.validate_code_and_tip("ABCD123456", "상리")
        assert reason is not None
        assert "8자리 또는 10자리" in reason

    def test_tip_without_hangul(self):
        reason = geo.validate_code_and_tip("4159025321", "12345")
        assert reason is not None
        assert "한글" in reason

    def test_code_checked_before_tip(self):
        # 코드와 tip 둘 다 문제면, 코드 오류가 먼저 보고된다
        reason = geo.validate_code_and_tip("123", "456")
        assert "8자리 또는 10자리" in reason

    def test_hangul_jamo_counts(self):
        # 자음/모음 단독(ㄱ, ㅏ 등)도 한글로 인정
        assert geo.validate_code_and_tip("41590253", "ㄱ") is None


class TestDropStrayParts:
    # 미터 좌표계 기준 사각형 헬퍼
    @staticmethod
    def _box(x, y, size):
        from shapely.geometry import box
        return box(x, y, x + size, y + size)

    def test_drops_small_far_part(self):
        from shapely.geometry import MultiPolygon
        # 본체 2km 사각형 + 100km 북쪽의 200m 조각 (원천 데이터의 위도 밀림 패턴)
        geom = MultiPolygon([self._box(0, 0, 2000), self._box(0, 100_000, 200)])
        cleaned, dropped = geo.drop_stray_parts(geom)
        assert dropped == 1
        assert cleaned.geom_type == "Polygon"
        assert cleaned.area == 2000 * 2000

    def test_keeps_nearby_islands(self):
        from shapely.geometry import MultiPolygon
        # 30km 떨어진 작은 섬은 실제 도서 지역으로 보고 유지
        geom = MultiPolygon([self._box(0, 0, 2000), self._box(30_000, 0, 200)])
        cleaned, dropped = geo.drop_stray_parts(geom)
        assert dropped == 0
        assert cleaned is geom

    def test_keeps_large_far_part(self):
        from shapely.geometry import MultiPolygon
        # 멀리 있어도 면적 비중이 크면(>=5%) 유지
        geom = MultiPolygon([self._box(0, 0, 2000), self._box(0, 100_000, 1000)])
        _, dropped = geo.drop_stray_parts(geom)
        assert dropped == 0

    def test_keeps_remaining_parts_as_multipolygon(self):
        from shapely.geometry import MultiPolygon
        geom = MultiPolygon([self._box(0, 0, 2000), self._box(5000, 0, 500),
                             self._box(0, 100_000, 100)])
        cleaned, dropped = geo.drop_stray_parts(geom)
        assert dropped == 1
        assert cleaned.geom_type == "MultiPolygon"
        assert len(cleaned.geoms) == 2

    def test_single_polygon_unchanged(self):
        poly = self._box(0, 0, 1000)
        assert geo.drop_stray_parts(poly) == (poly, 0)


class TestCenterPoint:
    def test_convex_polygon_uses_centroid(self):
        from shapely.geometry import box
        poly = box(0, 0, 10, 10)
        assert geo.center_point(poly).equals(poly.centroid)

    def test_crescent_uses_point_inside(self):
        from shapely.geometry import box
        # ㄷ자 형상: 무게중심이 오목한 빈 공간(도형 밖)에 찍힌다
        crescent = box(0, 0, 10, 10).difference(box(3, 2, 10, 8))
        assert not crescent.contains(crescent.centroid)
        assert crescent.contains(geo.center_point(crescent))

    def test_multipolygon_keeps_centroid(self):
        from shapely.geometry import MultiPolygon, box
        islands = MultiPolygon([box(0, 0, 1, 1), box(10, 0, 11, 1)])
        assert geo.center_point(islands).equals(islands.centroid)
