from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from jevcheck.contract import Contract, FieldExpect, load_contract
from tests.helpers import FIXTURES


def test_load_json_contract(contract: Contract) -> None:
    assert contract.version == "0.1"
    assert contract.name == "support-triage"
    assert contract.baseline_model == "jev-1.13"
    assert [case.id for case in contract.cases] == [
        "ticket-001",
        "ticket-002",
        "ticket-003",
    ]
    intent = contract.cases[0].questions["intent"]
    assert intent.type == "choice"
    assert "billing" in intent.criteria


def test_load_jsonl_contract() -> None:
    loaded = load_contract(FIXTURES / "support-triage.jsonl")
    assert loaded.name == "support-triage-jsonl"
    assert loaded.baseline_model == "jev-1.13"
    assert loaded.cases[0].expect["intent"].choice == "general"


def test_jsonl_requires_baseline(tmp_path) -> None:
    path = tmp_path / "bare.jsonl"
    path.write_text(
        json.dumps(
            {
                "id": "only",
                "state": "hi",
                "questions": {
                    "intent": {"type": "choice", "criteria": {"a": None, "b": None}}
                },
                "expect": {"intent": {"choice": "a"}},
            }
        )
        + "\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="baseline_model"):
        load_contract(path)
    loaded = load_contract(path, baseline_model="jev-1.13")
    assert loaded.baseline_model == "jev-1.13"


def test_rejects_unknown_expect_keys() -> None:
    with pytest.raises(ValidationError):
        FieldExpect.model_validate({"choice": "billing", "invented_confidence": 0.9})


def test_rejects_unknown_question_fields() -> None:
    with pytest.raises(ValidationError):
        Contract.model_validate(
            {
                "baseline_model": "jev-1.13",
                "cases": [
                    {
                        "id": "x",
                        "state": "s",
                        "questions": {
                            "n": {
                                "type": "noul",
                                "instructions": "yes?",
                                "confidence": 0.9,
                            }
                        },
                        "expect": {"n": {"noul_true": True}},
                    }
                ],
            }
        )


def test_expect_must_match_questions() -> None:
    with pytest.raises(ValidationError, match="unknown questions"):
        Contract.model_validate(
            {
                "baseline_model": "jev-1.13",
                "cases": [
                    {
                        "id": "x",
                        "state": "s",
                        "questions": {
                            "intent": {"type": "choice", "criteria": {"a": None}}
                        },
                        "expect": {"tone": {"choice": "a"}},
                    }
                ],
            }
        )


def test_empty_expect_rejected() -> None:
    with pytest.raises(ValidationError, match="at least one constraint"):
        Contract.model_validate(
            {
                "baseline_model": "jev-1.13",
                "cases": [
                    {
                        "id": "x",
                        "state": "s",
                        "questions": {
                            "q": {"type": "choice", "criteria": {"a": None, "b": None}}
                        },
                        "expect": {"q": {}},
                    }
                ],
            }
        )


def test_wrong_kind_expect_rejected() -> None:
    with pytest.raises(ValidationError, match="do not apply"):
        Contract.model_validate(
            {
                "baseline_model": "jev-1.13",
                "cases": [
                    {
                        "id": "x",
                        "state": "s",
                        "questions": {
                            "q": {"type": "choice", "criteria": {"a": None, "b": None}}
                        },
                        "expect": {"q": {"score": 2}},
                    }
                ],
            }
        )


def test_empty_baseline_rejected() -> None:
    with pytest.raises(ValidationError, match="nonempty"):
        Contract.model_validate(
            {
                "baseline_model": "",
                "cases": [
                    {
                        "id": "x",
                        "state": "s",
                        "questions": {"n": {"type": "noul"}},
                        "expect": {"n": {"noul_true": True}},
                    }
                ],
            }
        )


@pytest.mark.parametrize("name", ["jev-latest", "jev-preview"])
def test_floating_baseline_rejected(name: str) -> None:
    with pytest.raises(ValidationError, match="unpinned"):
        Contract.model_validate(
            {
                "baseline_model": name,
                "cases": [
                    {
                        "id": "x",
                        "state": "s",
                        "questions": {"n": {"type": "noul"}},
                        "expect": {"n": {"noul_true": True}},
                    }
                ],
            }
        )


def test_floating_baseline_allowed_when_opted_in() -> None:
    loaded = Contract.model_validate(
        {
            "baseline_model": "jev-latest",
            "allow_unpinned": True,
            "cases": [
                {
                    "id": "x",
                    "state": "s",
                    "questions": {"n": {"type": "noul"}},
                    "expect": {"n": {"noul_true": True}},
                }
            ],
        }
    )
    assert loaded.baseline_model == "jev-latest"


def test_empty_score_criteria_rejected() -> None:
    with pytest.raises(ValidationError, match="nonempty"):
        Contract.model_validate(
            {
                "baseline_model": "jev-1.13",
                "cases": [
                    {
                        "id": "x",
                        "state": "s",
                        "questions": {"u": {"type": "score", "criteria": []}},
                        "expect": {"u": {"score": 1.0}},
                    }
                ],
            }
        )
