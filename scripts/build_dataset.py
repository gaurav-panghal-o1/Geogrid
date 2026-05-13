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
    print("Fetching Base Data from REST Countries...")
    base_url = "https://restcountries.com/v3.1/all?fields=name,cca2,cca3,independent,population,area,region,landlocked,borders,car"
    with httpx.Client(headers={"User-Agent": "Mozilla/5.0"}, follow_redirects=True) as client:
        rest_data = client.get(base_url).json()
    
    countries_list = []
    rest_name_map = {}
    for c in rest_data:
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

    # --- World Bank Demographics ---
    df_gdp = fetch_world_bank_indicator("NY.GDP.PCAP.CD", "gdp_per_capita")
    df_life = fetch_world_bank_indicator("SP.DYN.LE00.IN", "life_expectancy")
    df_pop_dens = fetch_world_bank_indicator("EN.POP.DNST", "pop_density")
    df_infant = fetch_world_bank_indicator("SP.DYN.IMRT.IN", "infant_mortality")
    df_arable = fetch_world_bank_indicator("AG.LND.ARBL.ZS", "arable_land_pct")
    df_urban = fetch_world_bank_indicator("SP.URB.TOTL.IN.ZS", "urban_pop_pct")
    

    # --- Local Data Processing ---
    print("Processing Local Datasets...")
    base_path = os.path.join(os.path.dirname(__file__), "..", "data", "raw")
    
    df_latlong = pd.read_csv(os.path.join(base_path, "latlong.csv"))
    master_name_map = {**dict(zip(df_latlong['Country'].str.strip().str.lower(), df_latlong['ISO-ALPHA-3'].str.strip())), **rest_name_map}

    def load_mapped_csv(filename, country_col_name='Country'):
        try:
            df = pd.read_csv(os.path.join(base_path, filename))
            df['cca3'] = df[country_col_name].str.strip().str.lower().map(master_name_map)
            return df
        except: return pd.DataFrame(columns=['cca3'])
    # Load Rivers Dataset
    try:
        df_rivers = pd.read_csv(os.path.join(base_path, "rivers_filter.xlsx - Sheet1.csv"))
    except: 
        df_rivers = pd.DataFrame()

    df_flags = load_mapped_csv("world_flags_2024.csv")
    df_coast = load_mapped_csv("countries-by-coastline-2026.csv", "country")
    
    df_blocs   = load_mapped_csv("blocs.csv")
    df_wars    = load_mapped_csv("wars.csv")
    df_empires = load_mapped_csv("empires.csv")
    df_colony  = load_mapped_csv("colony.csv")
    df_govt    = load_mapped_csv("government.csv", "country")
    df_heritage= load_mapped_csv("heritage_sites.csv", "country")
    df_phys    = load_mapped_csv("country_physical_attribute.csv")
    df_crime   = load_mapped_csv("crime.csv", "country")
    
    try:
        df_indep = pd.read_csv(os.path.join(base_path, "country_independence year.csv"))
        df_indep['cca3'] = df_indep['country'].str.strip().str.lower().map(master_name_map)
    except: df_indep = pd.DataFrame(columns=['cca3'])

    df_f1 = load_mapped_csv("cf1.csv", "country")
    try:
        df_fifa_p = pd.read_csv(os.path.join(base_path, "fifa_participate.csv"), on_bad_lines='skip')
        df_fifa_p['cca3'] = df_fifa_p['FIFA_Code'] # FIFA codes mostly match CCA3
    except: df_fifa_p = pd.DataFrame(columns=['cca3'])

    try:
        # We don't need the mapping function because Groq already output perfect cca3 codes!
        df_rarity = pd.read_csv(os.path.join(base_path, "country_rarity.csv"))
    except: 
        df_rarity = pd.DataFrame(columns=['cca3', 'rarity'])

    try:
        df_fifa_hw = pd.read_csv(os.path.join(base_path, "fifawchostwinner.xlsx - Sheet1.csv"))
    except: df_fifa_hw = pd.DataFrame()

    try:
        df_oly = pd.read_csv(os.path.join(base_path, "olympic.csv"))
        # Olympic country names have trailing spaces sometimes, so we strip them
        df_oly['cca3'] = df_oly['countries '].astype(str).str.strip().str.lower().map(master_name_map)
    except: df_oly = pd.DataFrame(columns=['cca3'])

    df_un = pd.read_excel(os.path.join(base_path, "undata.xlsx"), sheet_name=0, skiprows=4)
    df_un['cca3'] = df_un['Unnamed: 1'].astype(str).str.strip().str.lower().map(master_name_map)

    # --- Master Merge ---
    print("Executing Master Merge...")
    df_master = df_base\
        .merge(df_gdp, on='cca3', how='left').merge(df_life, on='cca3', how='left')\
        .merge(df_pop_dens, on='cca3', how='left').merge(df_infant, on='cca3', how='left')\
        .merge(df_arable, on='cca3', how='left').merge(df_urban, on='cca3', how='left')\
        .merge(df_un[['cca3', 'Human Development Index (HDI) ']].rename(columns={'Human Development Index (HDI) ': 'hdi'}), on='cca3', how='left')\
        .merge(df_latlong[['ISO-ALPHA-3', 'Latitude', 'Longitude']], left_on='cca3', right_on='ISO-ALPHA-3', how='left')

    merges = [
        (df_flags, ['White', 'Red', 'Blue', 'Black', 'Yellow', 'Green', 'Orange', 'Stars', 'Sun', 'Cross', 'Crescent', 'BlazonOrOther']),
        (df_coast, ['CountryCoastlineKm']),
        (df_blocs, ['NATO_Member', 'Warsaw_Pact_Member', 'Commonwealth_Member']),
        (df_wars, ['WW_Participation', 'ColdWar_US', 'ColdWar_USSR', 'Non_Aligned']),
        (df_empires, ['Ottoman_Rule', 'USSR_Member', 'Napoleonic_Empire', 'Mongol_Empire', 'Roman_Empire']),
        (df_colony, ['British', 'French', 'Spanish', 'Portuguese', 'Dutch', 'Never_Colonized']),
        (df_govt, ['GovernmentSystemConstitutionalForm', 'GovernmentSystemHeadOfState']),
        (df_heritage, ['WorldHeritageSites_TotalSites_num_YearFree']),
        (df_indep, ['year']),
        (df_phys, ['Altitude_m', 'Avg_Temp_C', 'Climate_Zone']),
        (df_crime, ['CrimeIndexViaNumbeo_2025']),
        (df_f1, []), # Just merging on cca3 to know they exist
        (df_fifa_p, ['Total_Appearances', 'in_2022', 'in_1990', 'in_1998', 'in_1974']), # Key participation metrics
        (df_oly, ['summer_total', 'winter_total', 'total_total']),
        (df_rarity, ['rarity']),
        (df_rivers, []) # Just merging on cca3 to know they exist
    ]
    
    for df, cols in merges:
        if not df.empty and all(c in df.columns for c in cols):
            df_master = df_master.merge(df[['cca3'] + cols], on='cca3', how='left')

    # Apply fix to eliminate the PerformanceWarning (Memory Fragmentation)
    df_master = df_master.drop_duplicates(subset=['cca3']).copy() 

    # --- Derived Feature Engineering ---
    print("Generating v5.0 Granular Criteria...")
    
    # 1. Names
    name_upper = df_master['name'].astype(str).str.upper()
    df_master['Name is 4 letters'] = name_upper.str.len() == 4
    df_master['Name is 5 letters'] = name_upper.str.len() == 5
    df_master['Name is 6 letters'] = name_upper.str.len() == 6
    df_master['Name 10+ letters'] = name_upper.str.len() >= 10
    df_master['Multiple words'] = name_upper.str.contains(' ')
    for letter in "ABCMSTU": df_master[f'Starts with {letter}'] = name_upper.str.startswith(letter)

    # 2. Geography
    df_master['Northern Hemisphere'] = df_master['Latitude'] > 0
    df_master['Southern Hemisphere'] = df_master['Latitude'] < 0
    df_master['Borders 5+ countries'] = df_master['borders_count'] >= 5
    df_master['Borders Russia'] = df_master['borders_rus']
    df_master['Borders France'] = df_master['borders_fra']
    df_master['Borders China'] = df_master['borders_chn']
    df_master['Borders Brazil'] = df_master['borders_bra']

    df_master['Landlocked'] = df_master['is_landlocked']
    df_master['Drives on Left'] = df_master['drives_left']

    df_master['Coastline ≥ 100 km'] = pd.to_numeric(df_master.get('CountryCoastlineKm', 0), errors='coerce').fillna(0) >= 100
    df_master['Coastline ≥ 1K km'] = pd.to_numeric(df_master.get('CountryCoastlineKm', 0), errors='coerce').fillna(0) >= 1000
    df_master['Coastline < 100 km'] = pd.to_numeric(df_master.get('CountryCoastlineKm', 0), errors='coerce').fillna(0) < 100


    # 3. Economy & Demographics
    df_master['hdi'] = pd.to_numeric(df_master['hdi'], errors='coerce')
    df_master['HDI ≥ 0.8'] = df_master['hdi'] >= 0.8
    df_master['HDI < 0.6'] = df_master['hdi'] < 0.6

    df_master['infant_mortality'] = pd.to_numeric(df_master['infant_mortality'], errors='coerce')
    df_master['Infant Mortality ≥ 50'] = df_master['infant_mortality'] >= 50
    df_master['Infant Mortality < 10'] = df_master['infant_mortality'] < 10

    df_master['gdp_per_capita'] = pd.to_numeric(df_master['gdp_per_capita'], errors='coerce')
    df_master['GDP/cap ≥ $20K'] = df_master['gdp_per_capita'] >= 20000
    df_master['GDP/cap < $5K'] = df_master['gdp_per_capita'] < 5000

    if 'urban_pop_pct' in df_master.columns:
        df_master['Highly Urbanized (> 80%)'] = pd.to_numeric(df_master['urban_pop_pct'], errors='coerce') > 80

    # 4. Flags
    if 'Red' in df_master.columns:
        df_master['Red on flag'] = df_master['Red'] == 1
        df_master['Blue on flag'] = df_master['Blue'] == 1
        df_master['Star on flag'] = df_master['Stars'] >= 1
        df_master['Coat of arms on flag'] = df_master['BlazonOrOther'] == 1

    # 5. History: Empires
    if 'Roman_Empire' in df_master.columns:
        df_master['Part of Roman Empire'] = df_master['Roman_Empire'] == 1
        df_master['Part of Ottoman Empire'] = df_master['Ottoman_Rule'] == 1
        df_master['Part of USSR'] = df_master['USSR_Member'] == 1
        df_master['Part of Napoleonic Empire'] = df_master['Napoleonic_Empire'] == 1
        df_master['Part of Mongol Empire'] = df_master['Mongol_Empire'] == 1
        
    # 6. History: Wars & Blocs
    if 'WW_Participation' in df_master.columns:
        df_master['Participated in World Wars'] = df_master['WW_Participation'] == 1
        df_master['Cold War: US Aligned'] = df_master['ColdWar_US'] == 1
        df_master['Cold War: USSR Aligned'] = df_master['ColdWar_USSR'] == 1
        df_master['Cold War: Non-Aligned'] = df_master['Non_Aligned'] == 1
    
    if 'NATO_Member' in df_master.columns:
        df_master['NATO Member'] = df_master['NATO_Member'] == 1
        df_master['Warsaw Pact Member'] = df_master['Warsaw_Pact_Member'] == 1
        df_master['Commonwealth Member'] = df_master['Commonwealth_Member'] == 1
    
    # 7. History: Colonization
    if 'Never_Colonized' in df_master.columns:
        df_master['Never Colonized'] = df_master['Never_Colonized'] == 1
        df_master['Former British Colony'] = df_master['British'] == 1
        df_master['Former French Colony'] = df_master['French'] == 1
        df_master['Former Spanish Colony'] = df_master['Spanish'] == 1
        df_master['Former Portuguese Colony'] = df_master['Portuguese'] == 1
        df_master['Former Dutch Colony'] = df_master['Dutch'] == 1
        #df_master['Ever Colonized'] = df_master[['British', 'French', 'Spanish', 'Portuguese', 'Dutch']].sum(axis=1) > 0

    # 8. Independence
    if 'year' in df_master.columns:
        indep_year = pd.to_numeric(df_master['year'], errors='coerce')

        df_master['Independent Before 1500'] = indep_year < 1500
        df_master['Independent in 1720-1800'] = (indep_year >= 1720) & (indep_year <= 1800)
        df_master['Independent in 1900-1920'] = (indep_year >= 1900) & (indep_year <= 1920)
        df_master['Independent in 1920-1945'] = (indep_year >= 1920) & (indep_year <= 1945)
        df_master['Independent in 1945-1960'] = (indep_year >= 1945) & (indep_year <= 1960)
        df_master['Independent in 1975-1990'] = (indep_year >= 1975) & (indep_year <= 1990)

    # 9. Government & Heritage
    if 'GovernmentSystemConstitutionalForm' in df_master.columns:
        df_master['Is a Republic'] = df_master['GovernmentSystemConstitutionalForm'].str.contains('Republic', na=False, case=False)
        df_master['Is a Monarchy'] = df_master['GovernmentSystemConstitutionalForm'].str.contains('Monarchy', na=False, case=False)

    if 'WorldHeritageSites_TotalSites_num_YearFree' in df_master.columns:
        sites = pd.to_numeric(df_master['WorldHeritageSites_TotalSites_num_YearFree'], errors='coerce').fillna(0)
        df_master['Less than 5 UNESCO Heritage Sites'] = sites <= 5
        df_master['5-20 UNESCO Heritage Sites'] = sites.between(5, 20)
        df_master['50+ UNESCO Heritage Sites'] = sites >= 50
        df_master['No UNESCO Heritage Sites'] = sites == 0

    # 10. Physical & Environment
    if 'Avg_Temp_C' in df_master.columns:
        temp = pd.to_numeric(df_master['Avg_Temp_C'], errors='coerce')
        df_master['Average Temp > 25°C'] = temp > 25
        df_master['Average Temp < 10°C'] = temp < 10
        df_master['Average Temp < 0°C'] = temp < 0

    if 'Altitude_m' in df_master.columns:
        alt = pd.to_numeric(df_master['Altitude_m'], errors='coerce')
        df_master['Average Altitude > 1000m'] = alt > 1000
        df_master['Average Altitude < 200m'] = alt < 200
        
    if 'Climate_Zone' in df_master.columns:
        df_master['Tropical Climate'] = df_master['Climate_Zone'].str.contains('Tropical', na=False, case=False)
        df_master['Dry / Arid Climate'] = df_master['Climate_Zone'].str.contains('Dry', na=False, case=False)
        df_master['Temperate Climate'] = df_master['Climate_Zone'].str.contains('Temperate', na=False, case=False)

    # 11. Crime
    if 'CrimeIndexViaNumbeo_2025' in df_master.columns:
        crime = pd.to_numeric(df_master['CrimeIndexViaNumbeo_2025'], errors='coerce')
        df_master['High Crime Rate'] = crime > 55
        df_master['Moderate Crime Rate'] = crime.between(35, 55)
        df_master['Low Crime Rate'] = crime < 35


    # 12. Geography: Major River Systems
    if not df_rivers.empty:
        # Dictionary mapping the CSV names to the display names requested in your .txt file
        target_rivers = {
            "Amazonas": "Amazon",
            "Nile": "Nile",
            "Danube": "Danube",
            "Congo": "Congo",
            "Niger": "Niger",
            "Rhine": "Rhine",
            "Mekong": "Mekong",
            "Zambezi": "Zambezi"
        }

        # Initialize all the river columns to False by default
        for display_name in target_rivers.values():
            df_master[f'{display_name} River system'] = False

        # Parse the comma-separated countries and set to True
        for _, row in df_rivers.iterrows():
            river_name = str(row['river_name']).strip()
            
            if river_name in target_rivers:
                display_name = target_rivers[river_name]
                
                # Split the 'countries_passed' string into a clean list of country names
                countries = [c.strip() for c in str(row['countries_passed']).split(',')]
                
                for country_name in countries:
                    # Look up the cca3 code from your existing master map
                    cca3 = master_name_map.get(country_name.lower())
                    
                    if cca3:
                        # Find that specific country in df_master and flip its river status to True
                        df_master.loc[df_master['cca3'] == cca3, f'{display_name} River system'] = True

    # 12. Sports: F1 Racing
    if not df_f1.empty:
        # If a country is in the cf1.csv file, they hosted an F1 race
        f1_countries = df_f1['cca3'].dropna().unique()
        df_master['Hosted F1 Grand Prix'] = df_master['cca3'].isin(f1_countries)

    # 13. Sports: FIFA World Cup
    if 'Total_Appearances' in df_master.columns:
        # THE FALLBACK FIX: Forcefully fill missing data for the 150+ countries that never played
        df_master['Total_Appearances'] = df_master['Total_Appearances'].fillna(0)
        df_master['in_1930'] = df_master.get('in_1930', pd.Series(False)).fillna(False)
        df_master['in_1990'] = df_master.get('in_1990', pd.Series(False)).fillna(False)
        df_master['in_2022'] = df_master.get('in_2022', pd.Series(False)).fillna(False)
    # 13. Sports: FIFA World Cup
    if 'Total_Appearances' in df_master.columns:
        df_master['Played in a World Cup'] = df_master['Total_Appearances'] > 0
        df_master['Never Played in a World Cup'] = df_master['Total_Appearances'].fillna(0) == 0
        df_master['Played exactly 1 World Cup'] = df_master['Total_Appearances'] == 1
        df_master['Played in 5-10 World Cups'] = df_master['Total_Appearances'].between(5, 10)
        df_master['Played in 10+ World Cups'] = df_master['Total_Appearances'] >= 10
        # df_master['Played in 1990 World Cup'] = df_master['in_1990'] == True
        # df_master['Played in 2022 World Cup'] = df_master['in_2022'] == True
        df_master['in_1998'] = df_master.get('in_1998', pd.Series(False)).fillna(False)
        df_master['in_1974'] = df_master.get('in_1974', pd.Series(False)).fillna(False)
        df_master['in_1990'] = df_master.get('in_1990', pd.Series(False)).fillna(False)
        df_master['in_2022'] = df_master.get('in_2022', pd.Series(False)).fillna(False)

    if not df_fifa_hw.empty:
        hosts = df_fifa_hw['Host Country FIFA Based Short Name'].dropna().unique()
        winners = df_fifa_hw['Winner Country FIFA Based Short Name'].dropna().unique()
        runners = df_fifa_hw['Runner Up Country FIFA Based Short Name'].dropna().unique()
        
        df_master['Hosted FIFA World Cup'] = df_master['cca3'].isin(hosts)
        df_master['Won FIFA World Cup'] = df_master['cca3'].isin(winners)
        df_master['Lost World Cup Final'] = df_master['cca3'].isin(runners)

    # 14. Sports: Olympic Games
    if 'total_total ' in df_master.columns or 'total_total' in df_master.columns:
        # Note: Olympic CSV has thousands separated by commas (e.g. "2,629"), so we must safely convert them to numbers
        df_master['summer_medals'] = pd.to_numeric(df_master['summer_total'].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
        df_master['winter_medals'] = pd.to_numeric(df_master['winter_total'].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
        df_master['total_medals'] = pd.to_numeric(df_master['total_total '].astype(str).str.replace(',', ''), errors='coerce').fillna(0)

        df_master['0 Olympic Medals'] = df_master['total_medals'] == 0
        df_master['Has Less than 50 Summer Olympic Medals'] = df_master['summer_medals'] < 50
        df_master['Has Less than 10 Summer Olympic Medals'] = df_master['summer_medals'] < 10
        df_master['10+ Olympic Medals'] = df_master['total_medals'] >= 10
        df_master['50+ Olympic Medals'] = df_master['total_medals'] >= 50
        df_master['100+ Olympic Medals'] = df_master['total_medals'] >= 100


    # --- Build Category Sets, Semantic Groups, & Matrix ---
    print("Building dynamic sets & Matrix...")
    categories = {}
    bool_cols = [c for c in df_master.columns if df_master[c].dtype == bool]
    
    ugly_names = ['is_landlocked', 'drives_left', 'borders_rus', 'borders_chn', 'borders_bra', 'borders_fra']
    for col in bool_cols:
        if col not in ugly_names:
            categories[col] = set(df_master[df_master[col] == True]["cca3"].tolist())

    categories["Is Landlocked"] = set(df_master[df_master['is_landlocked'] == True]["cca3"].tolist())
    categories["Drives on Left"] = set(df_master[df_master['drives_left'] == True]["cca3"].tolist())

    for continent in df_master["continent"].unique():
        if pd.notna(continent) and continent not in ["Unknown", "Antarctica"]:
            categories[f"Continent: {continent}"] = set(
                df_master[df_master["continent"] == continent]["cca3"].tolist()
            )

    compat_matrix = {}
    for c1, c2 in itertools.combinations(categories.keys(), 2):
        overlap_count = len(categories[c1] & categories[c2])
        key = f"{c1}|{c2}" if c1 < c2 else f"{c2}|{c1}"
        compat_matrix[key] = overlap_count

    serializable_categories = {k: list(v) for k, v in categories.items() if len(v) > 0}
    
    # ASSIGN SEMANTIC GROUPS TO PREVENT DUPLICATES ON THE BOARD
    category_groups = {}
    for col in serializable_categories.keys():
        col_lower = col.lower()
        if "hdi" in col_lower: category_groups[col] = "Economy_HDI"
        elif "gdp" in col_lower: category_groups[col] = "Economy_GDP"
        elif "letters" in col_lower or "words" in col_lower: category_groups[col] = "Name_Length"
        elif "starts with" in col_lower: category_groups[col] = "Name_Start"
        elif "hemisphere" in col_lower: category_groups[col] = "Geography_Hemisphere"
        elif "borders" in col_lower: category_groups[col] = "Geography_Borders"
        elif "continent" in col_lower: category_groups[col] = "Geography_Continent"
        elif "flag" in col_lower: category_groups[col] = "Flags"
        elif "empire" in col_lower or "ussr" in col_lower: category_groups[col] = "History_Empires"
        elif "colon" in col_lower: category_groups[col] = "History_Colony"
        elif "war" in col_lower or "aligned" in col_lower: category_groups[col] = "History_Wars"
        elif "nato" in col_lower or "pact" in col_lower or "commonwealth" in col_lower: category_groups[col] = "History_Blocs"
        elif "crime" in col_lower: category_groups[col] = "Society_Crime"
        elif "temp" in col_lower or "climate" in col_lower: category_groups[col] = "Environment_Climate"
        elif "altitude" in col_lower: category_groups[col] = "Environment_Altitude"
        elif "independent" in col_lower: category_groups[col] = "History_Independence"
        elif "unesco" in col_lower: category_groups[col] = "Society_Heritage"
        elif "republic" in col_lower or "monarchy" in col_lower: category_groups[col] = "Society_Govt"
        elif "urbanized" in col_lower: category_groups[col] = "Society_Urban"
        elif "river system" in col_lower: category_groups[col] = "Geography_Rivers"
        elif "world cup" in col_lower: category_groups[col] = "Sports_Football"
        elif "olympic" in col_lower: category_groups[col] = "Sports_Olympics"
        elif "f1 " in col_lower: category_groups[col] = "Sports_Motorsport"
        else: category_groups[col] = "Misc"


    final_payload = {
        "_meta": {
            "built_at": datetime.now().isoformat(),
            "total_countries": len(df_master),
            "total_categories": len(serializable_categories),
        },
        "countries": df_master.set_index("cca3")[["name", "cca2", "rarity"]].to_dict(orient="index"),
        "sets": serializable_categories,
        "_compat": compat_matrix,
        "_groups": category_groups  # Pass groups to the engine
    }

    with open("data/processed/master_countries.json", "wb") as f:
        f.write(orjson.dumps(final_payload, option=orjson.OPT_INDENT_2))
    print(f"Success! Database built with {len(serializable_categories)} categories.")

if __name__ == "__main__":
    build_game_database()