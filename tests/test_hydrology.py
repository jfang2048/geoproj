from __future__ import annotations

import numpy as np


def test_scs_cn_handles_zero_and_initial_abstraction():
    from app.services.hydrology import scs_runoff_mm

    assert float(scs_runoff_mm(0.0, 75.0)) == 0.0
    assert float(scs_runoff_mm(1.0, 30.0)) == 0.0
    assert float(scs_runoff_mm(80.0, 80.0)) > 0.0


def test_curve_numbers_are_clamped():
    from app.services.hydrology import burned_cn, scs_runoff_mm

    assert burned_cn(97, 3) == 98.0
    result = scs_runoff_mm(np.array([50.0]), np.array([150.0]))
    assert result[0] >= 0.0
