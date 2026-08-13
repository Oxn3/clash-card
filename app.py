import streamlit as st
import pandas as pd
import gspread
import io
import time
import datetime
import json
import socket
import numpy as np
from scipy.optimize import milp, LinearConstraint, Bounds

# Set global default timeout for all network requests to 5 seconds
socket.setdefaulttimeout(5)

# --- 1. PAGE SETUP ---
st.set_page_config(page_title="Clash Trade Optimizer", layout="wide", page_icon="⚔️")

st.title("⚔️ Clash Cards Trade Optimizer")

# --- 2. CONFIGURATION: MASTER CLAN REGISTRY URL ---
try:
    MASTER_REGISTRY_URL = st.secrets["MASTER_REGISTRY_URL"]
except Exception:
    st.error("⚠️ Config setup error: MASTER_REGISTRY_URL missing in app secrets!")
    st.stop()

# --- 3. AUTHENTICATION HELPER FOR GSPREAD ---
def get_gspread_client():
    """Builds an authenticated gspread client safely from Streamlit secrets without console prints."""
    try:
        creds_dict = None

        if "connections" in st.secrets and "gsheets" in st.secrets["connections"]:
            creds_dict = dict(st.secrets["connections"]["gsheets"])
        elif "gsheets" in st.secrets:
            creds_dict = dict(st.secrets["gsheets"])
        elif "service_account" in st.secrets:
            creds_dict = dict(st.secrets["service_account"])
        elif "GCP_SERVICE_ACCOUNT" in st.secrets:
            creds_dict = json.loads(st.secrets["GCP_SERVICE_ACCOUNT"])

        if creds_dict:
            clean_creds = dict(creds_dict)
            if "private_key" in clean_creds:
                clean_creds["private_key"] = clean_creds["private_key"].replace("\\n", "\n")
            clean_creds["type"] = "service_account"
            return gspread.service_account_from_dict(clean_creds)
        else:
            st.error("❌ Authentication Error: Could not load service credentials.")
            st.stop()

    except Exception:
        st.error("❌ Authentication Error: Invalid service account configuration.")
        st.stop()

# --- DIRECT GSPREAD LOADER (Bypasses GSheetsConnection hanging issues) ---
@st.cache_data(ttl=10)
def fetch_sheet_direct(url):
    """Directly fetches sheet data using gspread to prevent GSheetsConnection from hanging."""
    try:
        client = get_gspread_client()
        sh = client.open_by_url(url)
        ws = sh.get_worksheet(0)
        data = ws.get_all_records()
        return pd.DataFrame(data)
    except Exception as e:
        st.error(f"⚠️ Error loading sheet: {e}")
        st.stop()

# --- 4. SESSION STATE INITIALIZATION ---
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
if "player_name" not in st.session_state:
    st.session_state.player_name = None
if "stage_1_results" not in st.session_state:
    st.session_state.stage_1_results = None
if "stage_2_results" not in st.session_state:
    st.session_state.stage_2_results = None
if "active_trade" not in st.session_state:
    st.session_state.active_trade = None

# --- 5. HELPER FUNCTIONS ---
def validate_inputs(tag, p_name, pwd):
    if not tag.startswith("#") or len(tag) < 3:
        return False, "Clan Tag must start with '#' and be at least 3 characters."
    if not p_name or len(p_name) < 2:
        return False, "Please enter a valid Player Name."
    if len(pwd) < 4:
        return False, "Password must be at least 4 characters long."
    return True, ""

def validate_player_data(clan_df, player_col):
    col_data = clan_df[player_col]
    
    if col_data.isnull().any():
        null_count = col_data.isnull().sum()
        return False, f"Your column has **{null_count} empty/blank cell(s)**. Please fill in a number (0 or higher) for every troop."

    invalid_rows = []
    for idx, val in col_data.items():
        try:
            num_val = float(val)
            if not num_val.is_integer():
                invalid_rows.append(f"Row {idx+2}: decimal value ({val})")
            elif num_val < 0:
                invalid_rows.append(f"Row {idx+2}: negative value ({int(num_val)})")
        except (ValueError, TypeError):
            invalid_rows.append(f"Row {idx+2}: non-numeric value ('{val}')")

    if invalid_rows:
        error_details = ", ".join(invalid_rows[:3])
        if len(invalid_rows) > 3:
            error_details += f" ... and {len(invalid_rows) - 3} more."
        return False, f"Found **{len(invalid_rows)} invalid troop count(s)** ({error_details}). All counts must be valid non-negative integers (0 or greater)."

    return True, ""

def generate_excel_template():
    troops = [
        ('Raged Barbarian', 'Builder Elixir'), ('Sneaky Archer', 'Builder Elixir'),
        ('Boxer Giant', 'Builder Elixir'), ('Beta Minion', 'Builder Elixir'),
        ('Bomber', 'Builder Elixir'), ('Baby Dragon (Builder Base)', 'Builder Elixir'),
        ('Cannon Cart', 'Builder Elixir'), ('Night Witch', 'Builder Elixir'),
        ('Drop Ship', 'Builder Elixir'), ('Power P.E.K.K.A', 'Builder Elixir'),
        ('Hog Glider', 'Builder Elixir'), ('Minion', 'Dark Elixir'),
        ('Hog Rider', 'Dark Elixir'), ('Valkyrie', 'Dark Elixir'),
        ('Golem', 'Dark Elixir'), ('Witch', 'Dark Elixir'),
        ('Lava Hound', 'Dark Elixir'), ('Bowler', 'Dark Elixir'),
        ('Ice Golem', 'Dark Elixir'), ('Headhunter', 'Dark Elixir'),
        ('Apprentice Warden', 'Dark Elixir'), ('Druid', 'Dark Elixir'),
        ('Furnace', 'Dark Elixir'), ('Ruin Witch', 'Dark Elixir'),
        ('Super Minion', 'Dark Elixir'), ('Super Valkyrie', 'Dark Elixir'),
        ('Super Witch', 'Dark Elixir'), ('Ice Hound', 'Dark Elixir'),
        ('Super Bowler', 'Dark Elixir'), ('Super Hog Rider', 'Dark Elixir'),
        ('Barbarian', 'Elixir'), ('Archer', 'Elixir'),
        ('Giant', 'Elixir'), ('Goblin', 'Elixir'),
        ('Wall Breaker', 'Elixir'), ('Balloon', 'Elixir'),
        ('Wizard', 'Elixir'), ('Healer', 'Elixir'),
        ('Dragon', 'Elixir'), ('P.E.K.K.A', 'Elixir'),
        ('Baby Dragon', 'Elixir'), ('Miner', 'Elixir'),
        ('Electro Dragon', 'Elixir'), ('Yeti', 'Elixir'),
        ('Dragon Rider', 'Elixir'), ('Electro Titan', 'Elixir'),
        ('Root Rider', 'Elixir'), ('Thrower', 'Elixir'),
        ('Meteor Golem', 'Elixir'), ('Super Barbarian', 'Elixir'),
        ('Super Archer', 'Elixir'), ('Super Giant', 'Elixir'),
        ('Sneaky Goblin', 'Elixir'), ('Super Wall Breaker', 'Elixir'),
        ('Rocket Balloon', 'Elixir'), ('Super Wizard', 'Elixir'),
        ('Super Dragon', 'Elixir'), ('Inferno Dragon', 'Elixir'),
        ('Super Miner', 'Elixir'), ('Super Yeti', 'Elixir')
    ]
    
    template_data = {
        "Troop Name": [t[0] for t in troops],
        "Upgrade Resource": [t[1] for t in troops],
        "Player 1": [0] * len(troops),
        "Player 2": [0] * len(troops),
        "Player 3": [0] * len(troops),
        "Player 4": [0] * len(troops)
    }
    
    template_df = pd.DataFrame(template_data)
    
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        template_df.to_excel(writer, index=False, sheet_name="Sheet1")
    
    return output.getvalue()

# --- 6. SIDEBAR: AUTHENTICATION ENGINE ---
st.sidebar.header("🔑 Clan Portal")

if not st.session_state.authenticated:
    st.sidebar.info("Enter your Clan Tag, Player Name, and Password.")
    
    clan_tag_input = st.sidebar.text_input("Clan Tag", value="#CLAN123").strip().upper()
    player_name_input = st.sidebar.text_input("Your Player Name").strip()
    clan_pass_input = st.sidebar.text_input("Password", type="password")

    try:
        registry_df = fetch_sheet_direct(MASTER_REGISTRY_URL)
        existing_clan = registry_df[registry_df["Clan Tag"].astype(str).str.upper() == clan_tag_input]
    except Exception:
        existing_clan = pd.DataFrame()

    clan_url_input = ""
    if existing_clan.empty and len(clan_tag_input) >= 3:
        st.sidebar.divider()
        st.sidebar.subheader("🆕 New Clan Registration")
        st.sidebar.caption("Need a starting sheet? Download our template, upload it to your Google Drive as a Google Sheet, set sharing to 'Anyone with link can edit', and paste the URL below.")
        
        template_bytes = generate_excel_template()
        st.sidebar.download_button(
            label="📥 Download Clan Sheet Template (.xlsx)",
            data=template_bytes,
            file_name="Clash_Card_Template.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True
        )
        
        clan_url_input = st.sidebar.text_input("Clan Google Sheet URL").strip()

    if st.sidebar.button("🔓 Login / Connect Clan", type="primary"):
        is_valid, err_msg = validate_inputs(clan_tag_input, player_name_input, clan_pass_input)
        if not is_valid:
            st.sidebar.error(f"❌ {err_msg}")
        else:
            try:
                credentials_valid = False
                sheet_url_to_use = ""

                if not existing_clan.empty:
                    db_pass = str(existing_clan.iloc[0]["Password"])
                    db_url = str(existing_clan.iloc[0]["Sheet URL"]).strip()
                    
                    if clan_pass_input == db_pass:
                        credentials_valid = True
                        sheet_url_to_use = db_url
                    else:
                        st.sidebar.error("❌ Incorrect Password.")
                else:
                    if not clan_url_input or "docs.google.com/spreadsheets" not in clan_url_input:
                        st.sidebar.error("❌ Please provide a valid Google Sheet URL to register a new clan.")
                    else:
                        client = get_gspread_client()
                        sh = client.open_by_url(MASTER_REGISTRY_URL)
                        ws = sh.get_worksheet(0)
                        ws.append_row([clan_tag_input, clan_pass_input, clan_url_input])
                        
                        credentials_valid = True
                        sheet_url_to_use = clan_url_input

                if credentials_valid and sheet_url_to_use:
                    with st.spinner("Validating player login..."):
                        clan_df = fetch_sheet_direct(sheet_url_to_use)
                        
                        card_matches = [c for c in clan_df.columns if any(k in str(c).lower() for k in ["card", "troop", "name"])]
                        card_col = card_matches[0] if card_matches else clan_df.columns[0]
                        type_matches = [c for c in clan_df.columns if any(k in str(c).lower() for k in ["type", "resource"])]
                        type_col = type_matches[0] if type_matches else (clan_df.columns[1] if len(clan_df.columns) > 1 else clan_df.columns[0])
                        
                        player_cols = [str(c).strip() for c in clan_df.columns if c not in [card_col, type_col]]
                        recorded_names_lower = [p.lower() for p in player_cols]

                        if player_name_input.lower() not in recorded_names_lower:
                            st.sidebar.error(f"❌ Player **'{player_name_input}'** not found in clan roster!")
                            st.sidebar.markdown(f"👉 **[Click here to open Clan Sheet & add your column]({sheet_url_to_use})**")
                        else:
                            matched_name = next(p for p in player_cols if p.lower() == player_name_input.lower())
                            data_ok, data_err = validate_player_data(clan_df, matched_name)
                            
                            if not data_ok:
                                st.sidebar.error(f"❌ **Data Validation Failed for {matched_name}:**\n\n{data_err}")
                                st.sidebar.markdown(f"👉 **[Click here to open Clan Sheet & fix your data]({sheet_url_to_use})**")
                            else:
                                st.session_state.authenticated = True
                                st.session_state.clan_tag = clan_tag_input
                                st.session_state.sheet_url = sheet_url_to_use
                                st.session_state.player_name = matched_name
                                st.sidebar.success(f"Welcome, {matched_name} ({clan_tag_input})!")
                                st.rerun()

            except Exception:
                st.sidebar.error("❌ Unable to verify credentials right now. Please try again.")

    st.warning("⚠️ Please log in via sidebar to access your clan data.")
    st.stop()

# --- IF AUTHENTICATED ---
st.sidebar.success(f"🟢 Connected: **{st.session_state.clan_tag}**")
st.sidebar.info(f"👤 Player: **{st.session_state.player_name}**")

if st.sidebar.button("🔒 Logout"):
    st.session_state.authenticated = False
    st.session_state.player_name = None
    st.session_state.stage_1_results = None
    st.session_state.stage_2_results = None
    st.session_state.active_trade = None
    st.rerun()

st.sidebar.divider()

# --- 7. SAFE REFRESH & LIVE DATA LOAD ---
try:
    with st.spinner("Syncing card inventory..."):
        live_df = fetch_sheet_direct(st.session_state.sheet_url)
except Exception:
    st.error("⚠️ System temporarily offline. Unable to retrieve live inventory.")
    st.stop()

# --- 7. SIDEBAR ANALYTICAL DASHBOARD ---
card_matches = [c for c in live_df.columns if any(k in str(c).lower() for k in ["card", "troop", "name"])]
card_col = card_matches[0] if card_matches else live_df.columns[0]

type_matches = [c for c in live_df.columns if any(k in str(c).lower() for k in ["type", "resource"])]
type_col = type_matches[0] if type_matches else (live_df.columns[1] if len(live_df.columns) > 1 else live_df.columns[0])

player_cols = [c for c in live_df.columns if c not in [card_col, type_col]]

# --- NEW: CALCULATE COMPLETED VS INCOMPLETE PLAYERS ---
total_players = len(player_cols)
completed_players_count = 0

for p in player_cols:
    player_inventory = pd.to_numeric(live_df[p], errors='coerce').fillna(0)
    if (player_inventory > 0).all():
        completed_players_count += 1

incomplete_players_count = total_players - completed_players_count

# Stats Analytics
total_trades_count = 0
cards_gained_count = 0
player_gains = {}

try:
    history_sheet_url = st.secrets.get("HISTORY_SHEET_URL")
    if history_sheet_url:
        client = get_gspread_client()
        sh = client.open_by_url(history_sheet_url)
        ws = sh.get_worksheet(0)
        history_vals = ws.get_all_values()
        
        if len(history_vals) > 1:
            headers = history_vals[0]
            rows = history_vals[1:]
            total_trades_count = len(rows)
            
            init_idx = headers.index("Initiator") if "Initiator" in headers else 1
            part_idx = headers.index("Partner") if "Partner" in headers else 4
            new_idx = headers.index("New Cards Gained") if "New Cards Gained" in headers else -1

            for r in rows:
                initiator = r[init_idx]
                partner = r[part_idx]
                gained_val = 1
                
                if new_idx != -1 and len(r) > new_idx:
                    try:
                        gained_val = int(r[new_idx])
                    except ValueError:
                        pass
                
                cards_gained_count += gained_val
                
                if gained_val > 0:
                    player_gains[initiator] = player_gains.get(initiator, 0) + 1
                    if gained_val == 2:
                        player_gains[partner] = player_gains.get(partner, 0) + 1

except Exception:
    pass    

top_player_name = "N/A"
top_player_count = 0

if player_gains:
    top_player_name = max(player_gains, key=player_gains.get)
    top_player_count = player_gains[top_player_name]

total_cards_in_catalog = len(live_df)
unique_missing_cards = 0

for _, row in live_df.iterrows():
    if all((pd.to_numeric(row[p], errors='coerce') or 0) == 0 for p in player_cols):
        unique_missing_cards += 1

dup_elixir = 0
dup_dark_elixir = 0
dup_builder_elixir = 0

for _, row in live_df.iterrows():
    r_type = str(row[type_col]).strip().lower()
    for p in player_cols:
        try:
            val = int(row[p]) if pd.notnull(row[p]) else 0
            dups = max(0, val - 1)
            
            if "builder" in r_type:
                dup_builder_elixir += dups
            elif "dark" in r_type:
                dup_dark_elixir += dups
            elif "elixir" in r_type:
                dup_elixir += dups
        except ValueError:
            pass

st.sidebar.subheader("📊 Clan Stats")

# --- UI DISPLAY: METRICS GRID ---
row1_col1, row1_col2 = st.sidebar.columns(2)
with row1_col1:
    st.metric("🤝 Trades Done", total_trades_count)
with row1_col2:
    st.metric("🎉 Cards Gained", cards_gained_count)

# --- NEW METRICS ROW FOR EVENT COMPLETION ---
row2_col1, row2_col2 = st.sidebar.columns(2)
with row2_col1:
    st.metric("✅ Completed Event", f"{completed_players_count} / {total_players}")
with row2_col2:
    st.metric("⏳ Still Collecting", incomplete_players_count)

row3_col1, row3_col2 = st.sidebar.columns(2)
with row3_col1:
    st.metric("❌ Unique Missing", f"{unique_missing_cards} / {total_cards_in_catalog}")
with row3_col2:
    st.metric(f"🏆 {top_player_name if top_player_count > 0 else 'Top Collector'}", f"{top_player_count}" if top_player_count > 0 else "0")

# --- CALCULATE DUPLICATES & UNIQUE MISSING PER TYPE ---
dup_elixir = 0
dup_dark_elixir = 0
dup_builder_elixir = 0

missing_elixir = 0
missing_dark_elixir = 0
missing_builder_elixir = 0

for _, row in live_df.iterrows():
    r_type = str(row[type_col]).strip().lower()
    
    all_missing = all((pd.to_numeric(row[p], errors='coerce') or 0) == 0 for p in player_cols)
    if all_missing:
        if "builder" in r_type:
            missing_builder_elixir += 1
        elif "dark" in r_type:
            missing_dark_elixir += 1
        elif "elixir" in r_type:
            missing_elixir += 1

    for p in player_cols:
        try:
            val = int(row[p]) if pd.notnull(row[p]) else 0
            dups = max(0, val - 1)
            
            if "builder" in r_type:
                dup_builder_elixir += dups
            elif "dark" in r_type:
                dup_dark_elixir += dups
            elif "elixir" in r_type:
                dup_elixir += dups
        except ValueError:
            pass

# --- UI DISPLAY: 2-COLUMN BREAKDOWN STRICTLY INSIDE EXPANDER ---
with st.sidebar.expander("📦 Clan Card Breakdown", expanded=True) as breakdown_expander:
    col_dup, col_miss = breakdown_expander.columns(2)
    
    with col_dup:
        st.markdown("**🔄 Duplicates**")
        st.caption("Extra copies")
        st.write(f"💧 Elixir: `{dup_elixir}`")
        st.write(f"🖤 Dark: `{dup_dark_elixir}`")
        st.write(f"🔨 Builder: `{dup_builder_elixir}`")

    with col_miss:
        st.markdown("**❌ Missing**")
        st.caption("Extinct cards")
        st.write(f"💧 Elixir: `{missing_elixir}`")
        st.write(f"🖤 Dark: `{missing_dark_elixir}`")
        st.write(f"🔨 Builder: `{missing_builder_elixir}`")

# --- MAIN PAGE CONTINUES ---
col_title, _, col_refresh = st.columns([2.5, 1.0, 0.8], vertical_alignment="center")

with col_title:
    st.subheader(f"📋 Live Card Inventory Grid — {st.session_state.clan_tag}")

with col_refresh:
    if st.button("🔄 Sync Live Inventory", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

st.caption("Double-click any cell to edit numbers directly. Edits will feed into the optimizer.")

selected_players = st.multiselect(
    "👥 Filter Included Players:",
    options=player_cols,
    default=player_cols
)

active_cols = [card_col, type_col] + selected_players
filtered_df = live_df[active_cols].copy()

# --- TABLE 1: CLEAN STANDARD DATA EDITOR ---
edited_df = st.data_editor(
    filtered_df, 
    num_rows="dynamic", 
    use_container_width=True, 
    key="live_editor_grid"
)

grid_btn_col1, grid_btn_col2, _ = st.columns([1.5, 1.5, 3])

with grid_btn_col1:
    if st.button("💾 Save Manual Edits to Google Sheet", type="secondary", use_container_width=True):
        try:
            with st.spinner("Saving edits to Google Sheet..."):
                client = get_gspread_client()
                target_sheet = st.session_state.get("sheet_url") or st.secrets.get("MASTER_REGISTRY_URL")
                sh = client.open_by_url(target_sheet)
                ws = sh.get_worksheet(0)
                
                clean_df = edited_df.fillna("")
                ws.update([clean_df.columns.values.tolist()] + clean_df.values.tolist())
                
                st.cache_data.clear()
                st.success("✅ Inventory sheet successfully updated!")
                time.sleep(1)
                st.rerun()
        except Exception as e:
            st.error(f"❌ Failed to save updates to Google Sheet: {e}")

with grid_btn_col2:
    target_sheet_url = st.session_state.get("sheet_url") or st.secrets.get("MASTER_REGISTRY_URL")
    st.link_button("🔗 Open Google Sheet", target_sheet_url, use_container_width=True)

import numpy as np
from scipy.optimize import milp, LinearConstraint, Bounds
from scipy.sparse import dok_matrix

# --- 8. MEMORY-EFFICIENT ILP ENGINE (< 15MB RAM USAGE) ---
def run_optimization(data_df):
    card_matches = [c for c in data_df.columns if any(k in str(c).lower() for k in ["card", "troop", "name"])]
    card_col = card_matches[0] if card_matches else data_df.columns[0]

    type_matches = [c for c in data_df.columns if any(k in str(c).lower() for k in ["type", "resource"])]
    type_col = type_matches[0] if type_matches else (data_df.columns[1] if len(data_df.columns) > 1 else data_df.columns[0])

    player_cols = [c for c in data_df.columns if c not in [card_col, type_col]]

    catalog = {}
    for _, row in data_df.iterrows():
        name = str(row[card_col])
        catalog[name] = {
            "Type": str(row[type_col]),
            "IsSuper": "super" in name.lower()
        }

    all_cards = list(catalog.keys())
    num_players = len(player_cols)
    num_cards = len(all_cards)

    # Initial inventory matrix
    inv = np.zeros((num_players, num_cards), dtype=int)
    for p_idx, p in enumerate(player_cols):
        for c_idx, c in enumerate(all_cards):
            val = data_df.loc[data_df[card_col] == c, p].values
            try:
                inv[p_idx, c_idx] = int(val[0]) if len(val) > 0 and pd.notnull(val[0]) else 0
            except:
                inv[p_idx, c_idx] = 0

    # Build candidate legal trades list
    candidates = []
    for i in range(num_players):
        for j in range(num_players):
            if i == j: continue
            for g in range(num_cards):
                if inv[i, g] < 2: continue
                g_info = catalog[all_cards[g]]
                for r in range(num_cards):
                    if inv[i, r] != 0 or inv[j, r] < 2: continue
                    r_info = catalog[all_cards[r]]
                    if g_info["Type"] == r_info["Type"] and g_info["IsSuper"] == r_info["IsSuper"]:
                        candidates.append((i, j, g, r))

    num_candidates = len(candidates)

    if num_candidates == 0:
        curr_state = {p: {c: int(inv[p_idx, c_idx]) for c_idx, c in enumerate(all_cards)} for p_idx, p in enumerate(player_cols)}
        sol = {"trades": [], "state": curr_state, "missing": 0, "players": 0}
        return sol, [], player_cols, data_df.copy(), card_col

    # --- MEMORY-SAVING SPARSE MATRIX FORMULATION ---
    c_obj = np.zeros(num_candidates)
    for idx, (i, j, g, r) in enumerate(candidates):
        is_super = catalog[all_cards[g]]["IsSuper"]
        c_obj[idx] = -(100 + (25 if is_super else 0))

    # Calculate exact total constraints rows to pre-allocate
    num_supply = num_players * num_cards
    num_demand = num_players * num_cards
    total_constraints = num_supply + num_demand

    # Use Sparse Matrix (DOK format) so zeroes do NOT consume RAM
    A_sparse = dok_matrix((total_constraints, num_candidates), dtype=float)
    b_l = np.zeros(total_constraints)
    b_u = np.zeros(total_constraints)

    row_idx = 0

    # 1. Supply Constraints
    for i in range(num_players):
        for g in range(num_cards):
            dup = max(0, inv[i, g] - 1)
            b_l[row_idx] = 0
            b_u[row_idx] = dup
            row_idx += 1

    # 2. Demand Constraints
    for i in range(num_players):
        for r in range(num_cards):
            b_l[row_idx] = 0
            b_u[row_idx] = 1 if inv[i, r] == 0 else 0
            row_idx += 1

    # Map variables directly into sparse matrix without copying lists
    for idx, (p_init, p_part, c_give, c_rec) in enumerate(candidates):
        supply_row_init_give = (p_init * num_cards) + c_give
        supply_row_part_rec = (p_part * num_cards) + c_rec
        demand_row_init_rec = (num_supply) + (p_init * num_cards) + c_rec

        A_sparse[supply_row_init_give, idx] += 1
        A_sparse[supply_row_part_rec, idx] += 1
        A_sparse[demand_row_init_rec, idx] += 1

    # Convert to Compressed Sparse Column format for Scipy
    constraints = LinearConstraint(A_sparse.tocsc(), b_l, b_u)
    integrality = np.ones(num_candidates)
    bounds = Bounds(lb=0, ub=1)

    # Solve MILP
    res = milp(c=c_obj, integrality=integrality, bounds=bounds, constraints=constraints)

    executed_trades = []
    curr_state_mat = inv.copy()

    if res.success and res.x is not None:
        chosen_indices = np.where(res.x > 0.5)[0]
        for idx in chosen_indices:
            i, j, g, r = candidates[idx]
            curr_state_mat[i, g] -= 1
            curr_state_mat[j, g] += 1
            curr_state_mat[j, r] -= 1
            curr_state_mat[i, r] += 1

            executed_trades.append({
                "Initiator": player_cols[i],
                "Partner": player_cols[j],
                "Give": all_cards[g],
                "Receive": all_cards[r],
                "Type": catalog[all_cards[g]]["Type"]
            })

    curr_state = {}
    benefited_players = set()
    missing_gained = 0

    for p_idx, p in enumerate(player_cols):
        curr_state[p] = {}
        for c_idx, c in enumerate(all_cards):
            final_val = int(curr_state_mat[p_idx, c_idx])
            curr_state[p][c] = final_val
            if inv[p_idx, c_idx] == 0 and final_val > 0:
                missing_gained += 1
                benefited_players.add(p)

    sol = {
        "trades": executed_trades,
        "state": curr_state,
        "missing": missing_gained,
        "players": len(benefited_players)
    }

    updated_df = data_df.copy()
    for p in player_cols:
        for idx, row in updated_df.iterrows():
            card_name = str(row[card_col])
            updated_df.at[idx, p] = curr_state[p].get(card_name, row[p])

    return sol, [], player_cols, updated_df, card_col

# --- 9. TRADE MONITORING ENGINE ---
if st.session_state.active_trade is not None:
    trade_info = st.session_state.active_trade
    elapsed = int(time.time() - trade_info["start_time"])
    time_left = max(0, 180 - elapsed)

    trade = trade_info["trade"]
    card_col = trade_info["card_col"]
    init = trade["Initiator"]
    part = trade["Partner"]
    give = trade["Give"]
    rec = trade["Receive"]

    target_sheet = st.session_state.get("sheet_url") or st.secrets.get("MASTER_REGISTRY_URL")

    st.divider()
    st.warning(f"⏳ **Active Trade Action Required** (Initiated by: **{trade_info['initiated_by']}**)")
    
    col_t1, col_t2 = st.columns([3, 1])
    col_t1.markdown(f"**Trade in Progress:** 👤 `{init}` gives **{give}** ➡️ receives **{rec}** from 👤 `{part}`")
    
    mins, secs = divmod(time_left, 60)
    col_t2.metric("Time Remaining", f"{mins:02d}:{secs:02d}")

    btn_col1, btn_col2, _ = st.columns([1.5, 1.5, 3])
    
    with btn_col1:
        if st.button("✅ Confirm Trade Success", type="primary", use_container_width=True):
            with st.spinner("Processing and updating trade inventory..."):
                init_give_idx = edited_df[edited_df[card_col] == give].index
                init_rec_idx = edited_df[edited_df[card_col] == rec].index

                init_had_before = int(edited_df.loc[init_rec_idx, init].values[0]) if not init_rec_idx.empty else 0
                part_had_before = int(edited_df.loc[init_give_idx, part].values[0]) if not init_give_idx.empty else 0

                new_cards_gained = 0
                if init_had_before == 0:
                    new_cards_gained += 1
                if part_had_before == 0:
                    new_cards_gained += 1

                if not init_give_idx.empty:
                    edited_df.loc[init_give_idx, init] = max(0, int(edited_df.loc[init_give_idx, init].values[0]) - 1)
                if not init_rec_idx.empty:
                    edited_df.loc[init_rec_idx, init] = int(edited_df.loc[init_rec_idx, init].values[0]) + 1

                if not init_give_idx.empty:
                    edited_df.loc[init_give_idx, part] = int(edited_df.loc[init_give_idx, part].values[0]) + 1
                if not init_rec_idx.empty:
                    edited_df.loc[init_rec_idx, part] = max(0, int(edited_df.loc[init_rec_idx, part].values[0]) - 1)

                sheet_updated = False
                try:
                    client = get_gspread_client()
                    sh = client.open_by_url(target_sheet)
                    ws = sh.get_worksheet(0)
                    
                    clean_df = edited_df.fillna("")
                    ws.update([clean_df.columns.values.tolist()] + clean_df.values.tolist())
                    
                    st.cache_data.clear()
                    sheet_updated = True
                except Exception:
                    st.error("❌ Unable to write inventory updates. Please check connection.")

                if sheet_updated:
                    try:
                        history_sheet_url = st.secrets.get("HISTORY_SHEET_URL")
                        
                        if history_sheet_url:
                            timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                            row_to_append = [
                                timestamp,
                                init,
                                give,
                                rec,
                                part,
                                trade_info['initiated_by'],
                                new_cards_gained
                            ]

                            client = get_gspread_client()
                            sh = client.open_by_url(history_sheet_url)
                            worksheet = sh.get_worksheet(0)

                            headers = ["Timestamp", "Initiator", "Gave Card", "Received Card", "Partner", "Executed By", "New Cards Gained"]
                            existing_rows = worksheet.get_all_values()
                            
                            if not existing_rows:
                                worksheet.append_rows([headers, row_to_append])
                            elif existing_rows[0] != headers:
                                worksheet.insert_row(headers, index=1)
                                worksheet.append_row(row_to_append)
                            else:
                                worksheet.append_row(row_to_append)

                            st.toast("📜 Trade recorded in history log!", icon="📝")

                    except Exception:
                        st.toast("⚠️ Inventory saved, but trade log failed.", icon="⚠️")

                    st.toast("🎉 Trade completed!", icon="✅")
                    st.session_state.active_trade = None
                    st.session_state.stage_2_results = None
                    sol, recs, players, updated_df, card_col = run_optimization(edited_df)
                    st.session_state.stage_1_results = {
                        "sol": sol, "recs": recs, "players": players, "updated_df": updated_df, "card_col": card_col
                    }
                    time.sleep(1.5)
                    st.rerun()

    with btn_col1 if False else btn_col2:
        if st.button("❌ Cancel Trade", type="secondary", use_container_width=True):
            st.info("Trade cancelled.")
            st.session_state.active_trade = None
            st.rerun()

    if time_left <= 0:
        st.warning("⌛ 3-minute confirmation window expired. Trade request ignored.")
        st.session_state.active_trade = None
        st.rerun()
    else:
        time.sleep(1)

# --- 10. BUTTON ACTIONS ---
col_b1, col_b2 = st.columns([1, 4])

with col_b1:
    if st.button("🚀 Calculate Trade Options", type="primary"):
        st.session_state.active_trade = None
        st.session_state.stage_2_results = None
        with st.spinner("Calculating optimal trade sequences..."):
            sol, recs, players, updated_df, card_col = run_optimization(edited_df)
            st.session_state.stage_1_results = {
                "sol": sol, "recs": recs, "players": players, "updated_df": updated_df, "card_col": card_col
            }

# --- 11. DISPLAY STAGED TRADE OPTIONS ---
if (
    st.session_state.stage_1_results is not None
    and st.session_state.active_trade is None
):

    # --- STAGE 1 TRADES ---
    st.divider()
    st.subheader("⚡ Stage 1: Active Trade Sequence")

    sol_s1 = st.session_state.stage_1_results["sol"]

    # --- FIXED: ACCURATE TOP BENEFITED PLAYER CALCULATION ---
    # Only count net new missing cards gained by the Initiator (p1)
    player_gains_s1 = {}

    for trade in sol_s1.get("trades", []):
        p1 = trade.get("Initiator")
        if p1:
            player_gains_s1[str(p1)] = player_gains_s1.get(str(p1), 0) + 1

    top_player_s1 = "None"
    top_gain_s1 = 0
    if player_gains_s1:
        top_player_s1 = max(player_gains_s1, key=player_gains_s1.get)
        top_gain_s1 = player_gains_s1[top_player_s1]

    # --- UI DISPLAY: 4 COLUMNS ---
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Total Trades", len(sol_s1["trades"]))
    m2.metric("Missing Cards Gained", sol_s1["missing"])
    m3.metric("Players Benefited", sol_s1["players"])
    m4.metric(f"🏆 {top_player_s1}", f"+{top_gain_s1} cards")

    st.write("")

    # --- FIXED: RENDER TABLE WITH RECIPIENT OWNERSHIP COLORS ---
    def render_trade_table(sol_data, stage_num, can_initiate=True):
        trades = sol_data["sol"]["trades"]
        if len(trades) == 0:
            st.warning(f"No legal trades available in Stage {stage_num}.")
            return

        h_col1, h_col2, h_col3, h_col4, h_col5, h_col6, h_col7 = st.columns(
            [0.6, 1.2, 1.5, 1.8, 1.8, 1.5, 1.2], vertical_alignment="center"
        )
        h_col1.caption("**Step**")
        h_col2.caption("**Resource**")
        h_col3.caption("**Player**")
        h_col4.caption("**Gives**")
        h_col5.caption("**Receives**")
        h_col6.caption("**From Partner**")
        h_col7.caption("**Action**")

        st.markdown(
            "<hr style='margin: 0px 0px 8px 0px;' />", unsafe_allow_html=True
        )

        card_col_name = sol_data["card_col"]

        for i, trade in enumerate(trades):
            is_first_trade = (i == 0) and can_initiate

            p1 = trade["Initiator"]
            p2 = trade["Partner"]
            give_card = trade["Give"]
            rec_card = trade["Receive"]

            # --- OWNERSHIP CHECK FOR RECIPIENTS OF EACH CARD ---
            give_row = edited_df[edited_df[card_col_name] == give_card]
            rec_row = edited_df[edited_df[card_col_name] == rec_card]

            # P2 (Partner) receives give_card
            p2_give_count = (
                int(give_row[p2].values[0])
                if (
                    not give_row.empty
                    and p2 in give_row.columns
                    and pd.notnull(give_row[p2].values[0])
                )
                else 0
            )

            # P1 (Initiator) receives rec_card
            p1_rec_count = (
                int(rec_row[p1].values[0])
                if (
                    not rec_row.empty
                    and p1 in rec_row.columns
                    and pd.notnull(rec_row[p1].values[0])
                )
                else 0
            )

            # 🟢 Green if recipient owns 0 copies (Unowned)
            # 🟠 Orange if recipient owns >= 1 copy (Duplicate)
            give_badge = (
                f":green-background[**{give_card}**]"
                if p2_give_count == 0
                else f":orange-background[**{give_card}**]"
            )
            rec_badge = (
                f":green-background[**{rec_card}**]"
                if p1_rec_count == 0
                else f":orange-background[**{rec_card}**]"
            )

            r_col1, r_col2, r_col3, r_col4, r_col5, r_col6, r_col7 = st.columns(
                [0.6, 1.2, 1.5, 1.8, 1.8, 1.5, 1.2], vertical_alignment="center"
            )

            with r_col1:
                st.write(f"**#{i+1}**")
            with r_col2:
                st.write(f"`{trade['Type']}`")
            with r_col3:
                st.write(f"**{p1}**")
            with r_col4:
                st.markdown(give_badge)
            with r_col5:
                st.markdown(rec_badge)
            with r_col6:
                st.write(f"**{p2}**")

            with r_col7:
                if is_first_trade:
                    if st.button(
                        "🚀 Initiate",
                        key=f"s{stage_num}_init_btn_{i}",
                        type="primary",
                        use_container_width=True,
                    ):
                        st.session_state.active_trade = {
                            "trade": trade,
                            "initiated_by": st.session_state.player_name,
                            "start_time": time.time(),
                            "card_col": sol_data["card_col"],
                        }
                        st.rerun()
                else:
                    st.button(
                        "🔒 Locked",
                        key=f"s{stage_num}_init_btn_{i}",
                        disabled=True,
                        use_container_width=True,
                    )

    render_trade_table(
        st.session_state.stage_1_results, stage_num=1, can_initiate=True
    )

    # --- UNLOCKABLE RECOMMENDATIONS TABLE ---
    current_recs = (
        st.session_state.stage_2_results["recs"]
        if (
            st.session_state.stage_2_results
            and len(sol_s1["trades"]) > 0
        )
        else st.session_state.stage_1_results["recs"]
    )

    if len(current_recs) > 0:
        st.divider()
        st.subheader("💡 Unlockable Trades (Recommendations)")
        st.info(
            "Acquiring +1 duplicate copy of any card below will unlock multi-player trade chains:"
        )

        recs_df = pd.DataFrame(current_recs)[
            [
                "Player",
                "Target Card",
                "Type",
                "Cards Gained",
                "Players Benefited",
                "Trades Unlocked",
            ]
        ]

        st.dataframe(recs_df, use_container_width=True, hide_index=True)

# --- HISTORICAL TRADE LOGS ---
st.divider()
with st.expander("📜 View Trade History Log", expanded=False):
    st.caption("All confirmed trades logged to the system history:")
    try:
        history_sheet_url = st.secrets.get("HISTORY_SHEET_URL")
        if history_sheet_url:
            client = get_gspread_client()
            sh = client.open_by_url(history_sheet_url)
            worksheet = sh.get_worksheet(0)
            
            all_vals = worksheet.get_all_values()
            
            if len(all_vals) > 1:
                history_df = pd.DataFrame(all_vals[1:], columns=all_vals[0])
                st.dataframe(
                    history_df.iloc[::-1], 
                    use_container_width=True, 
                    hide_index=True
                )
            elif len(all_vals) == 1:
                st.info("No trades recorded yet (headers ready).")
            else:
                st.info("No trade history recorded yet.")
        else:
            st.info("History sheet log not currently configured.")
    except Exception:
        st.info("Trade history is currently unavailable.")