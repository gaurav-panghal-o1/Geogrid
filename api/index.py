import os
import random
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from unidecode import unidecode
from typing import List
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

from api.game_logic import generate_valid_board, validate_guess, GAME_DATA, SETS

app = FastAPI(title="Geo-Matrix API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

try:
    groq_client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
except Exception:
    groq_client = None

COUNTRIES = GAME_DATA["countries"]
SEARCH_INDEX = [
    {"id": cca3, "name": data["name"], "normalized": unidecode(data["name"]).lower()}
    for cca3, data in COUNTRIES.items()
]

# NOTE: SESSION_HISTORY is in-memory only. In Vercel's serverless environment each
# invocation may run in a fresh process, so history does not persist across requests.
SESSION_HISTORY = []


# --- Models ---
class GuessRequest(BaseModel):
    row_cat: str
    col_cat: str
    guess_cca3: str
    used_countries: List[str] = []


class GuessResponse(BaseModel):
    correct: bool
    country_name: str
    flag_cca2: str
    message: str = ""
    rarity: str = "Common"


class HintRequest(BaseModel):
    row_cat: str
    col_cat: str


# --- Endpoints ---
@app.get("/api/generate-board")
def get_board():
    global SESSION_HISTORY
    try:
        board = generate_valid_board(history=SESSION_HISTORY, min_valid_answers=5, hard_threshold=8)
        SESSION_HISTORY.extend(board["rows"] + board["cols"])
        if len(SESSION_HISTORY) > 12:
            SESSION_HISTORY = SESSION_HISTORY[-12:]
        return {"status": "success", "board": board}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/search")
def search_countries(q: str = ""):
    if not q or len(q) < 1:
        return {"results": []}
    query = unidecode(q).lower()
    matches = [
        {"id": c["id"], "name": c["name"]}
        for c in SEARCH_INDEX
        if c["normalized"].startswith(query) or query in c["normalized"]
    ]
    return {"results": matches[:6]}


@app.post("/api/submit-guess", response_model=GuessResponse)
def submit_guess(payload: GuessRequest):
    if payload.guess_cca3 not in COUNTRIES:
        raise HTTPException(status_code=400, detail="Invalid Country ID")

    country_data = COUNTRIES[payload.guess_cca3]

    if payload.guess_cca3 in payload.used_countries:
        return {
            "correct": False,
            "country_name": country_data["name"],
            "flag_cca2": country_data["cca2"],
            "message": "Already on board!",
            "rarity": country_data.get("rarity", "Common"),
        }

    is_correct = validate_guess(payload.row_cat, payload.col_cat, payload.guess_cca3)
    return {
        "correct": is_correct,
        "country_name": country_data["name"],
        "flag_cca2": country_data["cca2"],
        "message": "Correct!" if is_correct else "Incorrect match.",
        "rarity": country_data.get("rarity", "Common"),
    }


@app.post("/api/hint")
def get_hint(payload: HintRequest):
    if not groq_client:
        raise HTTPException(status_code=500, detail="Groq API Key not configured on server.")

    valid_set = SETS.get(payload.row_cat, set()).intersection(SETS.get(payload.col_cat, set()))
    if not valid_set:
        return {"hint": "No valid countries found for this combination."}

    target_cca3 = random.choice(list(valid_set))
    country_name = COUNTRIES[target_cca3]["name"]

    prompt = f"""
    You are a clever trivia game hint generator. 
    The user needs to guess a country that fits BOTH of these categories: '{payload.row_cat}' AND '{payload.col_cat}'.
    A valid answer they could guess is: {country_name}.

    Write a fun, engaging 1-to-2 sentence trivia hint about {country_name} that helps them guess it. 
    CRITICAL RULE: You MUST NOT say the words "{country_name}" in your response. Replace the name with "This country".
    Do not use markdown. Just provide the raw text.
    """

    try:
        chat_completion = groq_client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="llama-3.1-8b-instant",
            temperature=0.7,
            max_tokens=100,
        )
        return {"hint": chat_completion.choices[0].message.content.strip()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
