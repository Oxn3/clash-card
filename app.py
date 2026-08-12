import streamlit as st
import pandas as pd
from streamlit_gsheets import GSheetsConnection
import io
import time
import datetime

# --- 1. PAGE SETUP ---
st.set_page_config(page_title="Clash Trade Optimizer", layout="wide", page_icon="⚔️")

st.title("⚔️ Clash Cards Trade Optimizer")

# --- 2. CONFIGURATION: MASTER CLAN REGISTRY URL ---
try:
    MASTER_REGISTRY_URL = st.secrets["MASTER_REGISTRY_URL"]
except Exception:
    st.error("⚠️ MASTER_REGISTRY_URL missing in .streamlit/secrets.toml!")
    st.stop()

# --- 3. SESSION STATE INITIALIZATION ---
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

# --- 4. HELPER FUNCTIONS ---
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
            return connection.read(spreadsheet=url, ttl=0)
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

# --- 5. SIDEBAR: AUTHENTICATION ENGINE ---
st.sidebar.header("🔑 Clan Portal")

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
        st.sidebar.caption("Need a starting sheet? Download our template spreadsheet, upload it to your Google Drive as a Google Sheet, set sharing to 'Anyone with link can edit', and paste the URL below.")
        
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
                        new_row = pd.DataFrame([{
                            "Clan Tag": clan_tag_input,
                            "Password": clan_pass_input,
                            "Sheet URL": clan_url_input
                        }])
                        updated_registry = pd.concat([registry_df, new_row], ignore_index=True)
                        conn.update(spreadsheet=MASTER_REGISTRY_URL, data=updated_registry)
                        
                        credentials_valid = True
                        sheet_url_to_use = clan_url_input

                if credentials_valid and sheet_url_to_use:
                    with st.spinner("Validating Player Name and Inventory Data..."):
                        clan_df = fetch_sheet_with_retry(conn, sheet_url_to_use)
                        
                        card_matches = [c for c in clan_df.columns if any(k in str(c).lower() for k in ["card", "troop", "name"])]
                        card_col = card_matches[0] if card_matches else clan_df.columns[0]
                        type_matches = [c for c in clan_df.columns if any(k in str(c).lower() for k in ["type", "resource"])]
                        type_col = type_matches[0] if type_matches else (clan_df.columns[1] if len(clan_df.columns) > 1 else clan_df.columns[0])
                        
                        player_cols = [str(c).strip() for c in clan_df.columns if c not in [card_col, type_col]]
                        recorded_names_lower = [p.lower() for p in player_cols]

                        if player_name_input.lower() not in recorded_names_lower:
                            st.sidebar.error(f"❌ Player **'{player_name_input}'** not found in sheet headers!")
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

            except Exception as e:
                st.sidebar.error(f"Error accessing Google Sheets: {e}")

    st.warning("⚠️ Please log in via sidebar to access your clan sheet.")
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

# --- 6. SAFE REFRESH & LIVE DATA LOAD ---
col_refresh, _ = st.columns([1, 4])
with col_refresh:
    if st.button("🔄 Sync Live Sheet Data"):
        st.rerun()

try:
    live_df = fetch_sheet_with_retry(conn, st.session_state.sheet_url)
except Exception as e:
    st.error(f"⚠️ Google Sheets server is temporarily unreachable. Details: {e}")
    st.stop()

st.subheader(f"📋 Live Card Inventory Grid — {st.session_state.clan_tag}")
st.write("Double-click any cell to edit numbers directly. Edits will feed into the optimizer.")
edited_df = st.data_editor(live_df, num_rows="dynamic", use_container_width=True, key="live_editor")

# --- 7. ORIGINAL ALGORITHM ENGINE ---
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

import datetime

# --- 8. TRADE MONITORING & CONFIRMATION ENGINE ---
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

    # Target spreadsheet URL from session_state or secrets
    target_sheet = st.session_state.get("sheet_url") or st.secrets.get("MASTER_REGISTRY_URL")

    st.divider()
    st.warning(f"⏳ **Active Trade Action Required** (Initiated by: **{trade_info['initiated_by']}**)")
    
    col_t1, col_t2 = st.columns([3, 1])
    col_t1.markdown(f"**Trade in Progress:** 👤 `{init}` gives **{give}** ➡️ receives **{rec}** from 👤 `{part}`")
    
    mins, secs = divmod(time_left, 60)
    col_t2.metric("Time Remaining", f"{mins:02d}:{secs:02d}")

    # Action Buttons: Confirm vs Cancel
    btn_col1, btn_col2, _ = st.columns([1.5, 1.5, 3])
    
    with btn_col1:
        if st.button("✅ Confirm Trade Success", type="primary", use_container_width=True):
            with st.spinner("Updating Google Sheet & recording history..."):
                # 1. Update inventory in local dataframe
                init_give_idx = edited_df[edited_df[card_col] == give].index
                init_rec_idx = edited_df[edited_df[card_col] == rec].index
                
                if not init_give_idx.empty:
                    edited_df.loc[init_give_idx, init] = max(0, int(edited_df.loc[init_give_idx, init].values[0]) - 1)
                if not init_rec_idx.empty:
                    edited_df.loc[init_rec_idx, init] = int(edited_df.loc[init_rec_idx, init].values[0]) + 1

                if not init_give_idx.empty:
                    edited_df.loc[init_give_idx, part] = int(edited_df.loc[init_give_idx, part].values[0]) + 1
                if not init_rec_idx.empty:
                    edited_df.loc[init_rec_idx, part] = max(0, int(edited_df.loc[init_rec_idx, part].values[0]) - 1)

                # 2. Write updated inventory dataframe back to Google Sheet
                sheet_updated = False
                try:
                    conn.update(spreadsheet=target_sheet, worksheet="Sheet1", data=edited_df)
                    st.cache_data.clear()
                    sheet_updated = True
                except Exception as e:
                    try:
                        conn.update(spreadsheet=target_sheet, data=edited_df)
                        st.cache_data.clear()
                        sheet_updated = True
                    except Exception as err:
                        st.error(f"❌ Failed to write inventory to Google Sheet: {err}")

                # 3. Append historical trade log row into separate 'Clan Trade History Log' Google Sheet
                if sheet_updated:
                    try:
                        history_sheet_url = st.secrets.get("HISTORY_SHEET_URL") or "YOUR_NEW_SHEET_URL_HERE"
                        
                        new_log_row = pd.DataFrame([{
                            "Timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            "Initiator": init,
                            "Gave Card": give,
                            "Received Card": rec,
                            "Partner": part,
                            "Executed By": trade_info['initiated_by']
                        }])

                        # Read existing rows from the separate sheet file
                        try:
                            history_df = conn.read(spreadsheet=history_sheet_url, ttl=0)
                            if history_df is not None and not history_df.empty:
                                updated_history = pd.concat([history_df, new_log_row], ignore_index=True)
                            else:
                                updated_history = new_log_row
                        except Exception:
                            updated_history = new_log_row

                        # Write to the dedicated history sheet
                        conn.update(spreadsheet=history_sheet_url, data=updated_history)
                        st.toast("📜 Trade logged to History Sheet!", icon="📝")

                    except Exception as log_err:
                        # Log notice without failing the main trade confirmation
                        st.toast(f"⚠️ Inventory saved, but separate history log skipped: {log_err}", icon="⚠️")

                    # 4. Reset state and re-optimize
                    st.toast("🎉 Trade completed & logged to history!", icon="✅")
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

    # Timeout handling (3 mins)
    if time_left <= 0:
        st.warning("⌛ 3-minute confirmation window expired. Trade request ignored.")
        st.session_state.active_trade = None
        st.rerun()
    else:
        time.sleep(1)
        st.rerun()

# --- 9. BUTTON ACTIONS ---
col_b1, col_b2 = st.columns([1, 4])

with col_b1:
    if st.button("🚀 Calculate Trade Options", type="primary"):
        st.session_state.active_trade = None
        st.session_state.stage_2_results = None
        with st.spinner("Calculating optimal trade chains..."):
            sol, recs, players, updated_df, card_col = run_optimization(edited_df)
            st.session_state.stage_1_results = {
                "sol": sol, "recs": recs, "players": players, "updated_df": updated_df, "card_col": card_col
            }

# --- 10. DISPLAY TRADE OPTIONS ---
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

    # --- STAGE 2 TRADES (ONLY SHOW IF STAGE 1 HAS TRADES) ---
    if len(sol_s1["trades"]) > 0:
        st.divider()
        if st.session_state.stage_2_results is None:
            st.subheader("🔄 Future Projection: Stage 2")
            st.caption("Calculate downstream options based on projected inventory after Stage 1 finishes.")
            
            if st.button("⚡ Run Stage 2 Optimization", type="secondary"):
                with st.spinner("Calculating Stage 2 optimization on projected inventory..."):
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

# --- 11. HISTORICAL TRADE LOGS ---
st.divider()
with st.expander("📜 View Trade History Log", expanded=False):
    st.caption("All confirmed trades logged to the dedicated Trade History Sheet:")
    try:
        history_sheet_url = st.secrets.get("HISTORY_SHEET_URL") or "YOUR_NEW_SHEET_URL_HERE"
        history_data = conn.read(spreadsheet=history_sheet_url, ttl=10)
        
        if history_data is not None and not history_data.empty:
            st.dataframe(
                history_data.iloc[::-1], 
                use_container_width=True, 
                hide_index=True
            )
        else:
            st.info("No trade history recorded yet.")
    except Exception as e:
        st.info("Connect a valid HISTORY_SHEET_URL to view past trade history.")