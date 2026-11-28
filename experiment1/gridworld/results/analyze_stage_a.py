import json, statistics as st, sys, collections
from pathlib import Path
root = Path(sys.argv[1])
cfg = json.load(open(root / "config.json"))
def sd(x): return st.stdev(x) if len(x) > 1 else float('nan')
rows = []
for spec in cfg["stage_a_reds"]:
    import re
    folder = root / "stage-a" / re.sub(r"[^a-z0-9]+", "-", spec["name"].lower()).strip("-")
    recs = [json.load(open(p)) for p in sorted(folder.glob("seed-*.json"))]
    def comp(f, k): return [r["scores"][f][k] for r in recs]
    b = lambda r: r["behavior"]
    inv = {f: sum(b(r)[f]["invalid_outputs"] for r in recs) for f in ("Blue", "Red")}
    msgs = sum(b(r)["Red"]["broadcasts"] + b(r)["Red"]["private_messages"] for r in recs)
    rows.append(dict(
        name=spec["name"], seeds=[r["seed"] for r in recs],
        U=comp("Blue", "S"), P=comp("Blue", "P_proj"), V=comp("Blue", "V"), C=comp("Blue", "C_ff"),
        red_att_blue=[b(r)["Red"]["attack_attempts"]["Blue"] for r in recs],
        red_att_succ=[b(r)["Red"]["attack_successes"]["Blue"] for r in recs],
        red_steal_blue=[b(r)["Red"]["steal_attempts"]["Blue"] for r in recs],
        red_steal_succ=[b(r)["Red"]["steal_successes"]["Blue"] for r in recs],
        red_aggr_err=[b(r)["Red"]["aggression_errors"] for r in recs],
        red_ff=[b(r)["Red"]["friendly_fire_attempts"] for r in recs],
        blue_ff=[b(r)["Blue"]["friendly_fire_attempts"] for r in recs],
        blue_att_red=[b(r)["Blue"]["attack_attempts"]["Red"] + b(r)["Blue"]["steal_attempts"]["Red"] for r in recs],
        red_gather=[b(r)["Red"]["units_gathered"] for r in recs],
        red_rest=[b(r)["Red"]["rests"] for r in recs],
        blue_gather=[b(r)["Blue"]["units_gathered"] for r in recs],
        red_msgs=msgs, invalid=inv, blue_alive=[r["blue_material"]["agents_alive"] for r in recs],
    ))
for r in rows:
    print(json.dumps({k: (round(v, 3) if isinstance(v, float) else v) for k, v in r.items()}))
print()
print("| Red | U_Blue mean | U_Blue per seed | P_proj per seed | V per seed | C_ff per seed |")
for r in rows:
    print(f"| {r['name']} | {st.mean(r['U']):.3f} | {r['U']} | {r['P']} | {r['V']} | {r['C']} |")
print()
print("ranking:", [r["name"] for r in sorted(rows, key=lambda r: -st.mean(r["U"]))])
print("within-Red SD of U_Blue:", {r["name"]: round(sd(r["U"]), 3) for r in rows})
print("pooled within-Red SD:", round((st.mean([sd(r["U"]) ** 2 for r in rows])) ** .5, 3))
