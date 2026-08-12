import streamlit as st
import pandas as pd
from streamlit_gsheets import GSheetsConnection
import gspread
import io
import time
import datetime
import json

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
            # Safely create a copy to avoid altering original secrets dictionary
            clean_creds = dict(creds_dict)
            
            # Format private key safely
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

def fetch_sheet_with_retry(connection, url, retries=3, delay=2):
    for attempt in range(retries):
        try:
            return connection.read(spreadsheet=url, ttl=0, show_spinner=False)
        except Exception as e:
            if attempt < retries - 1:
                time.sleep(delay)
            else:
                raise e

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

# Standard connection call
conn = st.connection("gsheets", type=GSheetsConnection)

if not st.session_state.authenticated:
    st.sidebar.info("Enter your Clan Tag, Player Name, and Password.")
    
    clan_tag_input = st.sidebar.text_input("Clan Tag", value="#CLAN123").strip().upper()
    player_name_input = st.sidebar.text_input("Your Player Name").strip()
    clan_pass_input = st.sidebar.text_input("Password", type="password")

    try:
        registry_df = fetch_sheet_with_retry(conn, MASTER_REGISTRY_URL)
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
                        clan_df = fetch_sheet_with_retry(conn, sheet_url_to_use)
                        
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

# Button column weights set to 0.3 (25% of the original 1.2 width)
col_title, _, col_refresh, col_sheet = st.columns(
    [2.5, 2.8, 0.3, 0.3], 
    vertical_alignment="center"
)

with col_title:
    st.subheader(f"Live Card Inventory Grid — {CLAN_TAG}")

with col_refresh:
    if st.button("🔄 Sync Live Inventory", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

with col_sheet:
    st.link_button(
        "📄 View Inventory Sheet", 
        url="https://docs.google.com/spreadsheets/d/1zkL8HCQgX7TgCKd6skLMfOvHkeRQBvwEFGG-IT2M5PE/edit?pli=1&gid=1125446752#gid=1125446752",
        use_container_width=True
    )

try:
    with st.spinner("Syncing card inventory..."):
        live_df = fetch_sheet_with_retry(conn, st.session_state.sheet_url)
except Exception:
    st.error("⚠️ System temporarily offline. Unable to retrieve live inventory.")
    st.stop()

# --- SIDEBAR ANALYTICAL DASHBOARD ---
card_matches = [c for c in live_df.columns if any(k in str(c).lower() for k in ["card", "troop", "name"])]
card_col = card_matches[0] if card_matches else live_df.columns[0]

type_matches = [c for c in live_df.columns if any(k in str(c).lower() for k in ["type", "resource"])]
type_col = type_matches[0] if type_matches else (live_df.columns[1] if len(live_df.columns) > 1 else live_df.columns[0])

player_cols = [c for c in live_df.columns if c not in [card_col, type_col]]

# 1. Total Trades Done, Non-Duplicate Cards Gained & Top Player (from History Sheet)
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
                gained_val = 1  # Default fallback
                
                if new_idx != -1 and len(r) > new_idx:
                    try:
                        gained_val = int(r[new_idx])
                    except ValueError:
                        pass
                
                cards_gained_count += gained_val
                
                # Attribute gains (split/allocate to initiator primarily)
                if gained_val > 0:
                    player_gains[initiator] = player_gains.get(initiator, 0) + 1
                    if gained_val == 2:  # Both players got a new card
                        player_gains[partner] = player_gains.get(partner, 0) + 1

except Exception:
    pass    

# Determine Top Player
top_player_name = "N/A"
top_player_count = 0

if player_gains:
    top_player_name = max(player_gains, key=player_gains.get)
    top_player_count = player_gains[top_player_name]

# 2. Total Unique Missing Cards (Cards where EVERY player has 0)
total_cards_in_catalog = len(live_df)
unique_missing_cards = 0

for _, row in live_df.iterrows():
    # Only count as missing if EVERY player in player_cols has 0 (or invalid/empty)
    if all((pd.to_numeric(row[p], errors='coerce') or 0) == 0 for p in player_cols):
        unique_missing_cards += 1

# 3. Total Duplicate Cards by Type
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

# Render cleanly into the Sidebar
st.sidebar.divider()
st.sidebar.subheader("📊 Clan Stats")

# Row 1: Trades Done & Cards Gained
row1_col1, row1_col2 = st.sidebar.columns(2)
with row1_col1:
    st.metric(
        "🤝 Trades Done", 
        total_trades_count,
        help="Total number of trades executed and confirmed by clan members."
    )
with row1_col2:
    st.metric(
        "🎉 Cards Gained", 
        cards_gained_count,
        help="Total number of brand-new (previously unowned) cards unlocked by players through trades."
    )

# Row 2: Unique Missing Cards & Top Player Metric
row2_col1, row2_col2 = st.sidebar.columns(2)
with row2_col1:
    st.metric(
        "❌ Unique Missing Cards", 
        f"{unique_missing_cards} / {total_cards_in_catalog}",
        help="Number of cards that NO ONE in the clan owns yet (0/60 means every single card in the game is owned by at least one clan member!)."
    )
with row2_col2:
    st.metric(
        f"🏆 {top_player_name if top_player_count > 0 else 'Top Collector'}", 
        f"{top_player_count}" if top_player_count > 0 else "0",
        help="Player who has unlocked the highest number of brand-new (previously unowned) cards through trading!"
    )

# Collapsible expander open by default
with st.sidebar.expander("📦 Surplus Duplicates Breakdown", expanded=True):
    st.caption("Total extra card copies available for trade across all players:")
    st.write(f"💧 **Elixir:** `{dup_elixir}`")
    st.write(f"🖤 **Dark Elixir:** `{dup_dark_elixir}`")
    st.write(f"🔨 **Builder Base:** `{dup_builder_elixir}`")

# --- MAIN PAGE CONTINUES ---
st.subheader(f"📋 Live Card Inventory Grid — {st.session_state.clan_tag}")
st.write("Double-click any cell to edit numbers directly. Edits will feed into the optimizer.")
edited_df = st.data_editor(live_df, num_rows="dynamic", use_container_width=True, key="live_editor")

# --- 8. ORIGINAL ALGORITHM ENGINE ---
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

    all_cards = sorted(list(catalog.keys()))
    
    inventory = {}
    for p in player_cols:
        inventory[p] = {}
        for _, row in data_df.iterrows():
            val = row[p]
            try:
                inventory[p][str(row[card_col])] = int(val) if pd.notnull(val) else 0
            except:
                inventory[p][str(row[card_col])] = 0

    initial_missing = {p: sum(1 for c in all_cards if inventory[p][c] == 0) for p in player_cols}

    def copy_state(state):
        return {p: state[p].copy() for p in state}

    def get_hash(state):
        return "|".join([f"{p}:" + ",".join(str(state[p][c]) for c in all_cards) for p in sorted(player_cols)])

    def get_score(orig, curr):
        missing, need_score, benefited = 0, 0, 0
        for p in player_cols:
            p_benefited = False
            for c in all_cards:
                if orig[p][c] == 0 and curr[p][c] > 0:
                    missing += 1
                    p_benefited = True
                    super_bonus = 25 if catalog[c]["IsSuper"] else 0
                    need_score += (100 + (initial_missing[p] * 5) + super_bonus)
            if p_benefited: benefited += 1
        
        dups = sum(max(0, curr[p][c] - 1) for p in player_cols for c in all_cards)
        return missing, benefited, (need_score + (benefited * 20) + (dups * 5))

    def get_legal_trades(inv):
        trades = []
        for init in player_cols:
            for part in player_cols:
                if init == part: continue
                for give in all_cards:
                    if inv[init][give] < 2: continue
                    g_info = catalog[give]
                    for rec in all_cards:
                        if inv[init][rec] != 0 or inv[part][rec] < 2: continue
                        r_info = catalog[rec]
                        if g_info["Type"] == r_info["Type"] and g_info["IsSuper"] == r_info["IsSuper"]:
                            trades.append({"Initiator": init, "Partner": part, "Give": give, "Receive": rec, "Type": g_info["Type"]})
        return trades

    memo = {}

    def solve(state):
        h = get_hash(state)
        if h in memo: return memo[h]

        best_trades = []
        m, p, best_score = get_score(inventory, state)
        best_sol = {"trades": best_trades, "state": state, "missing": m, "players": p, "score": best_score}

        for t in get_legal_trades(state):
            nxt = copy_state(state)
            nxt[t["Initiator"]][t["Give"]] -= 1
            nxt[t["Partner"]][t["Give"]] += 1
            nxt[t["Partner"]][t["Receive"]] -= 1
            nxt[t["Initiator"]][t["Receive"]] += 1

            fut = solve(nxt)
            cand_trades = [t] + fut["trades"]
            cm, cp, c_score = get_score(inventory, fut["state"])
            
            if c_score > best_sol["score"] or (c_score == best_sol["score"] and len(cand_trades) < len(best_sol["trades"])):
                best_sol = {"trades": cand_trades, "state": fut["state"], "missing": cm, "players": cp, "score": c_score}

        memo[h] = best_sol
        return best_sol

    sol = solve(inventory)

    recs = []
    if len(sol["trades"]) == 0:
        for p in player_cols:
            for c in all_cards:
                if sol["state"][p][c] == 1:
                    test_s = copy_state(sol["state"])
                    test_s[p][c] += 1
                    memo.clear()
                    sub_sol = solve(test_s)
                    if len(sub_sol["trades"]) > 0:
                        m, pl, sc = get_score(sol["state"], sub_sol["state"])
                        recs.append({
                            "Player": p, "Target Card": c, "Type": catalog[c]["Type"],
                            "Cards Gained": m, "Players Benefited": pl, "Trades Unlocked": len(sub_sol["trades"]), "Score": sc
                        })
        recs = sorted(recs, key=lambda x: x["Score"], reverse=True)

    updated_df = data_df.copy()
    for p in player_cols:
        for idx, row in updated_df.iterrows():
            card_name = str(row[card_col])
            updated_df.at[idx, p] = sol["state"][p].get(card_name, row[p])

    return sol, recs, player_cols, updated_df, card_col

# --- 9. TRADE MONITORING & CONFIRMATION ENGINE ---
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

                # --- CHECK IF GAINED CARDS ARE NEW (NON-DUPLICATES) ---
                init_had_before = int(edited_df.loc[init_rec_idx, init].values[0]) if not init_rec_idx.empty else 0
                part_had_before = int(edited_df.loc[init_give_idx, part].values[0]) if not init_give_idx.empty else 0

                new_cards_gained = 0
                if init_had_before == 0:
                    new_cards_gained += 1
                if part_had_before == 0:
                    new_cards_gained += 1

                # Update local dataframe values
                if not init_give_idx.empty:
                    edited_df.loc[init_give_idx, init] = max(0, int(edited_df.loc[init_give_idx, init].values[0]) - 1)
                if not init_rec_idx.empty:
                    edited_df.loc[init_rec_idx, init] = int(edited_df.loc[init_rec_idx, init].values[0]) + 1

                if not init_give_idx.empty:
                    edited_df.loc[init_give_idx, part] = int(edited_df.loc[init_give_idx, part].values[0]) + 1
                if not init_rec_idx.empty:
                    edited_df.loc[init_rec_idx, part] = max(0, int(edited_df.loc[init_rec_idx, part].values[0]) - 1)

                # Write updated inventory to Google Sheet
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

                # Append to history sheet with non-duplicate card count
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
                                new_cards_gained  # Logs 1 or 2 if non-duplicate cards were gained
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

                    except Exception as e:
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

    with btn_col2:
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
        st.rerun()

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

# --- 11. DISPLAY TRADE OPTIONS ---
if st.session_state.stage_1_results is not None and st.session_state.active_trade is None:
    
    def render_trade_table(sol_data, stage_num, can_initiate=True):
        trades = sol_data["sol"]["trades"]
        if len(trades) == 0:
            st.warning(f"No legal trades available in Stage {stage_num}.")
            return

        h_col1, h_col2, h_col3, h_col4, h_col5, h_col6, h_col7 = st.columns(
            [0.6, 1.2, 1.5, 1.5, 1.5, 1.5, 1.2], vertical_alignment="center"
        )
        h_col1.caption("**Step**")
        h_col2.caption("**Resource**")
        h_col3.caption("**Player**")
        h_col4.caption("**🔴 Gives**")
        h_col5.caption("**🟢 Receives**")
        h_col6.caption("**From Partner**")
        h_col7.caption("**Action**")

        st.markdown("<hr style='margin: 0px 0px 8px 0px;' />", unsafe_allow_html=True)

        for i, trade in enumerate(trades):
            is_first_trade = (i == 0) and can_initiate

            r_col1, r_col2, r_col3, r_col4, r_col5, r_col6, r_col7 = st.columns(
                [0.6, 1.2, 1.5, 1.5, 1.5, 1.5, 1.2], vertical_alignment="center"
            )

            with r_col1:
                st.write(f"**#{i+1}**")
            with r_col2:
                st.write(f"`{trade['Type']}`")
            with r_col3:
                st.write(f"**{trade['Initiator']}**")
            with r_col4:
                st.write(f"{trade['Give']}")
            with r_col5:
                st.write(f"**{trade['Receive']}**")
            with r_col6:
                st.write(f"{trade['Partner']}")

            with r_col7:
                if is_first_trade:
                    if st.button("🚀 Initiate", key=f"s{stage_num}_init_btn_{i}", type="primary", use_container_width=True):
                        st.session_state.active_trade = {
                            "trade": trade,
                            "initiated_by": st.session_state.player_name,
                            "start_time": time.time(),
                            "card_col": sol_data["card_col"]
                        }
                        st.rerun()
                else:
                    st.button("🔒 Locked", key=f"s{stage_num}_init_btn_{i}", disabled=True, use_container_width=True)

    # --- STAGE 1 TRADES ---
    st.divider()
    st.subheader("⚡ Stage 1: Active Trade Sequence")

    sol_s1 = st.session_state.stage_1_results["sol"]
    m1, m2, m3 = st.columns(3)
    m1.metric("Total Trades", len(sol_s1["trades"]))
    m2.metric("Missing Cards Gained", sol_s1["missing"])
    m3.metric("Players Benefited", sol_s1["players"])

    st.write("")
    render_trade_table(st.session_state.stage_1_results, stage_num=1, can_initiate=True)

    # --- STAGE 2 TRADES ---
    if len(sol_s1["trades"]) > 0:
        st.divider()
        if st.session_state.stage_2_results is None:
            st.subheader("🔄 Future Projection: Stage 2")
            st.caption("Calculate downstream options based on projected inventory after Stage 1 finishes.")
            
            if st.button("⚡ Run Stage 2 Optimization", type="secondary"):
                with st.spinner("Calculating Stage 2 optimization..."):
                    updated_df_s1 = st.session_state.stage_1_results["updated_df"]
                    sol_s2, recs_s2, players_s2, updated_df_s2, card_col_s2 = run_optimization(updated_df_s1)
                    
                    st.session_state.stage_2_results = {
                        "sol": sol_s2, 
                        "recs": recs_s2, 
                        "players": players_s2, 
                        "updated_df": updated_df_s2, 
                        "card_col": card_col_s2
                    }
                    st.rerun()
        else:
            st.subheader("🔮 Stage 2: Projected Follow-Up Trades")
            st.caption("These trades unlock *after* all Stage 1 trades are completed.")
            
            sol_s2 = st.session_state.stage_2_results["sol"]
            s2_m1, s2_m2, s2_m3 = st.columns(3)
            s2_m1.metric("Stage 2 Trades", len(sol_s2["trades"]))
            s2_m2.metric("Additional Cards Gained", sol_s2["missing"])
            s2_m3.metric("Players Benefited", sol_s2["players"])
            
            st.write("")
            render_trade_table(st.session_state.stage_2_results, stage_num=2, can_initiate=False)

    # --- UNLOCKABLE RECOMMENDATIONS ---
    current_recs = st.session_state.stage_2_results["recs"] if (st.session_state.stage_2_results and len(sol_s1["trades"]) > 0) else st.session_state.stage_1_results["recs"]
    
    if len(current_recs) > 0:
        st.divider()
        st.subheader("💡 Unlockable Trades (Recommendations)")
        st.info("Acquiring +1 duplicate copy of any card below will unlock multi-player trade chains:")
        st.dataframe(
            pd.DataFrame(current_recs)[["Player", "Target Card", "Type", "Cards Gained", "Players Benefited", "Trades Unlocked"]], 
            use_container_width=True,
            hide_index=True
        )

# --- 12. HISTORICAL TRADE LOGS ---
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
                # Row 0 is header, remaining are records
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