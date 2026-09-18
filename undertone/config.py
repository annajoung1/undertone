"""Scenario for the demo. In production the founder supplies all of this."""

# --- What the founder wants to find out. Spoken in Korean. -----------------
# Kept in Korean on purpose: the founder never has to leave their own language.
# English gloss: "We seeded a 10-pack of our sheet masks to US consumers for two weeks.
# What I most want to know is whether they actually liked it and what was different from
# what they expected. If it was good, I want to hear what they would pay."
FOUNDER_BRIEF_KO = (
    "저희 시트마스크 10장 팩을 미국 소비자분들께 2주간 시딩했습니다. "
    "제일 궁금한 건 실제로 좋았는지, 기대했던 거랑 뭐가 달랐는지예요. "
    "괜찮았다면 얼마까지 낼 수 있는지도 듣고 싶습니다."
)

PRODUCT = {
    "brand": "Korean sheet mask brand (SMB, first US launch)",
    "item": "10-sheet hydrating sheet mask pack",
    "seeded_for": "2 weeks",
    "price_being_tested_usd": 32,      # $3.20 per sheet
    "category_anchors_usd": {          # real US retail, 2026
        "Rhode Glazing Milk": 32,
        "Rhode Peptide Lip Treatment": 18,
        "Summer Fridays Jet Lag Mask": 49,
        "Laneige Water Sleeping Mask": 34,
        "Mediheal (per sheet)": 3,
    },
}

# --- Interview guide -------------------------------------------------------
# The order matters: behaviour -> satisfaction -> expectation -> (conditional) price
# -> comparison. Price is downstream of satisfaction. Asked early, it poisons every
# answer after it.
GUIDE = [
    # One question per entry. List two and the interviewer will faithfully ask both.
    dict(id="behavior", intent=(
        "Ask how many of the ten masks they actually used. Nothing else.")),
    dict(id="satisfaction", intent=(
        "Ask if they liked it. Keep it open and easy."),
        probe_target=True),
    dict(id="expectation", intent=(
        "Ask what surprised them about it, good or bad.")),
    dict(id="willingness", intent=(
        "Ask what they would pay for the 10-pack with their own money."),
        conditional_on_satisfaction=True),
    dict(id="alternatives", intent=(
        "Ask what skincare they buy for themselves when they treat themselves. "
        "Let them name the brand. Do not suggest one.")),
    dict(id="comparison", intent=(
        "Look up the real US price of the brand they just named, then ask them to "
        "pick one: this 10-pack, or that product."),
        wants_tool=True),
]

# --- Simulated respondent --------------------------------------------------
# Used only when no real person is available. The character is told how a polite
# consumer behaves; it is never told what to score. Any mismatch that shows up was
# measured, not staged. Run with --live to put a real person here instead.
RESPONDENT = dict(
    name="Rachel",
    label="28 · Brooklyn · Sephora + Amazon",
    instructions=(
        "You are Rachel, 28, living in Brooklyn. You were sent a 10-pack of Korean sheet "
        "masks for free two weeks ago and agreed to a short interview about them.\n"
        "\n"
        "How you actually behave — this is important:\n"
        "- You are a polite person. When you don't love something, you soften it rather "
        "  than say it plainly. You say things like 'it was nice', 'yeah, it was fine', "
        "  'I liked it' even when you were not impressed.\n"
        "- You only give the blunt version when someone asks you a direct, specific "
        "  follow-up question. Then you are honest.\n"
        "- You got the product for free, which makes you even less likely to criticize it "
        "  unprompted.\n"
        "- Your real experience: the masks were fine. The essence dried out faster than you "
        "  expected and the fit around the nose was loose. You used four of the ten. You "
        "  would not pay full price, but you would not volunteer that.\n"
        "\n"
        "If you are asked what you would compare this to, or what something costs, call the "
        "lookup_competitor tool to check the real current price before answering — you are "
        "the kind of shopper who actually checks.\n"
        "\n"
        "Speak in natural American English, 1-3 sentences per answer. Never break character. "
        "Never mention that you are an AI."
    ),
)

# --- Mismatch sensitivity ---------------------------------------------------
# Judged as a fall from the speaker's own norm, never against an absolute scale.
# Measured: the same person, the same sentence - 75 said politely, 96 said sincerely.
ENGAGEMENT_DROP = 15     # points below their own baseline before it counts
FLAT_ENGAGEMENT = 48     # absolute reference, used only for gauge colours
