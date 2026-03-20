"""
Pet insurance question classification and aliases.

Pet data comes from 4 EAV tables with full-text question names.
This module maps them to short aliases and classifies by pivot type.
"""
from __future__ import annotations

# ---------------------------------------------------------------------------
# Question aliases: full-text -> short code
# ---------------------------------------------------------------------------

PET_QUESTION_ALIASES = {
    # pet_data_new (26 questions)
    "Is your pet microchipped?": "PET_MICROCHIPPED",
    "Is your pet a pedigree or crossbreed?": "PET_BREED_TYPE",
    "What type of pet do you have insured?": "PET_TYPE",
    "How old is your pet?": "PET_AGE",
    "How long have you had pet insurance?": "PET_TENURE",
    "What type of pet insurance policy do you have?": "PET_POLICY_TYPE",
    "How did you purchase your pet insurance policy?": "PET_PURCHASE_CHANNEL",
    "What level of annual vet fee cover does your policy provide?": "PET_VET_COVER",
    "How much is your annual premium?": "PET_ANNUAL_PREMIUM",
    "How much is your policy excess?": "PET_EXCESS",
    "Have you made a claim on your pet insurance in the last 12 months?": "PET_CLAIMED",
    "How satisfied were you with the claims process?": "PET_CLAIMS_SAT",
    "Did you shop around at your last renewal?": "PET_SHOPPED",
    "How many quotes did you get?": "PET_NUM_QUOTES",
    "What was the main reason you shopped around?": "PET_SHOP_REASON",
    "What was the main reason you switched?": "PET_SWITCH_REASON",
    "What was the main reason you stayed?": "PET_STAY_REASON",
    "How satisfied are you with your current provider?": "PET_PROVIDER_SAT",
    "Would you recommend your provider to a friend?": "PET_RECOMMEND",
    "How did you first hear about your current provider?": "PET_FIRST_HEARD",
    "What is the most important factor when choosing pet insurance?": "PET_IMPORTANT_FACTOR",
    "Gender": "PET_GENDER",
    "Do you have any other types of insurance?": "PET_OTHER_INSURANCE",
    "What breed is your dog?": "PET_DOG_BREED",
    "What breed is your cat?": "PET_CAT_BREED",
    "How many pets do you have insured?": "PET_NUM_PETS",
    # provider_data (9 questions)
    "Which providers were you aware of?": "PET_PROMPTED_AWARENESS",
    "List any providers you can think of?": "PET_SPONTANEOUS_AWARENESS",
    "Which providers did you consider?": "PET_CONSIDERATION",
    "Which providers did you get a quote from?": "PET_QUOTED",
    "Which of these providers have you heard anything positive about recently?": "PET_POSITIVE_HEARD",
    "Which of these providers have you heard anything negative about recently?": "PET_NEGATIVE_HEARD",
    "Which of these providers do you trust the most?": "PET_TRUST",
    "Which of these providers do you think offers the best value?": "PET_BEST_VALUE",
    "Which of these providers would you never consider?": "PET_NEVER_CONSIDER",
    # remaining_data (12 questions)
    "What was the main reason for choosing your current provider?": "PET_CHOOSE_REASON",
    "What could your provider do to improve?": "PET_IMPROVE",
    "What do you like most about your current provider?": "PET_LIKE_MOST",
    "What channels did you use to shop around?": "PET_SHOP_CHANNELS",
    "Which PCWs did you use?": "PET_PCWS_USED",
    "How satisfied are you with value for money?": "PET_VFM_SAT",
    "How satisfied are you with policy coverage?": "PET_COVERAGE_SAT",
    "How satisfied are you with customer service?": "PET_SERVICE_SAT",
    "How satisfied are you with the ease of making a claim?": "PET_CLAIM_EASE_SAT",
    "How satisfied are you with communication from your provider?": "PET_COMMS_SAT",
    "How likely are you to renew with your current provider?": "PET_RENEW_LIKELIHOOD",
    "How important is it that your provider is well known?": "PET_BRAND_IMPORTANCE",
}

# Reverse lookup
PET_ALIAS_TO_QUESTION = {v: k for k, v in PET_QUESTION_ALIASES.items()}

# ---------------------------------------------------------------------------
# Classification by pivot type
# ---------------------------------------------------------------------------

# Single-code: one answer per respondent
PET_SINGLE_CODE = {
    "PET_MICROCHIPPED", "PET_BREED_TYPE", "PET_TYPE", "PET_AGE",
    "PET_TENURE", "PET_POLICY_TYPE", "PET_PURCHASE_CHANNEL",
    "PET_VET_COVER", "PET_ANNUAL_PREMIUM", "PET_EXCESS",
    "PET_CLAIMED", "PET_CLAIMS_SAT", "PET_SHOPPED", "PET_NUM_QUOTES",
    "PET_SHOP_REASON", "PET_SWITCH_REASON", "PET_STAY_REASON",
    "PET_PROVIDER_SAT", "PET_RECOMMEND", "PET_FIRST_HEARD",
    "PET_IMPORTANT_FACTOR", "PET_GENDER", "PET_DOG_BREED",
    "PET_CAT_BREED", "PET_NUM_PETS",
    # remaining_data single-code
    "PET_CHOOSE_REASON", "PET_IMPROVE", "PET_LIKE_MOST",
    "PET_VFM_SAT", "PET_COVERAGE_SAT", "PET_SERVICE_SAT",
    "PET_CLAIM_EASE_SAT", "PET_COMMS_SAT", "PET_RENEW_LIKELIHOOD",
    "PET_BRAND_IMPORTANCE",
}

# Multi-code: multiple answers per respondent (boolean columns)
PET_MULTI_CODE = {
    "PET_PROMPTED_AWARENESS", "PET_CONSIDERATION",
    "PET_QUOTED", "PET_POSITIVE_HEARD", "PET_NEGATIVE_HEARD",
    "PET_TRUST", "PET_BEST_VALUE", "PET_NEVER_CONSIDER",
    "PET_OTHER_INSURANCE", "PET_SHOP_CHANNELS", "PET_PCWS_USED",
}

# Free-text spontaneous awareness: excluded from multi-code pivot
# because each unique text response would become its own boolean column,
# causing a memory explosion. Needs brand normalisation like Motor/Home Q1.
PET_SPONTANEOUS_AWARENESS = {"PET_SPONTANEOUS_AWARENESS"}

# NPS/Scale: numeric answer
PET_NPS_SCALE = set()  # Statement data handled separately

# Grid: statement_data (21 statements, 7-point scale)
PET_GRID_STATEMENTS = set()  # Will be populated when statement data is loaded

PET_ALL_KNOWN = PET_SINGLE_CODE | PET_MULTI_CODE | PET_NPS_SCALE
