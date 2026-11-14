# -*- coding: utf-8 -*-
"""optimize/ 순수 함수 단위 테스트 (ground truth 샘플링, 채점, 반경 갱신)."""
import numpy as np
import pandas as pd
import pytest

from optimize import evaluate as ev
from optimize import generate_ground_truth as gt
from optimize import optimize_radius as opt


class TestSamplePoints:
    def test_points_are_inside_and_counted(self):
        import shapely
        from shapely.geometry import box
        # ㄷ자 형상: bbox의 상당 부분이 도형 밖
        geom = box(0, 0, 10, 10).difference(box(3, 2, 10, 8))
        xy = gt.sample_points(geom, 200, np.random.default_rng(0))
        assert xy.shape == (200, 2)
        assert shapely.contains_xy(geom, xy[:, 0], xy[:, 1]).all()

    def test_same_seed_same_points(self):
        from shapely.geometry import box
        a = gt.sample_points(box(0, 0, 1, 1), 10, np.random.default_rng(7))
        b = gt.sample_points(box(0, 0, 1, 1), 10, np.random.default_rng(7))
        assert np.array_equal(a, b)

    def test_empty_geometry(self):
        from shapely.geometry import Polygon
        assert gt.sample_points(Polygon(), 5, np.random.default_rng(0)).shape == (0, 2)


class TestJudge:
    def test_parent_counts_for_top1(self):
        assert ev.judge("4885025021", ["4885025000", "4885025021"]) == (True, True)

    def test_exact_top1(self):
        assert ev.judge("1111010100", ["1111010100"]) == (True, True)

    def test_miss(self):
        assert ev.judge("4885025021", ["4885036000", "4885036021", "4885036022"]) == (False, False)

    def test_top3_needs_exact_code(self):
        # 상위 읍면동만 3위 안에 있으면 Top-3 실패
        assert ev.judge("4885025021", ["4885036000", "4885025000"]) == (False, False)

    def test_empty_result(self):
        assert ev.judge("1111010100", []) == (False, False)


class TestLoadGroundTruth:
    def test_pads_legacy_eight_digit_ids(self, tmp_path):
        path = tmp_path / "gt.csv"
        pd.DataFrame({"dnid": ["48850250", "4885025021"], "lat": [35.0, 35.1],
                      "lon": [127.7, 127.8]}).to_csv(path, index=False)
        df = ev.load_ground_truth(path, 1.0, 0)
        assert df["dnid"].tolist() == ["4885025000", "4885025021"]


class TestApplyVotes:
    def test_step_and_clamps(self):
        radii = {"a": 1.0, "b": 0.06, "c": 2.0}
        out = opt.apply_votes(radii, {"a": 100, "b": -1000, "c": 10_000_000, "zzz": 5}, lr=1.0)
        assert out["a"] == pytest.approx(1.1)            # 100표 x 1.0 x 0.001
        assert out["b"] == opt.MIN_RADIUS                 # 최소 반경 아래로 안 내려감
        assert out["c"] == pytest.approx(2.0 + opt.MAX_STEP)  # 1회 변화량 상한
        assert "zzz" not in out
        assert radii["a"] == 1.0                          # 원본 불변
