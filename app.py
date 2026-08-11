import streamlit as st
import pandas as pd
import io

# Set Page Config
st.set_page_config(page_title="Clash Trade Optimizer", layout="wide", page_icon="⚔️")

st.title("⚔️ Clash Cards Trade Optimizer")
st.write("Enter troop counts for your clan members below, or upload an existing Excel file, then click **Optimize Trades**!")

# --- Initialize Session State for Multi-Stage Optimization ---
if "optimization_history" not in st.session_state:
    st.session_state.optimization_history = []

# --- Initial Default Data Generator matching Template ---
TEMPLATE_DATA = [
    {"Troop Name": "Raged Barbarian", "Upgrade Resource": "Builder Elixir", "Eludidator": 1, "Lambent Light": 0, "Night Sky": 1, "Dark Repulser": 0},
    {"Troop Name": "Sneaky Archer", "Upgrade Resource": "Builder Elixir", "Eludidator": 1, "Lambent Light": 1, "Night Sky": 0, "Dark Repulser": 1},
    {"Troop Name": "Boxer Giant", "Upgrade Resource": "Builder Elixir", "Eludidator": 2, "Lambent Light": 0, "Night Sky": 0, "Dark Repulser": 2},
    {"Troop Name": "Beta Minion", "Upgrade Resource": "Builder Elixir", "Eludidator": 0, "Lambent Light": 1, "Night Sky": 1, "Dark Repulser": 1},
    {"Troop Name": "Bomber", "Upgrade Resource": "Builder Elixir", "Eludidator": 0, "Lambent Light": 1, "Night Sky": 1, "Dark Repulser": 0},
    {"Troop Name": "Baby Dragon (Builder Base)", "Upgrade Resource": "Builder Elixir", "Eludidator": 0, "Lambent Light": 0, "Night Sky": 2, "Dark Repulser": 0},
    {"Troop Name": "Cannon Cart", "Upgrade Resource": "Builder Elixir", "Eludidator": 1, "Lambent Light": 0, "Night Sky": 1, "Dark Repulser": 1},
    {"Troop Name": "Night Witch", "Upgrade Resource": "Builder Elixir", "Eludidator": 0, "Lambent Light": 1, "Night Sky": 1, "Dark Repulser": 0},
    {"Troop Name": "Drop Ship", "Upgrade Resource": "Builder Elixir", "Eludidator": 1, "Lambent Light": 0, "Night Sky": 1, "Dark Repulser": 1},
    {"Troop Name": "Power P.E.K.K.A", "Upgrade Resource": "Builder Elixir", "Eludidator": 1, "Lambent Light": 0, "Night Sky": 0, "Dark Repulser": 1},
    {"Troop Name": "Hog Glider", "Upgrade Resource": "Builder Elixir", "Eludidator": 0, "Lambent Light": 1, "Night Sky": 0, "Dark Repulser": 0},
    {"Troop Name": "Minion", "Upgrade Resource": "Dark Elixir", "Eludidator": 1, "Lambent Light": 1, "Night Sky": 1, "Dark Repulser": 1},
    {"Troop Name": "Hog Rider", "Upgrade Resource": "Dark Elixir", "Eludidator": 1, "Lambent Light": 2, "Night Sky": 1, "Dark Repulser": 1},
    {"Troop Name": "Valkyrie", "Upgrade Resource": "Dark Elixir", "Eludidator": 0, "Lambent Light": 1, "Night Sky": 1, "Dark Repulser": 1},
    {"Troop Name": "Golem", "Upgrade Resource": "Dark Elixir", "Eludidator": 0, "Lambent Light": 0, "Night Sky": 1, "Dark Repulser": 1},
    {"Troop Name": "Witch", "Upgrade Resource": "Dark Elixir", "Eludidator": 1, "Lambent Light": 2, "Night Sky": 2, "Dark Repulser": 1},
    {"Troop Name": "Lava Hound", "Upgrade Resource": "Dark Elixir", "Eludidator": 0, "Lambent Light": 1, "Night Sky": 2, "Dark Repulser": 1},
    {"Troop Name": "Bowler", "Upgrade Resource": "Dark Elixir", "Eludidator": 2, "Lambent Light": 1, "Night Sky": 1, "Dark Repulser": 0},
    {"Troop Name": "Ice Golem", "Upgrade Resource": "Dark Elixir", "Eludidator": 1, "Lambent Light": 0, "Night Sky": 0, "Dark Repulser": 1},
    {"Troop Name": "Headhunter", "Upgrade Resource": "Dark Elixir", "Eludidator": 1, "Lambent Light": 1, "Night Sky": 1, "Dark Repulser": 0},
    {"Troop Name": "Apprentice Warden", "Upgrade Resource": "Dark Elixir", "Eludidator": 1, "Lambent Light": 0, "Night Sky": 1, "Dark Repulser": 0},
    {"Troop Name": "Druid", "Upgrade Resource": "Dark Elixir", "Eludidator": 1, "Lambent Light": 1, "Night Sky": 0, "Dark Repulser": 1},
    {"Troop Name": "Furnace", "Upgrade Resource": "Dark Elixir", "Eludidator": 0, "Lambent Light": 0, "Night Sky": 1, "Dark Repulser": 0},
    {"Troop Name": "Ruin Witch", "Upgrade Resource": "Dark Elixir", "Eludidator": 1, "Lambent Light": 0, "Night Sky": 1, "Dark Repulser": 2},
    {"Troop Name": "Super Minion", "Upgrade Resource": "Dark Elixir", "Eludidator": 0, "Lambent Light": 0, "Night Sky": 1, "Dark Repulser": 1},
    {"Troop Name": "Super Valkyrie", "Upgrade Resource": "Dark Elixir", "Eludidator": 1, "Lambent Light": 1, "Night Sky": 0, "Dark Repulser": 1},
    {"Troop Name": "Super Witch", "Upgrade Resource": "Dark Elixir", "Eludidator": 1, "Lambent Light": 0, "Night Sky": 1, "Dark Repulser": 1},
    {"Troop Name": "Ice Hound", "Upgrade Resource": "Dark Elixir", "Eludidator": 0, "Lambent Light": 0, "Night Sky": 1, "Dark Repulser": 0},
    {"Troop Name": "Super Bowler", "Upgrade Resource": "Dark Elixir", "Eludidator": 0, "Lambent Light": 0, "Night Sky": 0, "Dark Repulser": 0},
    {"Troop Name": "Super Hog Rider", "Upgrade Resource": "Dark Elixir", "Eludidator": 0, "Lambent Light": 1, "Night Sky": 1, "Dark Repulser": 0},
    {"Troop Name": "Barbarian", "Upgrade Resource": "Elixir", "Eludidator": 1, "Lambent Light": 2, "Night Sky": 1, "Dark Repulser": 1},
    {"Troop Name": "Archer", "Upgrade Resource": "Elixir", "Eludidator": 1, "Lambent Light": 1, "Night Sky": 1, "Dark Repulser": 1},
    {"Troop Name": "Giant", "Upgrade Resource": "Elixir", "Eludidator": 1, "Lambent Light": 1, "Night Sky": 1, "Dark Repulser": 1},
    {"Troop Name": "Goblin", "Upgrade Resource": "Elixir", "Eludidator": 0, "Lambent Light": 1, "Night Sky": 0, "Dark Repulser": 0},
    {"Troop Name": "Wall Breaker", "Upgrade Resource": "Elixir", "Eludidator": 1, "Lambent Light": 1, "Night Sky": 1, "Dark Repulser": 2},
    {"Troop Name": "Balloon", "Upgrade Resource": "Elixir", "Eludidator": 2, "Lambent Light": 1, "Night Sky": 1, "Dark Repulser": 0},
    {"Troop Name": "Wizard", "Upgrade Resource": "Elixir", "Eludidator": 1, "Lambent Light": 1, "Night Sky": 0, "Dark Repulser": 0},
    {"Troop Name": "Healer", "Upgrade Resource": "Elixir", "Eludidator": 1, "Lambent Light": 1, "Night Sky": 0, "Dark Repulser": 0},
    {"Troop Name": "Dragon", "Upgrade Resource": "Elixir", "Eludidator": 1, "Lambent Light": 1, "Night Sky": 1, "Dark Repulser": 0},
    {"Troop Name": "P.E.K.K.A", "Upgrade Resource": "Elixir", "Eludidator": 1, "Lambent Light": 1, "Night Sky": 0, "Dark Repulser": 1},
    {"Troop Name": "Baby Dragon", "Upgrade Resource": "Elixir", "Eludidator": 0, "Lambent Light": 1, "Night Sky": 0, "Dark Repulser": 1},
    {"Troop Name": "Miner", "Upgrade Resource": "Elixir", "Eludidator": 0, "Lambent Light": 1, "Night Sky": 1, "Dark Repulser": 1},
    {"Troop Name": "Electro Dragon", "Upgrade Resource": "Elixir", "Eludidator": 1, "Lambent Light": 1, "Night Sky": 1, "Dark Repulser": 0},
    {"Troop Name": "Yeti", "Upgrade Resource": "Elixir", "Eludidator": 1, "Lambent Light": 1, "Night Sky": 1, "Dark Repulser": 1},
    {"Troop Name": "Dragon Rider", "Upgrade Resource": "Elixir", "Eludidator": 1, "Lambent Light": 1, "Night Sky": 1, "Dark Repulser": 1},
    {"Troop Name": "Electro Titan", "Upgrade Resource": "Elixir", "Eludidator": 2, "Lambent Light": 1, "Night Sky": 1, "Dark Repulser": 2},
    {"Troop Name": "Root Rider", "Upgrade Resource": "Elixir", "Eludidator": 1, "Lambent Light": 2, "Night Sky": 3, "Dark Repulser": 2},
    {"Troop Name": "Thrower", "Upgrade Resource": "Elixir", "Eludidator": 1, "Lambent Light": 0, "Night Sky": 0, "Dark Repulser": 2},
    {"Troop Name": "Meteor Golem", "Upgrade Resource": "Elixir", "Eludidator": 2, "Lambent Light": 1, "Night Sky": 2, "Dark Repulser": 1},
    {"Troop Name": "Super Barbarian", "Upgrade Resource": "Elixir", "Eludidator": 1, "Lambent Light": 0, "Night Sky": 0, "Dark Repulser": 0},
    {"Troop Name": "Super Archer", "Upgrade Resource": "Elixir", "Eludidator": 1, "Lambent Light": 1, "Night Sky": 1, "Dark Repulser": 1},
    {"Troop Name": "Super Giant", "Upgrade Resource": "Elixir", "Eludidator": 1, "Lambent Light": 1, "Night Sky": 0, "Dark Repulser": 1},
    {"Troop Name": "Sneaky Goblin", "Upgrade Resource": "Elixir", "Eludidator": 1, "Lambent Light": 0, "Night Sky": 0, "Dark Repulser": 0},
    {"Troop Name": "Super Wall Breaker", "Upgrade Resource": "Elixir", "Eludidator": 0, "Lambent Light": 0, "Night Sky": 1, "Dark Repulser": 0},
    {"Troop Name": "Rocket Balloon", "Upgrade Resource": "Elixir", "Eludidator": 1, "Lambent Light": 0, "Night Sky": 0, "Dark Repulser": 0},
    {"Troop Name": "Super Wizard", "Upgrade Resource": "Elixir", "Eludidator": 1, "Lambent Light": 1, "Night Sky": 0, "Dark Repulser": 0},
    {"Troop Name": "Super Dragon", "Upgrade Resource": "Elixir", "Eludidator": 1, "Lambent Light": 0, "Night Sky": 0, "Dark Repulser": 0},
    {"Troop Name": "Inferno Dragon", "Upgrade Resource": "Elixir", "Eludidator": 0, "Lambent Light": 1, "Night Sky": 0, "Dark Repulser": 1},
    {"Troop Name": "Super Miner", "Upgrade Resource": "Elixir", "Eludidator": 0, "Lambent Light": 1, "Night Sky": 1, "Dark Repulser": 0},
    {"Troop Name": "Super Yeti", "Upgrade Resource": "Elixir", "Eludidator": 1, "Lambent Light": 0, "Night Sky": 0, "Dark Repulser": 2}
]

def get_default_df():
    return pd.DataFrame(TEMPLATE_DATA)

# Helper function to convert dataframe to downloadable Excel bytes
def to_excel_bytes(df_to_export, sheet_name='Sheet1'):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df_to_export.to_excel(writer, index=False, sheet_name=sheet_name)
    return output.getvalue()

# --- Sidebar Controls ---
st.sidebar.header("Data Options")

# 📥 Download Sample Excel Template
sample_df = get_default_df()
sample_excel_data = to_excel_bytes(sample_df, sheet_name='Card_Inventory')

st.sidebar.subheader("📄 Need a template?")
st.sidebar.download_button(
    label="📄 Download Sample Excel (.xlsx)",
    data=sample_excel_data,
    file_name="Clash_Cards_Sample_Template.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)

st.sidebar.divider()

# 📤 Upload Excel File
st.sidebar.subheader("📤 Upload Data")
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

# --- Button Actions ---
col_b1, col_b2 = st.columns([1, 4])

with col_b1:
    if st.button("🚀 Optimize Initial Trades", type="primary"):
        st.session_state.optimization_history = []  # Reset history
        with st.spinner("Calculating initial optimal trade chains..."):
            sol, recs, players, updated_df = run_optimization(edited_df)
            st.session_state.optimization_history.append({
                "stage": 1,
                "sol": sol,
                "recs": recs,
                "players": players,
                "updated_df": updated_df
            })

# --- Display All Stages sequentially ---
if len(st.session_state.optimization_history) > 0:
    for idx, stage_data in enumerate(st.session_state.optimization_history):
        stage_num = stage_data["stage"]
        sol = stage_data["sol"]
        recs = stage_data["recs"]
        updated_df = stage_data["updated_df"]

        st.divider()
        st.header(f"📊 Results Stage {stage_num}")
        
        c1, c2, c3 = st.columns(3)
        c1.metric("Trades Executed", len(sol["trades"]))
        c2.metric("Missing Cards Gained", sol["missing"])
        c3.metric("Players Benefited", sol["players"])

        st.divider()

        # Excel Download for this stage
        st.subheader(f"📥 Download Stage {stage_num} Updated Inventory")
        excel_data = to_excel_bytes(updated_df, sheet_name=f'Stage_{stage_num}_Inventory')
        st.download_button(
            label=f"💾 Download Stage {stage_num} Inventory (.xlsx)",
            data=excel_data,
            file_name=f"Clash_Cards_Stage_{stage_num}_Inventory.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key=f"dl_btn_{stage_num}"
        )

        st.divider()

        if len(sol["trades"]) > 0:
            st.subheader(f"📋 Executed Trade Breakdown (Stage {stage_num})")
            st.dataframe(pd.DataFrame(sol["trades"]), use_container_width=True)
        else:
            st.warning(f"No further legal trades could be made in Stage {stage_num}.")

        if len(recs) > 0:
            st.subheader(f"💡 Recommendations to Unlock Further Trades (Stage {stage_num})")
            st.info("Acquiring +1 duplicate copy of any card below will unlock multi-player trade chains:")
            st.dataframe(pd.DataFrame(recs)[["Player", "Target Card", "Type", "Cards Gained", "Players Benefited", "Trades Unlocked"]], use_container_width=True)

        # Show option to run NEXT stage using the updated inventory from THIS stage
        if idx == len(st.session_state.optimization_history) - 1:
            st.divider()
            st.subheader(f"🔄 Next Optimization Stage")
            st.write(f"Want to perform another optimization round starting with the **Stage {stage_num} updated inventory**?")
            
            if st.button(f"⚡ Optimize Stage {stage_num + 1} (Use Stage {stage_num} Updated Inventory)", key=f"next_stage_btn_{stage_num}"):
                with st.spinner(f"Calculating Stage {stage_num + 1} trades..."):
                    next_sol, next_recs, next_players, next_updated_df = run_optimization(updated_df)
                    st.session_state.optimization_history.append({
                        "stage": stage_num + 1,
                        "sol": next_sol,
                        "recs": next_recs,
                        "players": next_players,
                        "updated_df": next_updated_df
                    })
                    st.rerun()