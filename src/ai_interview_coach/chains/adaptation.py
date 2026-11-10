"""Per-skill difficulty routing with explicit LCEL branches."""

from langchain_core.runnables import RunnableBranch, RunnableLambda

from ai_interview_coach.models.plan import Difficulty

LEVELS = [Difficulty.EASY, Difficulty.MEDIUM, Difficulty.HARD]


def shift(current, delta):
    return LEVELS[max(0, min(2, LEVELS.index(Difficulty(current)) + delta))]


def build_difficulty_router():
    return RunnableBranch(
        (lambda x: x["status"] == "defaulted", RunnableLambda(lambda x: Difficulty(x["current"]))),
        (lambda x: x["score"] < 4, RunnableLambda(lambda x: shift(x["current"], -1))),
        (lambda x: x["score"] > 8, RunnableLambda(lambda x: shift(x["current"], 1))),
        RunnableLambda(lambda x: Difficulty(x["current"])),
    )
