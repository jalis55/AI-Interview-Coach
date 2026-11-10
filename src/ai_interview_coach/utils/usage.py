"""LangChain callbacks record counts/tokens, never prompts or credentials."""

from threading import Lock

from langchain_core.callbacks import BaseCallbackHandler


class UsageCollector(BaseCallbackHandler):
    _lock = Lock()

    def __init__(self, session, stage):
        self.session = session
        self.stage = stage

    def _start(self):
        with self._lock:
            usage = self.session.usage
            usage.provider_calls += 1
            usage.calls_by_stage[self.stage] = usage.calls_by_stage.get(self.stage, 0) + 1

    def on_chat_model_start(self, serialized, messages, **kwargs):
        self._start()

    def on_llm_start(self, serialized, prompts, **kwargs):
        self._start()

    def on_llm_error(self, error, **kwargs):
        with self._lock:
            self.session.usage.failed_calls += 1

    def on_llm_end(self, response, **kwargs):
        usage = (response.llm_output or {}).get("token_usage")
        if not usage and response.generations and response.generations[0]:
            message = getattr(response.generations[0][0], "message", None)
            usage = getattr(message, "usage_metadata", None)
        if not isinstance(usage, dict):
            return
        with self._lock:
            summary = self.session.usage
            summary.metered_responses += 1
            summary.input_tokens += int(
                usage.get("input_tokens", usage.get("prompt_tokens", 0)) or 0
            )
            summary.output_tokens += int(
                usage.get("output_tokens", usage.get("completion_tokens", 0)) or 0
            )


def model_config(session, stage):
    if session is None:
        return {}
    return {
        "callbacks": [UsageCollector(session, stage)],
        "configurable": {"session_id": str(session.session_id)},
    }
