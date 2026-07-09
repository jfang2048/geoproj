"""Test the SCS-CN runoff formula."""
import numpy as np
import pytest
from postfire_runoff.hydrology.scs_cn import scs_runoff_mm, burned_cn


class TestSCSRunoff:
    def test_zero_rainfall(self):
        q = scs_runoff_mm(0.0, 70)
        assert float(q) == 0.0

    def test_below_abstraction(self):
        q = scs_runoff_mm(5.0, 60, 0.20)
        assert float(q) == 0.0

    def test_positive_runoff(self):
        q = scs_runoff_mm(100.0, 70, 0.20)
        assert float(q) > 0.0

    def test_cn_clamped_low(self):
        q = scs_runoff_mm(100.0, -99)
        assert np.isfinite(float(q))

    def test_cn_clamped_high(self):
        q = scs_runoff_mm(100.0, 200)
        assert float(q) > 0.0

    def test_vectorized(self):
        p = np.array([10.0, 50.0, 100.0, 200.0])
        cn = np.array([60, 70, 80, 90])
        q = scs_runoff_mm(p, cn)
        assert q.shape == (4,)
        assert np.all(np.isfinite(q))

    def test_lambda_effect(self):
        q_std = scs_runoff_mm(100.0, 70, 0.20)
        q_low = scs_runoff_mm(100.0, 70, 0.05)
        assert float(q_low) >= float(q_std)

    def test_negative_rainfall_raises(self):
        with pytest.raises(ValueError):
            scs_runoff_mm(-10.0, 70)

    def test_zero_lambda_raises(self):
        with pytest.raises(ValueError):
            scs_runoff_mm(100.0, 70, 0.0)


class TestBurnedCN:
    def test_unburned(self):
        assert burned_cn(60, 0) == 60.0

    def test_low_severity(self):
        assert burned_cn(60, 1) == 64.0

    def test_clamped_at_98(self):
        assert burned_cn(95, 3) == 98.0

    def test_unknown_burn_class_raises(self):
        with pytest.raises(ValueError):
            burned_cn(60, 99)
