"""Optional thin helper. Not the product — contracts and eval are."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field

from jevcheck.answers import mapped_confidence


class Action(str, Enum):
    AUTO = "auto"
    ASK_HUMAN = "ask_human"
    REJECT = "reject"


class Decision(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    action: Action
    confidence: float
    reason: str


class Gate(BaseModel):
    """Map a verified confidence scalar onto auto / ask_human / reject."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    auto_threshold: float = Field(default=0.85, ge=0.0, le=1.0)
    human_threshold: float = Field(default=0.5, ge=0.0, le=1.0)

    def decide(self, confidence: float) -> Decision:
        if not 0.0 <= confidence <= 1.0:
            raise ValueError("confidence must be in [0, 1]")
        if self.human_threshold > self.auto_threshold:
            raise ValueError("human_threshold must be <= auto_threshold")
        if confidence >= self.auto_threshold:
            return Decision(
                action=Action.AUTO,
                confidence=confidence,
                reason=f"{confidence:.2f} >= auto_threshold {self.auto_threshold:.2f}",
            )
        if confidence >= self.human_threshold:
            return Decision(
                action=Action.ASK_HUMAN,
                confidence=confidence,
                reason=(
                    f"{self.human_threshold:.2f} <= {confidence:.2f} "
                    f"< {self.auto_threshold:.2f}"
                ),
            )
        return Decision(
            action=Action.REJECT,
            confidence=confidence,
            reason=f"{confidence:.2f} < human_threshold {self.human_threshold:.2f}",
        )

    def decide_answer(self, answer: object) -> Decision:
        return self.decide(mapped_confidence(answer))  # type: ignore[arg-type]
