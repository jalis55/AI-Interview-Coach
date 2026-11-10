"""Run with: uv run streamlit run demo.py (no provider calls)."""

import os

os.environ.setdefault("GROQ_API_KEY", "offline-demo")
os.environ.setdefault("TAVILY_API_KEY", "offline-demo")
os.environ.setdefault("GROQ_MODEL", "offline-demo")
os.environ["DEMO_MODE"] = "true"

from ai_interview_coach.ui.app import main  # noqa: E402

if __name__ == "__main__":
    main()
