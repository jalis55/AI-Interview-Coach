"""Clearly labeled last-resort prompts, with finite novelty rather than silent repeats."""


def generic_question_texts(skill):
    if skill == "behavioral":
        return [
            "Describe a project where you resolved a team conflict. What did you do?",
            "Describe a situation where feedback changed your decision. What happened?",
            "Describe a project balancing quality and delivery time. What was the outcome?",
            "Describe a situation where you owned a mistake. How did your team recover?",
            "Describe a decision you made with incomplete information. How did you assess risk?",
            "Describe a project where you explained a complex idea to a nontechnical teammate.",
            "Describe a situation where priorities changed suddenly. What action did you take?",
            "Describe a project with a disputed technical decision. How was it resolved?",
            "Describe a team experience where you helped someone learn a difficult concept.",
            "Describe a situation where you identified an ethical concern and raised it.",
            "Describe a project where customer feedback changed your original approach.",
            "Describe a situation where you handled an urgent incident with your team.",
            "Describe a decision where you traded short-term speed for long-term maintainability.",
            "Describe a project where unclear ownership caused problems. What did you change?",
            "Describe a situation where your first solution failed. What did you learn?",
        ]
    return [
        f"Explain a core concept in {skill} with a small practical example.",
        f"How would you apply {skill} to a backend or product task, and verify the result?",
        f"Describe how you would diagnose a failure involving {skill} and compare fixes.",
        f"What trade-offs would you consider when maintaining a system that uses {skill}?",
        f"What security risks would you investigate before deploying a feature using {skill}?",
        f"Design a test strategy for a small component that depends on {skill}.",
        f"How would you measure resource consumption in a workload involving {skill}?",
        f"Describe a safe migration strategy for an existing product using {skill}.",
        f"Which monitoring signals would help detect failures in a service using {skill}?",
        f"How would you explain the limitations of {skill} to a new teammate?",
        f"What would you look for during a code review of a change involving {skill}?",
        f"Describe your incident response when a recent change involving {skill} fails.",
        f"How would you preserve backward compatibility while changing a {skill} component?",
        f"Design a staged rollout and rollback approach for a feature that uses {skill}.",
        f"How would you investigate an integration failure between {skill} and another service?",
        f"Which assumptions would you validate before selecting {skill} for a new project?",
        f"Explain how you would benchmark competing implementations involving {skill}.",
        f"How would you document an important architectural decision involving {skill}?",
        f"What recovery plan would you propose for lost or corrupted state involving {skill}?",
        f"Describe how you would simplify an overly complex implementation involving {skill}.",
    ]
