"""
Survey question reference mapping (Spec Section 3.2 / 13.7).

Maps question codes to full wording for tooltips and chart footers.
"""

QUESTION_WORDING = {
    "S6": "S6: In which month did your policy renew?",
    "Q1": "Q1: Which companies come to mind that sell motor/home insurance? (Spontaneous, open-text)",
    "Q2": "Q2: Which of these companies are you aware of selling motor/home insurance? (Prompted, multi-select)",
    "Q4": "Q4: Which company is your current motor/home insurance with?",
    "Q7": "Q7: Did you shop around at your most recent renewal?",
    "Q8": "Q8: What were your reasons for shopping around? (Ranked)",
    "Q9b": "Q9b: Which channels did you use to shop around? (Multi-select)",
    "Q11": "Q11: Which price comparison websites did you use? (Multi-select)",
    "Q15": "Q15: Did you switch insurer at your most recent renewal?",
    "Q18": "Q18: What were your reasons for staying with your insurer after shopping? (Ranked)",
    "Q19": "Q19: What were your reasons for not shopping around? (Ranked)",
    "Q27": "Q27: Which of these companies would you consider buying insurance from? (Multi-select)",
    "Q31": "Q31: What were your reasons for switching away from your previous insurer? (Multi-select)",
    "Q33": "Q33: What were your reasons for choosing your new insurer? (Ranked)",
    "Q39": "Q39: Which company were you previously insured with?",
    "Q40a": "Q40a: How satisfied were you with your previous insurer overall? (1-5 scale)",
    "Q40b": "Q40b: How likely would you be to recommend your previous insurer to a friend? (0-10, NPS)",
    "Q52": "Q52: How satisfied were you with the claims process overall? (1-5 scale)",
    "Q53": "Q53: How would you rate the following aspects of your claims experience? (1-5 scale)",
}


def get_question_text(q_code: str) -> str:
    """Return full question wording for a given question code."""
    return QUESTION_WORDING.get(q_code, q_code)


def get_question_tooltip(q_code: str) -> str:
    """Return tooltip-formatted question reference."""
    text = QUESTION_WORDING.get(q_code)
    if text:
        return f"Source: {text}"
    return ""
