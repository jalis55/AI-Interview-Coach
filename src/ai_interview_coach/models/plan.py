from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Difficulty(StrEnum):
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"


class QuestionType(StrEnum):
    TECHNICAL = "technical"
    BEHAVIORAL = "behavioral"


class QuestionSlot(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    skill: str = Field(min_length=1)
    question_type: QuestionType
    target_difficulty: Difficulty


class QuestionPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    num_questions: int = Field(strict=True, ge=3, le=10)
    slots: list[QuestionSlot]
    prioritized_skills: list[str] = Field(min_length=1)
    omitted_skills: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_plan(self) -> "QuestionPlan":
        if len(self.slots) != self.num_questions:
            raise ValueError("Slot count must match num_questions.")

        behavioral_slots = [
            slot for slot in self.slots if slot.question_type == QuestionType.BEHAVIORAL
        ]

        if len(behavioral_slots) != 1:
            raise ValueError("A plan must contain exactly one behavioral slot.")

        if len(set(self.prioritized_skills)) != len(self.prioritized_skills):
            raise ValueError("Prioritized skills must not contain duplicates.")

        if len(set(self.omitted_skills)) != len(self.omitted_skills):
            raise ValueError("Omitted skills must not contain duplicates.")

        if set(self.prioritized_skills) & set(self.omitted_skills):
            raise ValueError("A skill cannot be both prioritized and omitted.")

        technical_skills = {
            slot.skill for slot in self.slots if slot.question_type == QuestionType.TECHNICAL
        }

        if technical_skills != set(self.prioritized_skills):
            raise ValueError("Technical slots must cover exactly the prioritized skills.")

        return self
