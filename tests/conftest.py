from __future__ import annotations

import pytest

from jevcheck.contract import load_contract
from tests.helpers import FIXTURES


@pytest.fixture
def contract():
    return load_contract(FIXTURES / "support-triage.json")
