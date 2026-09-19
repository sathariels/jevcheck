from __future__ import annotations

import os

import pytest

from jevcheck import JevClient

pytestmark = pytest.mark.skipif(
    not os.environ.get("TYPESAFE_API_KEY"),
    reason="TYPESAFE_API_KEY not set; live System One call skipped",
)


def test_live_system_one_noul_choice_score() -> None:
    client = JevClient(model="jev-1.13")
    response = client.system_one(
        state="I was charged twice. Please fix this ASAP.",
        questions={
            "billing": {"type": "noul", "instructions": "Is this ticket about billing?"},
            "tone": {
                "type": "choice",
                "instructions": "What is the customer's tone?",
                "criteria": {"calm": None, "frustrated": None, "angry": None},
            },
            "urgency": {
                "type": "score",
                "instructions": "How urgent is this ticket?",
                "criteria": ["can wait", "this week", "today"],
            },
        },
    )
    assert 0.0 <= response.answers["billing"].noul <= 1.0
    assert response.answers["tone"].choice in {"calm", "frustrated", "angry"}
    assert 0.0 <= response.answers["tone"].confidence <= 1.0
    assert response.answers["urgency"].score >= 0.0
