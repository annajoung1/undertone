# API 검증 결과 — 2026-09-18

Higgs Realtime을 직접 때려보고 확인한 사실만 적는다. 추측은 ❓로 표시.

## 확인됨 ✅

| 항목 | 값 |
|---|---|
| 엔드포인트 | `wss://api.boson.ai/v1/realtime?model=higgs-realtime` |
| 인증 | `Authorization: Bearer $BOSON_API_KEY` |
| 프로토콜 | **OpenAI Realtime API와 동일** (이벤트 이름까지 같음) |
| 출력 오디오 | base64 PCM, 24kHz, 16-bit, mono |
| 모델 목록 | `higgs-realtime`, `higgs-realtime-tts`, `higgs-tts-v3`, `higgs-tts-mps`, `higgs-stt-3.1` |

확인된 이벤트 흐름:
session.update → conversation.item.create → response.create
→ response.output_audio.delta (267개) + response.output_audio_transcript.delta → response.done

첫 응답 품질 (프롬프트: LA 24세 스킨케어 쇼퍼, 질문: "$38 한국 나이트 세럼 어때?"):
> "Omg, that's kinda steep for a night serum! I'd probably look for something
> similar under $25. Have you checked out some of the drugstore brands?"

→ 페르소나가 지어낸 티 없이 **진짜 가격 저항**을 냄. 아이디어의 핵심 가정이 검증됨.

## 막힌 것 ⛔

**`default` 외의 voice 값이 전부 거부된다.**
`alloy/echo/shimmer/ash/ballad/coral/sage/verse/marin/cedar/nova/onyx/fable/
en_woman/en_man/belinda/female/male/...` → 전부 `Invalid voice '...': not found`

`GET /v1/voices` → `{"object":"list","data":[]}` (빈 배열)
→ ❓**보이스를 먼저 생성/클로닝해야 목록이 차는 구조로 추정.** 미확인.

### 이게 왜 중요한가
"3명의 패널이 서로 다른 목소리로 토론" 이 데모의 핵심인데, 목소리가 하나면 누가 말하는지 구분이 안 됨 → UX 25% 직격.

### 대응 (우선순위)
1. `POST /v1/voices` 보이스 클로닝 확인 — **15분 타임박스**
2. 안 되면 `higgs-tts-v3` + reference audio로 페르소나 음성만 따로 생성
3. 그것도 안 되면 목소리 1개 + 말투/속도/성격으로 구분 (최후)

## 기타
- rate limit 있음. 연속 호출 시 429. 세션 간 1.5~3초 간격 필요.
- `/v1/audio/voices`, `/v1/realtime/voices` → 404 또는 429
