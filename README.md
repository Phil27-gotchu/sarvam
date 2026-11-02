# Bolo Khana (बोलो खाना)

Voice-first dining companion for foreign tourists exploring regional **Malwani / Marathi** cuisine.

- **Scan Menu**: Upload a menu photo → Sarvam Vision extracts items → `rapidfuzz` matches the 30-dish Malwani KB; unmatched items are flagged `not in KB · unverified` and explained by `sarvam-105b`.
- **Hear & Practice Pronunciation**: Native Marathi TTS via **Bulbul v3** (`POST /tts`, cached on disk by hash) and interactive syllable-level pronunciation coach via **Saaras v3** (`translit` mode + Levenshtein scorer).
- **Deterministic Allergy & Diet Safety**: Pure `allergen_engine` (`SAFE` / `WARN` / `BLOCK`) with alias matching, hidden-allergen rules (`sol kadhi → coconut`), diet conflicts, and spice warnings. The LLM never decides safety.
- **Cultural Bridge**: Weighted Flavor-DNA similarity against 5 tourist origins (`Australia`, `UK`, `USA`, `Germany`, `Japan` × 8 dishes each) + grounded `sarvam-105b` comparison + optional **Mayura** translation + thumbs up/down feedback in `data/feedback.json`.
- **Waiter Mode**: Polite Marathi order drafting (`POST /order/draft`) + live Marathi-to-English waiter translation (`POST /order/listen` via Saaras `translate` mode).

## Run Steps

```bash
# 1. Install dependencies
.venv/bin/pip install -r requirements.txt

# 2. Configure environment (.env already holds SARVAM_API_KEY)
cp -n .env.example .env

# 3. Run in offline MOCK mode (zero network / zero keys needed)
MOCK_SARVAM=1 .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000

# 4. Run in REAL Sarvam mode (uses SARVAM_API_KEY from .env)
MOCK_SARVAM=0 .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000

# 5. Run test suite
MOCK_SARVAM=1 .venv/bin/pytest -q
```

## Example cURL Calls

```bash
# Health check
curl -s http://127.0.0.1:8000/health | jq

# Cultural bridge for Kombdi Vade -> Australia (returns 3 ranked matches with similar_in & different_in)
curl -s "http://127.0.0.1:8000/bridge/kombdi-vade?origin=Australia" | jq

# Deterministic peanut allergy BLOCK check via /dishes
curl -s "http://127.0.0.1:8000/dishes/shengdana-chutney?avoid_allergens=peanut" | jq '.safety'

# Pronounce dish (Bulbul TTS cached on disk)
curl -s -X POST http://127.0.0.1:8000/tts \
  -H "Content-Type: application/json" \
  -d '{"dish_id":"kombdi-vade","lang":"mr-IN"}' | jq 'del(.audio_base64)'

# Draft polite Marathi order
curl -s -X POST http://127.0.0.1:8000/order/draft \
  -H "Content-Type: application/json" \
  -d '{"items":[{"dish_id":"kombdi-vade","qty":1},{"dish_id":"sol-kadhi","qty":2}],"profile":{"max_spice":2,"diet":"nonveg","avoid_allergens":["peanut"],"origin":"Australia"}}' | jq 'del(.audio_base64)'
```
# sarvam
