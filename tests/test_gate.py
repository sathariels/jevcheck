from __future__ import annotations

import pytest

from jevcheck.answers import ChoiceAnswer, NoulAnswer
from jevcheck.gate import Action, Gate


def test_gate_thresholds() -> None:
    gate = Gate(auto_threshold=0.85, human_threshold=0.5)
    assert gate.decide(0.9).action is Action.AUTO
    assert gate.decide(0.6).action is Action.ASK_HUMAN
    assert gate.decide(0.2).action is Action.REJECT


def test_gate_uses_documented_noul_mapping() -> None:
    gate = Gate(auto_threshold=0.85, human_threshold=0.5)
    yes = gate.decide_answer(NoulAnswer(noul=0.96))
    no = gate.decide_answer(NoulAnswer(noul=0.2))
    choice = gate.decide_answer(
        ChoiceAnswer(choice="billing", confidence=0.7, probabilities={"billing": 0.7})
    )
    assert yes.action is Action.AUTO
    assert no.action is Action.REJECT
    assert choice.action is Action.ASK_HUMAN


def test_gate_rejects_inverted_thresholds() -> None:
    gate = Gate(auto_threshold=0.4, human_threshold=0.8)
    with pytest.raises(ValueError, match="human_threshold"):
        gate.decide(0.5)
