from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from unidecode import unidecode
from typing import List

# Import the engine
from backend.game_logic import generate_valid_board, validate_guess, GAME_DATA

app = FastAPI(title="Geo-Matrix API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

COUNTRIES = GAME_DATA["countries"]
SEARCH_INDEX = [
    {"id": cca3, "name": data["name"], "normalized": unidecode(data["name"]).lower()}
    for cca3, data in COUNTRIES.items()
]

# --- Models ---
class GuessRequest(BaseModel):
    row_cat: str
    col_cat: str
    guess_cca3: str
    used_countries: List[str] = []  # NEW: Array of already played countries

class GuessResponse(BaseModel):
    correct: bool
    country_name: str
    flag_cca2: str
    message: str = "" # NEW: For "Already Used" warnings

# --- Endpoints ---
@app.get("/api/generate-board")
def get_board():
    try:
        # Our new hard-mode threshold is respected here from game_logic.py
        board = generate_valid_board(min_valid_answers=8)
        return {"status": "success", "board": board}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/search")
def search_countries(q: str = ""):
    if not q or len(q) < 1: return {"results": []}
    query = unidecode(q).lower()
    
    matches = [
        {"id": c["id"], "name": c["name"]}
        for c in SEARCH_INDEX
        if c["normalized"].startswith(query) or query in c["normalized"]
    ]
    return {"results": matches[:6]} # Show top 6

@app.post("/api/submit-guess", response_model=GuessResponse)
def submit_guess(payload: GuessRequest):
    if payload.guess_cca3 not in COUNTRIES:
        raise HTTPException(status_code=400, detail="Invalid Country ID")

    country_data = COUNTRIES[payload.guess_cca3]

    # Backend Security: Block if already used on the board
    if payload.guess_cca3 in payload.used_countries:
        return {
            "correct": False, 
            "country_name": country_data["name"], 
            "flag_cca2": country_data["cca2"],
            "message": "Already on board!"
        }

    is_correct = validate_guess(payload.row_cat, payload.col_cat, payload.guess_cca3)
    
    return {
        "correct": is_correct,
        "country_name": country_data["name"],
        "flag_cca2": country_data["cca2"],
        "message": "Correct!" if is_correct else "Incorrect match."
    }