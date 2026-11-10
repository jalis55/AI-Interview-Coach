"""Parallel evidence summaries with deterministic arithmetic and branch fallbacks."""

import json
from statistics import fmean

from langchain_core.runnables import RunnableLambda, RunnableParallel

from ai_interview_coach.chains.report import build_report_branch
from ai_interview_coach.models.report import (
    InterviewReport,
    ObservedScore,
    Recommendations,
    ReportText,
    SkillEvidence,
)
from ai_interview_coach.services.validated_call import call_validated
from ai_interview_coach.utils.activity import emit

LEVEL = {"easy": 0, "medium": 1, "hard": 2}


def build_evidence(session):
    records = session.progress.records
    skills = [*session.requirements.core_skills, "behavioral"]
    evidence = []
    for skill in skills:
        related = [r for r in records if r.question.skill == skill]
        valid = [r for r in related if r.evaluation_status == "valid"]
        target = session.progress.target_difficulty[skill]
        at_target = [r for r in valid if LEVEL[r.question.difficulty.value] >= LEVEL[target.value]]
        gap = (
            "No reliable answers observed at the JD target difficulty."
            if not at_target
            else "Observed target-level answers need improvement."
            if fmean(r.assessment.score for r in at_target) < 7
            else "Some target-level evidence observed; coverage remains limited."
        )
        evidence.append(
            SkillEvidence(
                skill=skill,
                target_difficulty=target,
                observations=[
                    ObservedScore(
                        difficulty=r.question.difficulty,
                        score=r.assessment.score,
                        status=r.evaluation_status,
                    )
                    for r in related
                ],
                valid_count=len(valid),
                reliable_mean=fmean(r.assessment.score for r in valid) if valid else None,
                assessment="insufficiently_assessed" if len(valid) < 2 else "observed_practice",
                target_gap=gap,
            )
        )
    return evidence


class ReportService:
    def __init__(self, settings, branches):
        self.settings = settings
        self.branches = branches

    def create(self, session):
        progress = session.progress
        if not progress.round_slots or progress.current_index != len(progress.round_slots):
            raise ValueError("Report requires a completed round.")
        if not progress.records:
            raise ValueError("Report requires stored evaluations.")
        evidence = build_evidence(session)
        valid = [r for r in progress.records if r.evaluation_status == "valid"]
        strengths = [s for r in valid for s in r.assessment.strengths][:8]
        improvements = [s for r in valid for s in r.assessment.improvements][:8]
        default_strengths = ReportText(
            text="; ".join(strengths) or "No reliable strengths assessed."
        )
        default_gaps = ReportText(
            text="; ".join(improvements)
            or "Skills remain insufficiently assessed; collect reliable answers."
        )
        default_recs = Recommendations(
            items=[
                f"Practice {e.skill} at {e.target_difficulty.value}: {e.target_gap}"
                for e in sorted(
                    evidence, key=lambda e: (e.reliable_mean is not None, e.reliable_mean or 0)
                )[:5]
            ]
        )
        defaults = {
            "strengths_summary": default_strengths,
            "gaps_summary": default_gaps,
            "recommendations": default_recs,
        }
        payload = {
            "evidence": json.dumps(
                {
                    "coverage": [e.model_dump(mode="json") for e in evidence],
                    "strengths": strengths,
                    "improvements": improvements,
                }
            )
        }

        def branch(name):
            def run(_):
                if session.is_demo or not valid or name not in self.branches:
                    return defaults[name]
                primary, fallback = self.branches[name]
                schema = Recommendations if name == "recommendations" else ReportText
                try:
                    result = call_validated(
                        session,
                        primary,
                        fallback,
                        payload,
                        schema,
                        self.settings,
                        stage=f"report_{name}",
                    )
                except Exception:
                    # Isolate text branches so numeric evidence survives any branch failure.
                    emit(session, "safe_default", stage=f"report_{name}", status="error")
                    return defaults[name]
                if result.value is None:
                    emit(session, "safe_default", stage=f"report_{name}")
                return result.value or defaults[name]

            return RunnableLambda(run)

        parallel = RunnableParallel(
            strengths_summary=branch("strengths_summary"),
            gaps_summary=branch("gaps_summary"),
            recommendations=branch("recommendations"),
            overall_score=RunnableLambda(
                lambda _: fmean(r.assessment.score for r in progress.records)
            ),
        )
        values = parallel.invoke({})
        defaulted = sum(r.evaluation_status == "defaulted" for r in progress.records)
        return InterviewReport(
            strengths_summary=values["strengths_summary"].text,
            gaps_summary=values["gaps_summary"].text,
            recommendations=values["recommendations"].items,
            overall_score=values["overall_score"],
            defaulted_count=defaulted,
            evaluated_count=len(progress.records),
            readiness_status="limited_evidence" if valid else "unavailable",
            coverage=evidence,
            omitted_skills=list(session.plan.omitted_skills),
            caveat=(
                f"The average includes all {len(progress.records)} stored scores, including "
                f"{defaulted} neutral fallback score(s). Difficulty levels are not calibrated "
                "hiring predictions. Skills with fewer than two reliable answers are "
                "insufficiently assessed."
            ),
        )


def create_report_service(settings):
    tasks = {
        "strengths_summary": "Summarize observed strengths.",
        "gaps_summary": "Summarize gaps and target-level limitations.",
        "recommendations": "Recommend specific next practice actions tied to observed gaps.",
    }
    branches = {
        name: (
            build_report_branch(task, recommendations=name == "recommendations"),
            build_report_branch(task, recommendations=name == "recommendations", fallback=True),
        )
        for name, task in tasks.items()
    }
    return ReportService(settings, branches)
