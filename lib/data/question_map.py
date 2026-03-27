"""
Survey question reference data.

Maps question IDs to their verbatim question text and a plain-English
description of how the metric is calculated. Used by render_question_info()
to show "About this data" expanders on every screen section.
"""

QUESTION_MAP: dict[str, dict[str, str]] = {
    "Q1": {
        "text": "Without looking anything up, which motor insurance companies can you think of?",
        "calc": "Unprompted awareness: free-text responses normalised to brand names.",
    },
    "Q2": {
        "text": "Which of the following motor insurance companies have you heard of?",
        "calc": "Prompted awareness: percentage selecting each brand.",
    },
    "Q3": {
        "text": "Did you shop around for quotes from other insurance companies before renewing?",
        "calc": "Shopping rate: percentage answering Yes.",
    },
    "Q6": {
        "text": "Compared to the premium you paid last year, was the renewal price you were quoted higher, lower, or about the same?",
        "calc": "Percentage of respondents selecting each option.",
    },
    "Q6a": {
        "text": "You said your renewal price was higher. By approximately how much per year did it increase?",
        "calc": "Distribution across price bands. Average computed from band midpoints.",
    },
    "Q6b": {
        "text": "You said your renewal price was lower. By approximately how much per year did it decrease?",
        "calc": "Distribution across price bands. Average computed from band midpoints.",
    },
    "Q7": {
        "text": "Did you switch to a different insurance company at renewal?",
        "calc": "Switching rate: percentage answering Yes.",
    },
    "Q8": {
        "text": "What were your reasons for shopping around? (Select all that apply)",
        "calc": "Ranked reasons: percentage citing each reason, ranked by frequency.",
    },
    "Q9a": {
        "text": "How did you shop around for motor insurance quotes?",
        "calc": "Channel usage: percentage using each shopping channel.",
    },
    "Q18": {
        "text": "You shopped around but stayed with your existing insurer. Why?",
        "calc": "Ranked reasons for staying after shopping.",
    },
    "Q19": {
        "text": "You did not shop around. Why not?",
        "calc": "Ranked reasons for not shopping.",
    },
    "Q21": {
        "text": "How long have you been insured with your current provider?",
        "calc": "Percentage of respondents in each tenure band.",
    },
    "Q27": {
        "text": "Which of these companies would you consider using for your motor insurance?",
        "calc": "Consideration rate: percentage selecting each brand.",
    },
    "Q31": {
        "text": "What were your reasons for switching to a new insurer?",
        "calc": "Ranked reasons for leaving.",
    },
    "Q33": {
        "text": "Why did you choose your new insurer over the alternatives?",
        "calc": "Ranked reasons for choosing new insurer.",
    },
    "Q47": {
        "text": "Overall, how satisfied are you with your current motor insurance provider?",
        "calc": "Mean satisfaction score on a 1-5 scale.",
    },
    "Q48": {
        "text": "How likely are you to recommend your motor insurance provider to a friend or colleague?",
        "calc": "NPS: % promoters (9-10) minus % detractors (0-6) on 0-10 scale.",
    },
    "Q52": {
        "text": "If you made a claim, how satisfied were you with the claims process?",
        "calc": "Mean claims satisfaction score on a 1-5 scale.",
    },
}
