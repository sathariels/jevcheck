from __future__ import annotations

from pathlib import Path

from jevcheck.answers import ChoiceAnswer, JevResponse, NoulAnswer, ScoreAnswer, Usage

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "fixtures"


def choice(label: str, confidence: float, other: str = "general") -> ChoiceAnswer:
    alt = other if label != other else "billing"
    return ChoiceAnswer(
        choice=label,
        confidence=confidence,
        probabilities={label: confidence, alt: round(1.0 - confidence, 4)},
    )


def noul(value: float) -> NoulAnswer:
    return NoulAnswer(noul=value)


def score(value: float, confidence: float) -> ScoreAnswer:
    return ScoreAnswer(
        score=value,
        confidence=confidence,
        legend={"0": "can wait", "1": "this week", "2": "today"},
        probabilities={"0": 0.05, "1": 0.1, "2": 0.85},
    )


def response(model: str, **answers) -> JevResponse:
    return JevResponse(model=model, usage=Usage(), answers=answers)
