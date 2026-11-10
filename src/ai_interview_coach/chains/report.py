"""Validated textual branches; service assembles them with RunnableParallel."""

from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import ChatPromptTemplate

from ai_interview_coach.models.report import Recommendations, ReportText
from ai_interview_coach.prompts.report import REPORT_SYSTEM
from ai_interview_coach.providers.groq import create_chat_model


def build_report_branch(task, *, recommendations=False, fallback=False):
    schema = Recommendations if recommendations else ReportText
    parser = PydanticOutputParser(pydantic_object=schema)
    messages = [("system", REPORT_SYSTEM)]
    if fallback:
        messages.append(("system", "Return only JSON.\n{format_instructions}"))
    messages.append(("human", "Observed evidence: {evidence}"))
    prompt = ChatPromptTemplate.from_messages(messages).partial(task=task)
    if fallback:
        return (
            prompt.partial(format_instructions=parser.get_format_instructions())
            | create_chat_model()
            | parser
        )
    return prompt | create_chat_model().with_structured_output(
        schema,
        method="json_schema",
        strict=False,
    )
