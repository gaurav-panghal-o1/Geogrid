import orjson
import random
import os

# --- 1. Load the Offline Database ---
DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "processed", "master_countries.json")

with open(DB_PATH, "rb") as f:
    GAME_DATA = orjson.loads(f.read())

SETS = {k: set(v) for k, v in GAME_DATA["sets"].items()}
COMPAT = GAME_DATA["_compat"]
GROUPS = GAME_DATA.get("_groups", {})  # Dynamically loaded grouping assignments
CATEGORIES = list(SETS.keys())

# --- 2. Engine Helpers ---
def get_overlap_count(c1, c2):
    """O(1) lookup for how many countries match both criteria."""
    if c1 == c2: return len(SETS[c1])
    key = f"{c1}|{c2}" if c1 < c2 else f"{c2}|{c1}"
    return COMPAT.get(key, 0)

# --- 3. The Core Group-Aware Generator ---
def generate_valid_board(history=None, min_valid_answers=5, hard_threshold=8, max_attempts=2500):
    """
    Generates 3 rows and 3 columns checking:
    1. 2-Session Cooldown (via history array)
    2. Strict Semantic Group uniqueness (No two HDI or Colonial clues on same board)
    3. Minimum answers per cell (e.g. 5)
    4. At least one "Hard" cell per board (<= 8 valid answers)
    """
    if history is None:
        history = []

    for _ in range(max_attempts):
        rows = []
        cols = []
        used_groups = set()
        
        # Shuffle everything, remove items recently played (2 session cooldown)
        available = [c for c in CATEGORIES if c not in history]
        random.shuffle(available)

        # 1. Pick 3 Unique Row Criteria avoiding identical semantic groups
        for cat in available:
            cat_group = GROUPS.get(cat, "Misc")
            if cat_group not in used_groups:
                rows.append(cat)
                used_groups.add(cat_group)
            if len(rows) == 3: break
        
        if len(rows) < 3: continue

        # 2. Pick 3 Column Criteria with Group Auto-Exclusion & Overlap Verification
        for cat in available:
            if cat in rows: continue
            cat_group = GROUPS.get(cat, "Misc")
            
            # If the group is unused, test its overlap math
            if cat_group not in used_groups:
                # Every row intersection must have at least `min_valid_answers`
                if all(get_overlap_count(r, cat) >= min_valid_answers for r in rows):
                    cols.append(cat)
                    used_groups.add(cat_group)
            
            if len(cols) == 3: break

        # 3. Success & Difficulty Check
        if len(rows) == 3 and len(cols) == 3:
            # Enforce at least one cell out of 9 is hard to guess
            has_hard_cell = False
            for r in rows:
                for c in cols:
                    if get_overlap_count(r, c) <= hard_threshold:
                        has_hard_cell = True
                        break
                if has_hard_cell: break
            
            if has_hard_cell:
                return {"rows": rows, "cols": cols}

    raise Exception(f"Failed to generate valid group-strict board after {max_attempts} attempts.")

def validate_guess(row_cat, col_cat, guess_cca3):
    return guess_cca3 in SETS[row_cat] and guess_cca3 in SETS[col_cat]

if __name__ == "__main__":
    print("Testing Smart Category Group Generator...")
    board = generate_valid_board()
    print("\nROWS:", board["rows"])
    print("COLS:", board["cols"])