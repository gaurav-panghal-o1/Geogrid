# """Game logic for country set intersections."""
# import orjson
# import random
# from itertools import combinations
# import os

# # --- 1. Load the Offline Database ---
# # We load this ONCE into memory when the server starts.
# DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "processed", "master_countries.json")

# with open(DB_PATH, "rb") as f:
#     GAME_DATA = orjson.loads(f.read())

# SETS = {k: set(v) for k, v in GAME_DATA["sets"].items()}
# COMPAT = GAME_DATA["_compat"]
# CATEGORIES = list(SETS.keys())

# # --- 2. Mutual Exclusion Manifest ---
# # Hardcoded rules to prevent the generator from trying impossible combinations
# MUTUAL_EXCLUSIONS = set([
#     frozenset({"Is Landlocked", "Continent: Oceania"}),
#     frozenset({"Pop Under 1M", "Pop Over 50M"}),
#     frozenset({"Is Microstate", "Pop Over 50M"})
# ])

# # Dynamically add exclusions so two Continents are never placed on the same axis 
# # (e.g. Row 1: Africa, Row 2: Europe is fine, but checking "Africa AND Europe" is impossible)
# continents = [c for c in CATEGORIES if "Continent" in c]
# for c1, c2 in combinations(continents, 2):
#     MUTUAL_EXCLUSIONS.add(frozenset({c1, c2}))

# # --- 3. Engine Helpers ---
# def get_overlap_count(c1, c2):
#     """O(1) lookup for how many countries match both criteria."""
#     key = f"{c1}|{c2}" if c1 < c2 else f"{c2}|{c1}"
#     return COMPAT.get(key, 0)

# def is_mutually_exclusive(candidate, chosen_list):
#     """Checks if a category contradicts anything already chosen."""
#     for chosen in chosen_list:
#         if frozenset({candidate, chosen}) in MUTUAL_EXCLUSIONS:
#             return True
#     return False

# # --- 4. The Core Generator (Tier 1 Greedy Algorithm) ---
# def generate_valid_board(min_valid_answers=3, max_attempts=100):
#     """
#     Generates 3 rows and 3 columns where EVERY intersection has 
#     at least `min_valid_answers` valid countries.
#     """
#     for _ in range(max_attempts):
#         rows = []
#         cols = []
#         available = CATEGORIES.copy()
#         random.shuffle(available)

#         # 1. Pick 3 Row Criteria
#         for cat in available:
#             if len(rows) < 3 and not is_mutually_exclusive(cat, rows):
#                 rows.append(cat)
        
#         if len(rows) < 3:
#             continue # Try again if we couldn't find 3 valid rows

#         # 2. Pick 3 Column Criteria
#         for cat in available:
#             # Skip if it's already a row, or conflicts with other columns
#             if cat in rows or is_mutually_exclusive(cat, cols):
#                 continue
            
#             # CRITICAL: Check overlap with ALL 3 currently selected rows
#             is_valid_column = True
#             for r in rows:
#                 if get_overlap_count(r, cat) < min_valid_answers:
#                     is_valid_column = False
#                     break
            
#             if is_valid_column:
#                 cols.append(cat)
                
#             if len(cols) == 3:
#                 break # We found our 3 columns!

#         # 3. Success Check
#         if len(rows) == 3 and len(cols) == 3:
#             return {
#                 "rows": rows,
#                 "cols": cols
#             }

#     # If we hit max_attempts (rare with the matrix), raise an error
#     raise Exception("Failed to generate a valid board. Try lowering min_valid_answers or adding more categories.")

# def validate_guess(row_cat, col_cat, guess_cca3):
#     """Checks if a user's guess exists in both the row and column sets."""
#     return guess_cca3 in SETS[row_cat] and guess_cca3 in SETS[col_cat]

# # --- Quick Test Execution ---
# if __name__ == "__main__":
#     print("Testing Board Generation (Minimum 3 answers per cell)...")
#     board = generate_valid_board(min_valid_answers=3)
    
#     print("\nROWS:", board["rows"])
#     print("COLS:", board["cols"])
    
#     print("\nIntersection Verification:")
#     for r in board["rows"]:
#         for c in board["cols"]:
#             overlap = get_overlap_count(r, c)
#             print(f"  [{r}] x [{c}] -> {overlap} valid countries")

# import orjson
# import random
# from itertools import combinations
# import os

# # --- 1. Load the Offline Database ---
# DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "processed", "master_countries.json")

# with open(DB_PATH, "rb") as f:
#     GAME_DATA = orjson.loads(f.read())

# SETS = {k: set(v) for k, v in GAME_DATA["sets"].items()}
# COMPAT = GAME_DATA["_compat"]
# CATEGORIES = list(SETS.keys())

# # --- 2. Engine Helpers ---
# def get_overlap_count(c1, c2):
#     """O(1) lookup for how many countries match both criteria."""
#     if c1 == c2: return len(SETS[c1])
#     key = f"{c1}|{c2}" if c1 < c2 else f"{c2}|{c1}"
#     return COMPAT.get(key, 0)

# # --- 3. The Core Generator (Auto-Exclusion Algorithm) ---
# def generate_valid_board(min_valid_answers=8, max_attempts=500):
#     """
#     Generates 3 rows and 3 columns where EVERY intersection has 
#     at least `min_valid_answers` valid countries.
#     Automatically prevents impossible combinations (e.g., 'Starts with A' and 'Starts with B') 
#     because their overlap count will naturally be 0.
#     """
#     for _ in range(max_attempts):
#         rows = []
#         cols = []
#         available = CATEGORIES.copy()
#         random.shuffle(available)

#         # 1. Pick 3 Unique Row Criteria
#         for cat in available:
#             if len(rows) < 3 and cat not in rows:
#                 rows.append(cat)
        
#         if len(rows) < 3: continue

#         # 2. Pick 3 Column Criteria with Auto-Exclusion
#         for cat in available:
#             if cat in rows or cat in cols: continue
            
#             # THE SMART VALIDATOR: 
#             # Check overlap against ALL 3 currently selected rows
#             is_valid_column = True
#             for r in rows:
#                 if get_overlap_count(r, cat) < min_valid_answers:
#                     is_valid_column = False
#                     break
            
#             if is_valid_column:
#                 cols.append(cat)
                
#             if len(cols) == 3: break

#         # 3. Success Check
#         if len(rows) == 3 and len(cols) == 3:
#             return {"rows": rows, "cols": cols}

#     raise Exception(f"Failed to generate board after {max_attempts} attempts. Try lowering min_valid_answers.")

# def validate_guess(row_cat, col_cat, guess_cca3):
#     return guess_cca3 in SETS[row_cat] and guess_cca3 in SETS[col_cat]

# if __name__ == "__main__":
#     print("Testing Smart Auto-Exclusion Generator...")
#     board = generate_valid_board()
#     print("\nROWS:", board["rows"])
#     print("COLS:", board["cols"])

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