"""Interview, feedback, reports, focused practice, and fresh retries."""

import streamlit as st

from ai_interview_coach.models.session import InterviewStatus
from ai_interview_coach.services.interview import (
    InterviewService,
    UnrelatedAnswerError,
    create_interview_service,
)
from ai_interview_coach.services.research import ResearchPreparationError


def render_feedback(record):
    st.subheader("Latest feedback")
    st.write(
        f"Score: {record.assessment.score}/10 at {record.question.difficulty.value} difficulty"
    )
    if record.evaluation_status == "defaulted":
        st.warning("Evaluation unavailable: this neutral score is not reliable evidence.")
    st.write(record.assessment.feedback)
    if record.assessment.strengths:
        st.write("Strengths")
        for item in record.assessment.strengths:
            st.write(f"- {item}")
    if record.assessment.improvements:
        st.write("Improve next time")
        for item in record.assessment.improvements:
            st.write(f"- {item}")


def render_report(session):
    report = session.final_report
    st.subheader("JD preparation report")
    st.metric("Recorded average", f"{report.overall_score:.2f}/10")
    st.caption(report.caveat)
    if report.readiness_status == "unavailable":
        st.warning("Readiness unavailable: no reliable evaluations were recorded.")
    else:
        st.info("Limited coaching evidence, not a hiring prediction.")
    if report.defaulted_count:
        st.warning(f"{report.defaulted_count} evaluation(s) used a neutral fallback score of 5.")
    st.write("Strengths")
    st.write(report.strengths_summary)
    st.write("Gaps")
    st.write(report.gaps_summary)
    st.write("Recommended practice")
    for recommendation in report.recommendations:
        st.write(f"- {recommendation}")
    st.table(
        [
            {
                "Skill": e.skill,
                "JD target": e.target_difficulty.value,
                "Reliable answers": e.valid_count,
                "Observed scores": "; ".join(
                    f"{o.score}/{o.difficulty.value} ({o.status})" for o in e.observations
                )
                or "Not assessed",
                "Assessment": e.assessment.replace("_", " "),
                "Target gap": e.target_gap,
            }
            for e in report.coverage
        ]
    )
    if report.omitted_skills:
        st.caption("Omitted from initial coverage: " + ", ".join(report.omitted_skills))
    st.download_button(
        "Download report JSON",
        data=report.model_dump_json(indent=2),
        file_name=f"interview-report-{session.session_id}.json",
        mime="application/json",
    )


def render_interview(session, *, settings, sessions, histories, lineages):
    if not session.research_complete:
        return

    def service():
        return create_interview_service(settings, sessions, histories, lineages)

    if session.is_demo:
        st.info(
            "Offline demo: provider calls are disabled and scores are simulated neutral values."
        )
    if not session.progress.round_slots:
        if st.button("Start interview", type="primary"):
            try:
                service().start(session)
            except (ResearchPreparationError, ValueError):
                st.error("An unused question could not be prepared. Your progress is preserved.")
                return
            st.rerun()
        return

    progress = session.progress
    st.subheader("Focused practice" if progress.round_kind == "practice" else "Coverage interview")
    st.progress(
        progress.current_index / len(progress.round_slots),
        text=f"{progress.current_index} of {len(progress.round_slots)} answers completed",
    )
    if progress.records:
        render_feedback(progress.records[-1])
        with st.expander("Earlier answers"):
            for record in progress.records[:-1]:
                st.write(record.question.question)
                st.text(record.answer)
                st.write(f"{record.assessment.score}/10 - {record.assessment.feedback}")

    if progress.current_index == len(progress.round_slots):
        if session.final_report is None:
            if st.button("Generate report"):
                with st.spinner("Building your report..."):
                    service().complete_report(session)
                st.rerun()
        else:
            render_report(session)
            # Compute suggested skills without constructing provider clients.
            suggested = InterviewService.weak_skills(session)
            with st.form(f"practice_{progress.round_id}"):
                count = st.selectbox("Additional practice questions", [3, 5, 10])
                skills = st.multiselect("Practice focus", suggested, default=suggested[:2])
                practice = st.form_submit_button("Start focused practice")
            if practice:
                try:
                    service().start_practice(session, count=count, skills=skills)
                except (ValueError, ResearchPreparationError) as error:
                    st.warning(str(error))
                    return
                st.rerun()
    else:
        if progress.current_question is None:
            try:
                with st.spinner("Selecting the next question..."):
                    service().show_question(session)
            except ResearchPreparationError:
                st.error("No unused question is available. Retry later; your answers are saved.")
                if st.button("Retry question selection"):
                    st.rerun()
                render_fresh_retry(session, service)
                return
            st.rerun()
        question = progress.current_question
        with st.chat_message("assistant"):
            st.write(question.question)
            st.caption(
                f"{question.skill} | Practice: {question.difficulty.value} | "
                f"JD target: {progress.target_difficulty[question.skill].value}"
            )
            st.caption(
                "Source: web extraction"
                if question.source == "web"
                else "Source: generated practice"
            )
            if question.source_url:
                st.link_button(question.source_title or "Source", str(question.source_url))
            if "Generic skill practice" in question.rationale:
                st.caption(question.rationale)
        with st.form(f"answer_{progress.current_turn_id}"):
            answer = st.text_area(
                "Your answer", max_chars=settings.max_answer_characters, height=180
            )
            submitted = st.form_submit_button("Submit answer", type="primary")
        if submitted:
            try:
                with st.spinner("Evaluating your answer..."):
                    service().submit(session, answer=answer, turn_id=progress.current_turn_id)
            except UnrelatedAnswerError as error:
                st.warning(str(error))
                return
            except ValueError as error:
                st.warning(str(error))
                return
            st.rerun()

    render_fresh_retry(session, service)


def render_fresh_retry(session, service):
    if session.status != InterviewStatus.EVALUATING and st.button("Fresh interview on same JD"):
        fresh = service().fresh_retry(session)
        if fresh.is_demo:
            fresh.research_complete = True
        st.session_state["active_session_id"] = fresh.session_id
        st.session_state.pop("pending_jd_result", None)
        st.session_state.pop("jd_review_id", None)
        st.rerun()
