# import httpx
# import pandas as pd
# import orjson
# import itertools
# from datetime import datetime
# import os
# import re
# import time

# # --- 1. World Bank API Extraction ---
# def fetch_world_bank_indicator(indicator_code, col_name):
#     """Fetches WB data with pagination, timeouts, and polite retry logic."""
#     print(f"Fetching World Bank: {col_name}...")
    
#     all_data = []
#     page = 1
#     max_retries = 3
    
#     # Increased timeout to 60 seconds for slow WB servers
#     with httpx.Client(timeout=httpx.Timeout(60.0)) as client:
#         while True:
#             url = f"https://api.worldbank.org/v2/country/all/indicator/{indicator_code}?format=json&per_page=5000&page={page}"
            
#             # --- RETRY SAFETY NET ---
#             for attempt in range(max_retries):
#                 try:
#                     response = client.get(url)
#                     response.raise_for_status()
#                     json_resp = response.json()
#                     break # Success! Break out of the retry loop.
#                 except (httpx.ReadTimeout, httpx.ConnectTimeout, httpx.HTTPError) as e:
#                     print(f"  ⚠️ Timeout on page {page} (Attempt {attempt + 1}/{max_retries}). Retrying in 5s...")
#                     time.sleep(5) # Give the WB server 5 seconds to breathe
#             else:
#                 # This triggers if the loop finishes without a 'break' (all retries failed)
#                 print(f"  ❌ Failed to fetch {col_name} after {max_retries} attempts. Skipping metric.")
#                 return pd.DataFrame(columns=['cca3', col_name])
#             # ------------------------
            
#             # Catch API errors (e.g., if WB returns an error message instead of data)
#             if isinstance(json_resp, list) and len(json_resp) == 1 and "message" in json_resp[0]:
#                 print(f"  ⚠️ API Error for {indicator_code}: {json_resp[0]['message']}")
#                 break
                
#             # Break if no data is found
#             if len(json_resp) < 2 or json_resp[1] is None:
#                 break
                
#             metadata = json_resp[0]
#             page_data = json_resp[1]
#             all_data.extend(page_data)
            
#             if page >= metadata.get("pages", 1):
#                 break
            
#             page += 1
#             time.sleep(0.5) # Polite delay between normal requests
            
#     # If a dataset completely fails, return an empty placeholder
#     if not all_data:
#         print(f"  ⚠️ Warning: No data retrieved for {col_name}. Skipping this metric.")
#         return pd.DataFrame(columns=['cca3', col_name])
        
#     df = pd.DataFrame(all_data)
#     df = df.dropna(subset=['value'])
#     df = df[df['countryiso3code'] != '']
    
#     # SORTING MAGIC: Get the latest non-null value per country
#     df = df.sort_values("date").groupby("countryiso3code").tail(1)
    
#     return df[['countryiso3code', 'value']].rename(columns={'countryiso3code': 'cca3', 'value': col_name})

# def build_game_database():
#     # --- 2. Base API Extraction (REST Countries) ---
#     print("Fetching Base Data from REST Countries...")
#     base_url = "https://restcountries.com/v3.1/all?fields=name,cca2,cca3,independent,population,area,region,landlocked,borders,car"
#     with httpx.Client(headers={"User-Agent": "Mozilla/5.0"}, follow_redirects=True) as client:
#         rest_data = client.get(base_url).json()
    
#     countries_list = []
#     rest_name_map = {} # Helper map for later
#     for c in rest_data:
#         if c.get("independent") is False: continue
#         cca3 = c.get("cca3")
#         name = c.get("name", {}).get("common", "Unknown")
#         rest_name_map[name.lower()] = cca3
        
#         countries_list.append({
#             "cca3":           cca3,
#             "name":           name,
#             "cca2":           c.get("cca2", "").lower(),
#             "continent":      c.get("region", "Unknown"),
#             "is_landlocked":  c.get("landlocked", False),
#             "drives_left":    c.get("car", {}).get("side") == "left",
#             "borders_5_plus": len(c.get("borders", [])) >= 5,
#             # NEW: area is already in the API call, capture it here
#             "area_km2":       c.get("area", 0) or 0,
#         })
#     df_base = pd.DataFrame(countries_list)

#     # --- 3. World Bank Extraction ---
#     # Original indicators
#     df_gdp      = fetch_world_bank_indicator("NY.GDP.PCAP.CD", "gdp_per_capita")
#     df_life     = fetch_world_bank_indicator("SP.DYN.LE00.IN", "life_expectancy")
#     df_pop_dens = fetch_world_bank_indicator("EN.POP.DNST",    "pop_density")

#     # NEW indicators
#     df_literacy  = fetch_world_bank_indicator("SE.ADT.LITR.ZS", "literacy_rate")
#     df_gini      = fetch_world_bank_indicator("SI.POV.GINI",     "gini_index")
#     df_co2       = fetch_world_bank_indicator("EN.ATM.CO2E.PC",  "co2_per_capita")
#     df_electric  = fetch_world_bank_indicator("EG.ELC.ACCS.ZS",  "electricity_access")

#     # --- 4. Local Kaggle Data Extraction & Cleaning ---
#     print("Processing Local Kaggle CSVs/Excel...")
#     base_path = os.path.join(os.path.dirname(__file__), "..", "data", "raw")
    
#     # 4a. LatLong (Our Translation Dictionary)
#     df_latlong = pd.read_csv(os.path.join(base_path, "latlong.csv"))
#     name_to_cca3 = dict(zip(df_latlong['Country'].str.strip().str.lower(), df_latlong['ISO-ALPHA-3'].str.strip()))
#     ioc_to_cca3  = dict(zip(df_latlong['IOC'].str.strip(), df_latlong['ISO-ALPHA-3'].str.strip()))
#     # Combine latlong mapping with REST mapping for maximum match rate
#     master_name_map = {**name_to_cca3, **rest_name_map}

#     # 4b. Olympics
#     # NEW: also pull participation columns for "Competed in 20+ Olympics" criteria
#     df_olympic = pd.read_csv(os.path.join(base_path, "olympic.csv"))
#     df_olympic['clean_ioc'] = df_olympic['ioc_code '].astype(str).str.replace(r'[\(\)]', '', regex=True).str.strip()
#     df_olympic['cca3'] = df_olympic['clean_ioc'].map(ioc_to_cca3)
#     df_olympic = df_olympic.rename(columns={
#         'summer_total':          'summer_medals',
#         'winter_total':          'winter_medals',
#         'summer_participations': 'summer_participations',
#         'winter_participations': 'winter_participations',
#     })
#     # Numeric-clean participation counts (may have comma-separated strings)
#     df_olympic['summer_participations'] = pd.to_numeric(
#         df_olympic['summer_participations'].astype(str).str.replace(',', ''), errors='coerce'
#     ).fillna(0)
#     df_olympic['winter_participations'] = pd.to_numeric(
#         df_olympic['winter_participations'].astype(str).str.replace(',', ''), errors='coerce'
#     ).fillna(0)

#     # 4c. Elevation
#     df_elevation = pd.read_csv(os.path.join(base_path, "elevation.csv"))
#     df_elevation['elevation_m'] = df_elevation['Elevation'].str.extract(r'([-\d]+)\s*m')[0].astype(float)
#     df_elevation['cca3'] = df_elevation['Country'].str.strip().str.lower().map(master_name_map)

#     # 4d. UN Data — Sheet 0: HDI (original)
#     df_un = pd.read_excel(os.path.join(base_path, "undata.xlsx"), sheet_name=0, skiprows=4)
#     df_un = df_un.rename(columns={'Unnamed: 1': 'Country', 'Human Development Index (HDI) ': 'hdi'})
#     df_un['cca3'] = df_un['Country'].astype(str).str.strip().str.lower().map(master_name_map)

#     # 4e. UN Data — Sheet 4: Gender Inequality Index (NEW)
#     # Sheet index 4 = Table 5 (Gender Inequality Index)
#     df_gii = pd.read_excel(os.path.join(base_path, "undata.xlsx"), sheet_name=4, skiprows=4)
    
#     # FIX: Rename using exact column indices (B=1, C=2, K=10) instead of fragile string names 
#     # to completely bypass the UN's messy merged Excel headers.
#     df_gii = df_gii.rename(columns={
#         df_gii.columns[1]: 'Country',
#         df_gii.columns[2]: 'gii_value',
#         df_gii.columns[10]: 'women_in_parliament_pct',
#     })
    
#     df_gii['gii_value']              = pd.to_numeric(df_gii['gii_value'],              errors='coerce')
#     df_gii['women_in_parliament_pct']= pd.to_numeric(df_gii['women_in_parliament_pct'],errors='coerce')
#     df_gii['cca3'] = df_gii['Country'].astype(str).str.strip().str.lower().map(master_name_map)
    
#     # --- 5. The Master Merge ---
#     print("Executing Master Merge...")
#     df_master = df_base\
#         .merge(df_gdp,      on='cca3', how='left')\
#         .merge(df_life,     on='cca3', how='left')\
#         .merge(df_pop_dens, on='cca3', how='left')\
#         .merge(df_literacy, on='cca3', how='left')\
#         .merge(df_gini,     on='cca3', how='left')\
#         .merge(df_co2,      on='cca3', how='left')\
#         .merge(df_electric, on='cca3', how='left')\
#         .merge(
#             df_olympic[['cca3', 'summer_medals', 'winter_medals',
#                         'summer_participations', 'winter_participations']],
#             on='cca3', how='left'
#         )\
#         .merge(df_elevation[['cca3', 'elevation_m']], on='cca3', how='left')\
#         .merge(df_un[['cca3', 'hdi']],                on='cca3', how='left')\
#         .merge(df_gii[['cca3', 'gii_value', 'women_in_parliament_pct']], on='cca3', how='left')\
#         .merge(
#             df_latlong[['ISO-ALPHA-3', 'Latitude', 'Longitude']],
#             left_on='cca3', right_on='ISO-ALPHA-3', how='left'
#         )

#     # Numeric-safe medal columns (Kaggle strings with commas)
#     df_master['summer_medals'] = pd.to_numeric(
#         df_master['summer_medals'].astype(str).str.replace(',', ''), errors='coerce'
#     ).fillna(0)
#     df_master['winter_medals'] = pd.to_numeric(
#         df_master['winter_medals'].astype(str).str.replace(',', ''), errors='coerce'
#     ).fillna(0)

#     df_master = df_master.drop_duplicates(subset=['cca3'])

#     # --- 6. Derived Feature Engineering ---
#     print("Generating Gameplay Criteria...")

#     # Force all continuous columns to numeric (handles UN's ".." placeholders etc.)
#     numeric_cols = [
#         'hdi', 'gdp_per_capita', 'life_expectancy', 'pop_density',
#         'literacy_rate', 'gini_index', 'co2_per_capita', 'electricity_access',
#         'gii_value', 'women_in_parliament_pct', 'area_km2',
#         'elevation_m', 'Latitude', 'Longitude',
#         'summer_participations', 'winter_participations',
#     ]
#     for col in numeric_cols:
#         df_master[col] = pd.to_numeric(df_master[col], errors='coerce')

#     # ── ORIGINAL CRITERIA ─────────────────────────────────────────────────────
#     # Economic / Social
#     df_master['HDI > 0.80']              = df_master['hdi'] > 0.80
#     df_master['GDP Per Capita > $25k']   = df_master['gdp_per_capita'] > 25000
#     df_master['Life Expectancy > 75']    = df_master['life_expectancy'] > 75

#     # Geographic / Physical
#     df_master['Pop Density > 200/km²']   = df_master['pop_density'] > 200
#     df_master['Elevation > 2,000m']      = df_master['elevation_m'] > 2000
#     df_master['Elevation < 50m']         = df_master['elevation_m'] < 50
#     df_master['Northern Hemisphere']     = df_master['Latitude'] > 0
#     df_master['Southern Hemisphere']     = df_master['Latitude'] < 0

#     # Sports
#     df_master['Has Winter Olympic Medal']   = df_master['winter_medals'] > 0
#     df_master['50+ Summer Olympic Medals']  = df_master['summer_medals'] >= 50

#     # ── NEW CRITERIA ──────────────────────────────────────────────────────────

#     # Economic / Development
#     df_master['Literacy Rate > 95%']            = df_master['literacy_rate'] > 95
#     df_master['Low Inequality (Gini < 35)']     = df_master['gini_index'] < 35
#     df_master['High Inequality (Gini > 45)']    = df_master['gini_index'] > 45
#     df_master['High CO2 Emitter (> 8t/cap)']    = df_master['co2_per_capita'] > 8
#     df_master['Near-Full Electricity Access']   = df_master['electricity_access'] > 99

#     # Gender / Social
#     # GII ranges 0 (perfect equality) → 1 (maximum inequality)
#     df_master['High Gender Equality (GII < 0.10)'] = df_master['gii_value'] < 0.10
#     df_master['30%+ Women in Parliament']          = df_master['women_in_parliament_pct'] >= 30

#     # Geographic: Hemispheres & Zones
#     # Tropics = latitudes between the Tropic of Cancer and Tropic of Capricorn
#     df_master['In the Tropics']     = df_master['Latitude'].between(-23.5, 23.5)
#     df_master['Eastern Hemisphere'] = df_master['Longitude'] > 0
#     df_master['Western Hemisphere'] = df_master['Longitude'] < 0

#     # Geographic: Area
#     df_master['Large Country (> 1M km²)'] = df_master['area_km2'] > 1_000_000
#     df_master['Tiny Country (< 5k km²)']  = df_master['area_km2'] < 5_000

#     # Sports: Participation depth
#     df_master['Competed in 20+ Summer Olympics']  = df_master['summer_participations'] >= 20
#     df_master['Has Winter Olympic Participation'] = df_master['winter_participations'] > 0

#     # --- 7. Build Category Sets & Compat Matrix ---
#     print("Building category sets & Matrix...")
#     categories = {}

#     # Pick up all boolean columns that were derived above
#     bool_cols = [col for col in df_master.columns if df_master[col].dtype == bool]
#     for col in bool_cols:
#         # Skip the raw REST Countries internal booleans (they have ugly names)
#         if col not in ['is_landlocked', 'drives_left', 'borders_5_plus']:
#             categories[col] = set(df_master[df_master[col] == True]["cca3"].tolist())

#     # Re-add REST Countries booleans with clean display names
#     categories["Is Landlocked"]       = set(df_master[df_master['is_landlocked']   == True]["cca3"].tolist())
#     categories["Drives on Left"]      = set(df_master[df_master['drives_left']      == True]["cca3"].tolist())
#     categories["Borders 5+ Countries"]= set(df_master[df_master['borders_5_plus']  == True]["cca3"].tolist())

#     # Continents (dynamic — one category per unique continent value)
#     for continent in df_master["continent"].unique():
#         if pd.notna(continent) and continent != "Unknown":
#             categories[f"Continent: {continent}"] = set(
#                 df_master[df_master["continent"] == continent]["cca3"].tolist()
#             )

#     # Pre-compute pairwise overlap counts → O(1) lookup at runtime
#     compat_matrix = {}
#     for c1, c2 in itertools.combinations(categories.keys(), 2):
#         overlap_count = len(categories[c1] & categories[c2])
#         key = f"{c1}|{c2}" if c1 < c2 else f"{c2}|{c1}"
#         compat_matrix[key] = overlap_count

#     # --- 8. Save ---
#     serializable_categories = {k: list(v) for k, v in categories.items() if len(v) > 0}
#     final_payload = {
#         "_meta": {
#             "built_at":          datetime.now().isoformat(),
#             "total_countries":   len(df_master),
#             "total_categories":  len(serializable_categories),
#         },
#         "countries": df_master.set_index("cca3")[["name", "cca2"]].to_dict(orient="index"),
#         "sets":      serializable_categories,
#         "_compat":   compat_matrix,
#     }

#     with open("data/processed/master_countries.json", "wb") as f:
#         f.write(orjson.dumps(final_payload, option=orjson.OPT_INDENT_2))

#     print(f"✓ Success! Pro Database built with {len(serializable_categories)} categories.")

# if __name__ == "__main__":
#     build_game_database()

import httpx
import pandas as pd
import orjson
import itertools
from datetime import datetime
import os
import time

def fetch_world_bank_indicator(indicator_code, col_name):
    print(f"Fetching World Bank: {col_name}...")
    all_data = []
    page = 1
    max_retries = 3
    
    with httpx.Client(timeout=httpx.Timeout(60.0)) as client:
        while True:
            url = f"https://api.worldbank.org/v2/country/all/indicator/{indicator_code}?format=json&per_page=5000&page={page}"
            for attempt in range(max_retries):
                try:
                    response = client.get(url)
                    response.raise_for_status()
                    json_resp = response.json()
                    break 
                except (httpx.ReadTimeout, httpx.ConnectTimeout, httpx.HTTPError) as e:
                    print(f"  ⚠️ Timeout on page {page}. Retrying...")
                    time.sleep(5) 
            else:
                return pd.DataFrame(columns=['cca3', col_name])
            
            if isinstance(json_resp, list) and len(json_resp) == 1 and "message" in json_resp[0]:
                print(f"  ⚠️ API Error for {indicator_code}: {json_resp[0]['message']}")
                break
            if len(json_resp) < 2 or json_resp[1] is None: break
                
            metadata = json_resp[0]
            all_data.extend(json_resp[1])
            if page >= metadata.get("pages", 1): break
            page += 1
            time.sleep(0.5)
            
    if not all_data: return pd.DataFrame(columns=['cca3', col_name])
        
    df = pd.DataFrame(all_data).dropna(subset=['value'])
    df = df[df['countryiso3code'] != '']
    df = df.sort_values("date").groupby("countryiso3code").tail(1)
    return df[['countryiso3code', 'value']].rename(columns={'countryiso3code': 'cca3', 'value': col_name})

def build_game_database():
    # --- 2. Base API Extraction (Territories Unlocked!) ---
    print("Fetching Base Data from REST Countries...")
    base_url = "https://restcountries.com/v3.1/all?fields=name,cca2,cca3,independent,population,area,region,landlocked,borders,car"
    with httpx.Client(headers={"User-Agent": "Mozilla/5.0"}, follow_redirects=True) as client:
        rest_data = client.get(base_url).json()
    
    countries_list = []
    rest_name_map = {}
    for c in rest_data:
        # TERRITORIES UNLOCKED: We removed the 'if independent is False: continue' check!
        cca3 = c.get("cca3")
        name = c.get("name", {}).get("common", "Unknown")
        rest_name_map[name.lower()] = cca3
        
        borders = c.get("borders", [])
        countries_list.append({
            "cca3": cca3,
            "name": name,
            "cca2": c.get("cca2", "").lower(),
            "continent": c.get("region", "Unknown"),
            "is_landlocked": c.get("landlocked", False),
            "drives_left": c.get("car", {}).get("side") == "left",
            "borders_count": len(borders),
            "borders_rus": "RUS" in borders,
            "borders_chn": "CHN" in borders,
            "borders_bra": "BRA" in borders,
            "borders_fra": "FRA" in borders,
            "area_km2": c.get("area", 0) or 0,
        })
    df_base = pd.DataFrame(countries_list)

    # --- 3. World Bank Extraction ---
    df_gdp = fetch_world_bank_indicator("NY.GDP.PCAP.CD", "gdp_per_capita")
    df_life = fetch_world_bank_indicator("SP.DYN.LE00.IN", "life_expectancy")
    df_pop_dens = fetch_world_bank_indicator("EN.POP.DNST", "pop_density")

    # --- 4. Local Kaggle Data Extraction ---
    print("Processing Local Datasets...")
    base_path = os.path.join(os.path.dirname(__file__), "..", "data", "raw")
    
    # LatLong Mapping
    df_latlong = pd.read_csv(os.path.join(base_path, "latlong.csv"))
    master_name_map = {**dict(zip(df_latlong['Country'].str.strip().str.lower(), df_latlong['ISO-ALPHA-3'].str.strip())), **rest_name_map}

    # Flags
    try:
        df_flags = pd.read_csv(os.path.join(base_path, "world_flags_2024.csv"))
        df_flags['cca3'] = df_flags['Country'].str.strip().str.lower().map(master_name_map)
    except: df_flags = pd.DataFrame(columns=['cca3'])

    # Coastline
    try:
        df_coast = pd.read_csv(os.path.join(base_path, "countries-by-coastline-2026.csv"))
        df_coast['cca3'] = df_coast['country'].str.strip().str.lower().map(master_name_map)
    except: df_coast = pd.DataFrame(columns=['cca3'])

    # FIFA Participate
    try:
        df_fifa_p = pd.read_csv(os.path.join(base_path, "fifa_participate.csv"), on_bad_lines='skip')
        df_fifa_p['cca3'] = df_fifa_p['FIFA_Code'] # Usually 1:1 with CCA3
    except: df_fifa_p = pd.DataFrame(columns=['cca3'])

    # FIFA Host/Winner
    try:
        df_fifa_hw = pd.read_csv(os.path.join(base_path, "fifawchostwinner.xlsx - Sheet1.csv"))
    except: df_fifa_hw = pd.DataFrame()

    # Chocolate
    try:
        df_choc = pd.read_csv(os.path.join(base_path, "cf1.csv"))
        df_choc['is_top_chocolate'] = True
    except: df_choc = pd.DataFrame(columns=['cca3'])

    # UN HDI
    df_un = pd.read_excel(os.path.join(base_path, "undata.xlsx"), sheet_name=0, skiprows=4)
    df_un = df_un.rename(columns={'Unnamed: 1': 'Country', 'Human Development Index (HDI) ': 'hdi'})
    df_un['cca3'] = df_un['Country'].astype(str).str.strip().str.lower().map(master_name_map)

    # --- 5. The Master Merge ---
    print("Executing Master Merge...")
    df_master = df_base\
        .merge(df_gdp, on='cca3', how='left')\
        .merge(df_life, on='cca3', how='left')\
        .merge(df_pop_dens, on='cca3', how='left')\
        .merge(df_un[['cca3', 'hdi']], on='cca3', how='left')\
        .merge(df_latlong[['ISO-ALPHA-3', 'Latitude', 'Longitude']], left_on='cca3', right_on='ISO-ALPHA-3', how='left')

    if not df_flags.empty: df_master = df_master.merge(df_flags[['cca3', 'White', 'Red', 'Blue', 'Black', 'Yellow', 'Green', 'Orange', 'Stars', 'Sun', 'Cross', 'Crescent', 'BlazonOrOther']], on='cca3', how='left')
    if not df_coast.empty: df_master = df_master.merge(df_coast[['cca3', 'CountryCoastlineKm']], on='cca3', how='left')
    if not df_fifa_p.empty: df_master = df_master.merge(df_fifa_p[['cca3', 'Total_Appearances', 'in_2022', 'in_2014', 'in_1930']], on='cca3', how='left')
    if not df_choc.empty: df_master = df_master.merge(df_choc[['cca3', 'is_top_chocolate']], on='cca3', how='left')

    df_master = df_master.drop_duplicates(subset=['cca3'])
    df_master = df_master.copy()

    # --- 6. Derived Feature Engineering (The v4.0.1 Criteria Logic) ---
    print("Generating v4.0.1 Granular Criteria...")
    
    # A. Name Constraints
    name_upper = df_master['name'].astype(str).str.upper()
    df_master['Name is 4 letters'] = name_upper.str.len() == 4
    df_master['Name is 5 letters'] = name_upper.str.len() == 5
    df_master['Name is 6 letters'] = name_upper.str.len() == 6
    df_master['Name is 7 letters'] = name_upper.str.len() == 7
    df_master['Name is 8 letters'] = name_upper.str.len() == 8
    df_master['Name 10+ letters'] = name_upper.str.len() >= 10
    df_master['Multiple words'] = name_upper.str.contains(' ')
    df_master['Same first & last letter'] = name_upper.str[0] == name_upper.str[-1]

    for letter in "ABCDEGHIKLMNPSTU": df_master[f'Starts with {letter}'] = name_upper.str.startswith(letter)
    for letter in "ACDEILNORSY": df_master[f'Ends with {letter}'] = name_upper.str.endswith(letter)

    # B. Borders Constraints
    df_master['Borders 1–2 countries'] = df_master['borders_count'].between(1, 2)
    df_master['Borders 3–4 countries'] = df_master['borders_count'].between(3, 4)
    df_master['Borders 5+ countries'] = df_master['borders_count'] >= 5
    df_master['Borders Russia'] = df_master['borders_rus']
    df_master['Borders China'] = df_master['borders_chn']
    df_master['Borders Brazil'] = df_master['borders_bra']
    df_master['Borders France'] = df_master['borders_fra']

    # C. Numeric Bucketing (HDI, GDP, Coastline)
    df_master['hdi'] = pd.to_numeric(df_master['hdi'], errors='coerce')
    for hdi_val in [0.4, 0.5, 0.6, 0.7, 0.8, 0.9]:
        df_master[f'HDI ≥ {hdi_val}'] = df_master['hdi'] >= hdi_val
        df_master[f'HDI < {hdi_val}'] = df_master['hdi'] < hdi_val

    df_master['gdp_per_capita'] = pd.to_numeric(df_master['gdp_per_capita'], errors='coerce')
    for gdp_val in [5000, 10000, 20000, 50000, 100000]:
        val_str = f"${gdp_val//1000}K"
        df_master[f'GDP/cap ≥ {val_str}'] = df_master['gdp_per_capita'] >= gdp_val
        df_master[f'GDP/cap < {val_str}'] = df_master['gdp_per_capita'] < gdp_val

    if 'CountryCoastlineKm' in df_master.columns:
        df_master['coast'] = pd.to_numeric(df_master['CountryCoastlineKm'], errors='coerce').fillna(0)
        df_master['Coastline ≥ 100 km'] = df_master['coast'] >= 100
        df_master['Coastline ≥ 1K km'] = df_master['coast'] >= 1000
        df_master['Coastline ≥ 10K km'] = df_master['coast'] >= 10000
        df_master['Coastline < 100 km'] = df_master['coast'] < 100

    # D. Flags & Geography
    if 'Red' in df_master.columns:
        df_master['Red on flag'] = df_master['Red'] == 1
        df_master['Blue on flag'] = df_master['Blue'] == 1
        df_master['Green on flag'] = df_master['Green'] == 1
        df_master['Black on flag'] = df_master['Black'] == 1
        df_master['Star on flag'] = df_master['Stars'] == 1
        df_master['Coat of arms on flag'] = df_master['BlazonOrOther'] == 1

    df_master['Northern Hemisphere'] = df_master['Latitude'] > 0
    df_master['Southern Hemisphere'] = df_master['Latitude'] < 0
    df_master['Eastern Hemisphere'] = df_master['Longitude'] > 0
    df_master['Western Hemisphere'] = df_master['Longitude'] < 0

    # E. FIFA & Trivia
    if 'Total_Appearances' in df_master.columns:
        df_master['Played World Cup'] = df_master['Total_Appearances'] > 0
        df_master['Never Played World Cup'] = df_master['Total_Appearances'].fillna(0) == 0
        df_master['Played exactly 1 World Cup'] = df_master['Total_Appearances'] == 1
        df_master['Played in 5+ World Cups'] = df_master['Total_Appearances'] >= 5
        df_master['Played in 1930 World Cup'] = df_master['in_1930'] == True
        df_master['Played in 2022 World Cup'] = df_master['in_2022'] == True

    if not df_fifa_hw.empty:
        hosts = df_fifa_hw['Host Country FIFA Based Short Name'].dropna().unique()
        winners = df_fifa_hw['Winner Country FIFA Based Short Name'].dropna().unique()
        df_master['Hosted FIFA World Cup'] = df_master['cca3'].isin(hosts)
        df_master['Won World Cup'] = df_master['cca3'].isin(winners)

    if 'is_top_chocolate' in df_master.columns:
        df_master['Top 20 Chocolate Consumption'] = df_master['is_top_chocolate'] == True

    # --- 7. Build Category Sets & Compat Matrix ---
    print("Building dynamic sets & Matrix...")
    categories = {}
    bool_cols = [c for c in df_master.columns if df_master[c].dtype == bool]
    for col in bool_cols:
        if col not in ['is_landlocked', 'drives_left', 'borders_rus', 'borders_chn', 'borders_bra', 'borders_fra']:
            categories[col] = set(df_master[df_master[col] == True]["cca3"].tolist())

    categories["Is Landlocked"] = set(df_master[df_master['is_landlocked'] == True]["cca3"].tolist())
    categories["Drives on Left"] = set(df_master[df_master['drives_left'] == True]["cca3"].tolist())

    for continent in df_master["continent"].unique():
        if pd.notna(continent) and continent != "Unknown":
            categories[f"Continent: {continent}"] = set(df_master[df_master["continent"] == continent]["cca3"].tolist())

    compat_matrix = {}
    for c1, c2 in itertools.combinations(categories.keys(), 2):
        overlap_count = len(categories[c1] & categories[c2])
        key = f"{c1}|{c2}" if c1 < c2 else f"{c2}|{c1}"
        compat_matrix[key] = overlap_count

    serializable_categories = {k: list(v) for k, v in categories.items() if len(v) > 0}
    final_payload = {
        "_meta": {
            "built_at": datetime.now().isoformat(),
            "total_countries": len(df_master),
            "total_categories": len(serializable_categories),
        },
        "countries": df_master.set_index("cca3")[["name", "cca2"]].to_dict(orient="index"),
        "sets": serializable_categories,
        "_compat": compat_matrix,
    }

    with open("data/processed/master_countries.json", "wb") as f:
        f.write(orjson.dumps(final_payload, option=orjson.OPT_INDENT_2))
    print(f"✓ Success! Pro Database v4.0.1 built with {len(serializable_categories)} categories.")

if __name__ == "__main__":
    build_game_database()