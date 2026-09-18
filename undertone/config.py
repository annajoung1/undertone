"""데모 시나리오 설정. 실제 서비스에서는 대표가 입력하는 값들이다."""

# --- 대표가 알고 싶어하는 것 (한국어 브리핑) ------------------------------
FOUNDER_BRIEF_KO = (
    "저희 시트마스크 10장 팩을 미국 소비자분들께 2주간 시딩했습니다. "
    "제일 궁금한 건 실제로 좋았는지, 기대했던 거랑 뭐가 달랐는지예요. "
    "괜찮았다면 얼마까지 낼 수 있는지도 듣고 싶습니다."
)

PRODUCT = {
    "brand": "Korean sheet mask brand (SMB, first US launch)",
    "item": "10-sheet hydrating sheet mask pack",
    "seeded_for": "2 weeks",
    "price_being_tested_usd": 32,      # 10장 팩 = 장당 $3.2
    "category_anchors_usd": {          # 미국 실제 시장가 (2026)
        "Rhode Glazing Milk": 32,
        "Rhode Peptide Lip Treatment": 18,
        "Summer Fridays Jet Lag Mask": 49,
        "Laneige Water Sleeping Mask": 34,
        "Mediheal (per sheet)": 3,
    },
}

# --- 인터뷰 가이드 -------------------------------------------------------
# 순서가 중요하다. 행동 -> 만족 -> 기대차이 -> (조건부) 가격 -> 비교
# 가격은 만족도에 종속된 질문이다. 앞에 두면 답이 오염된다.
GUIDE = [
    # 각 항목은 질문 "하나"여야 한다. 여러 개를 적으면 인터뷰어가 전부 이어서 묻는다.
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

# --- 시뮬레이션 응답자 ---------------------------------------------------
# 중요: 대본을 박지 않는다. '실제 소비자처럼 예의 바르게 행동하라'까지만 준다.
# 톤 불일치가 나오면 그건 연출이 아니라 실제 발생한 것이다.
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

# --- 톤 불일치 판정 기준 -------------------------------------------------
# 절대값이 아니라 '그 사람의 평소 톤 대비 하락폭'으로 판정한다.
# 실측: 같은 사람의 시큰둥한 발화 75 vs 진심 발화 96 -> 21점 하락.
ENGAGEMENT_DROP = 15     # 본인 기준선보다 이만큼 떨어지면 '평평함'
FLAT_ENGAGEMENT = 48     # (참고용 절대 기준 — 색상 표시에만 쓴다)
