"""
Survey question reference mapping (Spec Section 21).

Maps question codes to full wording for tooltips and chart footers.
Includes response type information for context.
"""

# ---------------------------------------------------------------------------
# 21.1 Shopping & Switching Questions
# ---------------------------------------------------------------------------
QUESTION_WORDING = {
    "Q4": (
        "Which company currently insures the car you consider to be your main car? "
        "(Single code, dropdown list)"
    ),
    "Q6": (
        "Thinking about the renewal price quoted by the insurer you were with before "
        "your recent renewal, was it higher or lower than what you paid last year? "
        "(Single code)"
    ),
    "Q7": (
        "Did you shop around for one or more alternative quotes during your recent "
        "motor insurance renewal? (Single code: Yes / No)"
    ),
    "Q8": (
        "Please rank your reasons for shopping around at your recent renewal, starting "
        "from the most important/main reason, down to the least important reason. "
        "(Ranked, multi-select. Asked of shoppers only — Q7 = Yes)"
    ),
    "Q9b": (
        "When you shopped around for your motor insurance recently, which of the "
        "following did you use to shop for quotes? "
        "(Multi-select. Asked of shoppers only — Q7 = Yes)"
    ),
    "Q11": (
        "Which price comparison website(s) did you use? "
        "(Multi-select. Asked of PCW users only — Q9b = 3)"
    ),
    "Q15": (
        "At your recent renewal, did you switch to a new insurance provider? "
        "(Single code: Yes (switched) / No (stayed) / No previous policy)"
    ),
    "Q18": (
        "Please rank your reasons for staying with your insurance provider, starting "
        "from the most important/main reason, down to the least important reason. "
        "(Ranked, multi-select. Asked of non-switchers only — Q15 = No)"
    ),
    "Q19": (
        "Please rank your reasons for not shopping around for alternative quotes at "
        "your recent renewal, starting from the most important/main reason, down to "
        "the least important reason. "
        "(Ranked, multi-select. Asked of non-shoppers only — Q7 = No)"
    ),
    "Q31": (
        "What are your reason(s) for switching to a new insurer? "
        "(Multi-select. Asked of switchers only — Q15 = Yes)"
    ),
    "Q33": (
        "Please rank your reasons that influenced your decision to choose your current "
        "insurer, starting from the most important/main reason, down to the least "
        "important reason. "
        "(Ranked, multi-select. Asked of switchers only — Q15 = Yes)"
    ),
    "Q39": (
        "Who was your motor insurance provided by before you took out your policy "
        "with your current insurer? "
        "(Single code, dropdown. Asked of switchers only — Q15 = Yes)"
    ),
    "Q40a": (
        "How would you rate your overall satisfaction with your previous insurer? "
        "(Slider: 1 = Completely dissatisfied to 5 = Completely satisfied. "
        "Asked of switchers with known previous insurer)"
    ),
    "Q40b": (
        "How likely are you to recommend your previous insurer to your friends and family? "
        "(Slider: 0 = Not likely at all to 10 = Extremely likely. "
        "Asked of switchers with known previous insurer)"
    ),

    # ---------------------------------------------------------------------------
    # 21.2 Awareness Questions
    # ---------------------------------------------------------------------------
    "Q1": (
        "Please type in the names of any companies you are aware of that sell motor "
        "insurance. (Open text, up to 10 entries. All respondents)"
    ),
    "Q2": (
        "Which of these companies are you aware of selling motor insurance? Please "
        "tick all that apply. "
        "(Multi-select from randomised brand list. All respondents)"
    ),
    "Q27": (
        "Which of these companies would you consider getting a quote from the next "
        "time you come to renew your insurance policy? "
        "(Multi-select from brands named at Q1 and selected at Q2. All respondents)"
    ),

    # ---------------------------------------------------------------------------
    # 21.3 Demographics (for Cohort Heat Map)
    # ---------------------------------------------------------------------------
    "S1a": (
        "What is your date of birth? "
        "(Date. All respondents. Used to derive age bands)"
    ),
    "S2": (
        "Are you...? Male / Female / I identify in another way / Prefer not to say "
        "(Single code. All respondents)"
    ),
    "S3": (
        "What region do you live in? "
        "(Single code. All respondents. 10 regions)"
    ),
    "Q57": (
        "Which best describes your living situation? "
        "(Single code: Own outright / Own with mortgage / Renting / "
        "Living with parents or family / Council residence / Other)"
    ),
    "Q58": (
        "Do you have children? "
        "(Single code: No / Yes, live with me all the time / "
        "Yes, live with me some of the time / Yes, left home)"
    ),
    "Q60": (
        "What is your current employment status? "
        "(Single code: Full time / Part time / Self employed / Retired / "
        "Student / Unemployed / Houseperson / Other)"
    ),
    "Q61": (
        "What is the approximate combined annual income for all members of "
        "your household? "
        "(Single code. Banded from Less than \u00a310,000 to \u00a3150,000 or more. "
        "Includes Prefer not to say)"
    ),
    "Q62": (
        "What is the occupation of the main income earner in your household? "
        "(Single code. Maps to social grade: ABC1 (Q62 = 1-4) / C2DE (Q62 = 5-11))"
    ),
    "DSEG": (
        "Social grade derived from Q62. ABC1 = professional/managerial/clerical. "
        "C2DE = skilled manual/semi-skilled/unskilled."
    ),

    # ---------------------------------------------------------------------------
    # 21.4 Claims Questions
    # ---------------------------------------------------------------------------
    "Q52": (
        "How satisfied were you with the claims process overall? "
        "(Slider: 1 = Completely dissatisfied to 5 = Completely satisfied. "
        "Asked of claimants only)"
    ),
    "Q53": (
        "How would you rate the following aspects of your claims experience? "
        "(Slider: 1 = Completely dissatisfied to 5 = Completely satisfied. "
        "Asked of claimants only. Per-statement rating)"
    ),
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
