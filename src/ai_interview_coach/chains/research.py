"""LCEL extraction and generation with structured and JSON-parser variants."""

from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import ChatPromptTemplate

from ai_interview_coach.models.question import QuestionBatch
from ai_interview_coach.models.research import QuestionResearchRequest
from ai_interview_coach.prompts.research import (
    EXTRACTION_SYSTEM,
    GENERATION_SYSTEM,
    JSON_INSTRUCTIONS,
    RESEARCH_INPUT,
)
from ai_interview_coach.providers.groq import create_chat_model

TOOL_NAME = "find_interview_questions"


def build_question_chain(*, extract: bool, fallback: bool = False):
    system = EXTRACTION_SYSTEM if extract else GENERATION_SYSTEM
    messages = [("system", system)]
    if fallback:
        messages.append(("system", JSON_INSTRUCTIONS))
    messages.append(("human", RESEARCH_INPUT))
    prompt = ChatPromptTemplate.from_messages(messages)
    model = create_chat_model()
    if fallback:
        parser = PydanticOutputParser(pydantic_object=QuestionBatch)
        return prompt.partial(format_instructions=parser.get_format_instructions()) | model | parser
    return prompt | model.with_structured_output(
        QuestionBatch,
        method="json_schema",
        strict=False,
    )


def build_research_tool_planner():
    tool = {
        "type": "function",
        "function": {
            "name": TOOL_NAME,
            "description": "Find interview-question candidates for one authorized core skill.",
            "parameters": QuestionResearchRequest.model_json_schema(),
        },
    }
    return create_chat_model().bind_tools([tool])
