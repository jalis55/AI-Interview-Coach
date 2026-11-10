"""A validated evaluation runnable with staged, bounded conversation history."""

import warnings

from langchain_core._api import LangChainDeprecationWarning
from langchain_core.messages import AIMessage
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables import RunnableLambda, RunnableWithMessageHistory

from ai_interview_coach.models.interview import EvaluationDecision
from ai_interview_coach.prompts.evaluation import EVALUATION_CONTEXT, EVALUATION_SYSTEM
from ai_interview_coach.providers.groq import create_chat_model


def build_evaluator(*, fallback=False):
    messages = [("system", EVALUATION_SYSTEM), ("system", EVALUATION_CONTEXT)]
    parser = PydanticOutputParser(pydantic_object=EvaluationDecision)
    if fallback:
        messages.append(("system", "Return only JSON, no Markdown.\n{format_instructions}"))
    messages += [MessagesPlaceholder("history"), ("human", "{message}")]
    prompt = ChatPromptTemplate.from_messages(messages)
    if fallback:
        return (
            prompt.partial(format_instructions=parser.get_format_instructions())
            | create_chat_model()
            | parser
        )
    return prompt | create_chat_model().with_structured_output(
        EvaluationDecision,
        method="json_schema",
        strict=False,
    )


def with_staged_history(chain, history, max_messages, max_characters=24000):
    def bounded(inputs):
        selected = []
        remaining = max_characters
        for message in reversed(inputs["history"][-max_messages:]):
            content = message.content if isinstance(message.content, str) else str(message.content)
            if remaining <= 0:
                break
            selected.append(message.model_copy(update={"content": content[:remaining]}))
            remaining -= len(content[:remaining])
        return {**inputs, "history": list(reversed(selected))}

    def pack(output):
        decision = EvaluationDecision.model_validate(output)
        return {"decision": decision, "reply": AIMessage(content=decision.model_dump_json())}

    # Required LCEL concept in this project; suppress only this known migration notice.
    # LangGraph persistence is outside the agreed architecture. See docs/architecture.md.
    with warnings.catch_warnings():
        warnings.filterwarnings(
            "ignore",
            message="RunnableWithMessageHistory is deprecated.*",
            category=LangChainDeprecationWarning,
        )
        return RunnableWithMessageHistory(
            RunnableLambda(bounded) | chain | RunnableLambda(pack),
            lambda session_id: history,
            input_messages_key="message",
            history_messages_key="history",
            output_messages_key="reply",
        )
