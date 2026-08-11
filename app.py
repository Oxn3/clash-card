import streamlit as st
import pandas as pd
import io

# Set Page Config
st.set_page_config(page_title="Clash Trade Optimizer", layout="wide", page_icon="⚔️")

st.title("⚔️ Clash Cards Trade Optimizer")
st.write("Enter troop counts for your clan members below, or upload an existing Excel file, then click **Optimize Trades**!")

# --- Initial Default Data Generator ---
DEFAULT_CARDS = [
    ("Barbarian", "Common", False),
    ("Archer", "Common", False),
    ("Giant", "Rare", False),
    ("Wizard", "Rare", False),
    ("Pekka", "Epic", False),
    ("Super Barbarian", "Common", True),
    ("Super Wizard", "Rare", True),
]

def get_default_df():
    data = {"Card": [c[0] for c in DEFAULT_CARDS], "Type": [c[1] for c in DEFAULT_CARDS]}
    # Default 3 players
    data["Player_1"] = [2, 0, 1, 0, 0, 1, 0]
    data["Player_2"] = [0, 2, 0, 1, 0, 0, 0]
    data["Player_3"] = [0, 0, 0, 0, 2, 0, 1]
    return pd.DataFrame(data)

# --- Sidebar Controls ---
st.sidebar.header("Data Options")
uploaded_file = st.sidebar.file_uploader("Upload Excel File (.xlsx)", type=["xlsx"])

if uploaded_file:
    df = pd.read_excel(uploaded_file)
else:
    df = get_default_df()

st.subheader("📋 Card Inventory Grid")
st.write("Double-click any cell to edit numbers directly. Add columns for more players!")
edited_df = st.data_editor(df, num_rows="dynamic", use_container_width=True)

# --- Algorithm Engine ---
def run_optimization(data_df):
    # Robust Column Detection with Fallbacks
    card_matches = [c for c in data_df.columns if any(k in str(c).lower() for k in ["card", "troop", "name"])]
    card_col = card_matches[0] if card_matches else data_df.columns[0]

    type_matches = [c for c in data_df.columns if "type" in str(c).lower()]
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

    # Calculate need priority
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

    # Recommendations Engine
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

    # Build Updated DataFrame for Excel Export
    updated_df = data_df.copy()
    for p in player_cols:
        for idx, row in updated_df.iterrows():
            card_name = str(row[card_col])
            updated_df.at[idx, p] = sol["state"][p].get(card_name, row[p])

    return sol, recs, player_cols, updated_df

# Helper function to convert dataframe to downloadable Excel bytes
def to_excel_bytes(df_to_export):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df_to_export.to_excel(writer, index=False, sheet_name='Updated_Inventory')
    return output.getvalue()

# --- Run Action ---
if st.button("🚀 Optimize Trades", type="primary"):
    with st.spinner("Calculating optimal multi-player trade chains..."):
        sol, recs, players, updated_inventory_df = run_optimization(edited_df)

    st.divider()
    st.header("📊 Results Summary")
    
    col1, col2, col3 = st.columns(3)
    col1.metric("Trades Executed", len(sol["trades"]))
    col2.metric("Missing Cards Gained", sol["missing"])
    col3.metric("Players Benefited", sol["players"])

    st.divider()

    # --- Excel Download Section ---
    st.subheader("📥 Download Updated Inventory")
    st.write("Click below to download the updated Excel file reflecting card totals after all trades are executed:")
    
    excel_data = to_excel_bytes(updated_inventory_df)
    st.download_button(
        label="💾 Download Updated Workbook (.xlsx)",
        data=excel_data,
        file_name="Clash_Cards_Updated_Inventory.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

    st.divider()

    if len(sol["trades"]) > 0:
        st.subheader("📋 Executed Trade Breakdown Table")
        st.dataframe(pd.DataFrame(sol["trades"]), use_container_width=True)

    else:
        st.warning("No legal trades could be made with current card counts.")

    if len(recs) > 0:
        st.subheader("💡 Recommendations to Unlock Trades")
        st.info("Acquiring +1 duplicate copy of any card below will unlock multi-player trade chains:")
        st.dataframe(pd.DataFrame(recs)[["Player", "Target Card", "Type", "Cards Gained", "Players Benefited", "Trades Unlocked"]], use_container_width=True)