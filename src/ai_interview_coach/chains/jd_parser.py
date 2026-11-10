"""Primary and fallback JD parsing pipelines."""

from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import Runnable

from ai_interview_coach.models.jd_parse import JDParseResult
from ai_interview_coach.prompts.prompt_jd_parser import (
    JD_FALLBACK_INSTRUCTIONS,
    JD_SYSTEM_PROMPT,
)
from ai_interview_coach.providers.groq import create_chat_model


def build_jd_parser() -> Runnable:
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", JD_SYSTEM_PROMPT),
            ("human", "{jd_text}"),
        ]
    )

    structured_model = create_chat_model().with_structured_output(
        JDParseResult,
        method="json_schema",
        strict=False,
    )

    return prompt | structured_model


def build_jd_fallback_parser() -> Runnable:
    output_parser = PydanticOutputParser(
        pydantic_object=JDParseResult,
    )

    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", JD_SYSTEM_PROMPT),
            ("system", JD_FALLBACK_INSTRUCTIONS),
            ("human", "{jd_text}"),
        ]
    ).partial(
        format_instructions=output_parser.get_format_instructions(),
    )

    return prompt | create_chat_model() | output_parser
