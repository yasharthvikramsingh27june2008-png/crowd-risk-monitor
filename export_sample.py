"""Export sample zone readings from the simulator to CSV.

The competition guidelines require sample data in the repository. Rather than
hand-writing fake numbers, this script runs the same model used by the browser
build and writes real per-zone person-centred density readings to
sample_zone_readings.csv (in this folder).

Run:  python3 export_sample.py
"""
import csv
import numpy as np
from scipy.spatial import cKDTree

ZONES = [
    ('Gate A approach', 18, 0, 48, 32),
    ('Gate B approach', 72, 0, 102, 32),
    ('FUNNEL (12 m gap)', 50, 36, 70, 56),
    ('South corridor', 46, 56, 74, 78),
    ('Ghat / Sangam', 28, 78, 92, 92),
]

def simulate(minutes=9, dt=0.2, seed=7, baseline=12, pd_radius=1.0):
    rng = np.random.default_rng(seed)
    W, H, CELL = 120.0, 100.0, 2.0
    COLS, ROWS = int(W / CELL), int(H / CELL)
    GATE_L, GATE_R = np.array([34., 3.]), np.array([86., 3.])
    FUNNEL = np.array([60., 46.]); EXIT = np.array([60., 56.]); SANGAM = np.array([60., 90.])
    GAP_L, GAP_R, VS = 54., 66., 1.35
    jam, k_rep, w_rep = 6.8, 0.75, 0.45
    PD_AREA = np.pi * pd_radius * pd_radius

    px = np.zeros(0); py = np.zeros(0); pv = np.zeros(0)
    ps = np.zeros(0); pw = np.zeros(0); pl = np.zeros(0)
    t = 0.0; acc = 0.0; dens = np.zeros((ROWS, COLS))
    rows = []

    def d_of(x, y):
        c = np.clip((x / CELL).astype(int), 0, COLS - 1)
        r = np.clip((y / CELL).astype(int), 0, ROWS - 1)
        return dens[r, c]

    def recompute():
        nonlocal dens
        c = np.clip((px / CELL).astype(int), 0, COLS - 1)
        r = np.clip((py / CELL).astype(int), 0, ROWS - 1)
        flat = np.bincount(r * COLS + c, minlength=ROWS * COLS).astype(float)
        dens = (flat / (CELL * CELL)).reshape(ROWS, COLS)

    def person_density():
        if len(px) == 0:
            return np.zeros(0)
        pts = np.column_stack([px, py])
        tr = cKDTree(pts)
        cnts = tr.query_ball_point(pts, pd_radius, return_length=True)
        return np.maximum(0, cnts - 1) / PD_AREA

    while t < minutes * 60:
        mult = 3.0 if 300 <= t < 360 else 1.0          # surge at 5 min, as in the app
        acc += dt * baseline * mult * 2
        n = int(acc)
        if n:
            acc -= n
            if len(px) + n <= 3000:
                g = rng.random(n) < 0.5
                gx = np.where(g, GATE_L[0], GATE_R[0])
                gy = np.where(g, GATE_L[1], GATE_R[1])
                px = np.concatenate([px, gx + (rng.random(n) - .5) * 14])
                py = np.concatenate([py, gy + (rng.random(n) - .5) * 4])
                pv = np.concatenate([pv, VS * (.85 + rng.random(n) * .3)])
                ps = np.concatenate([ps, np.zeros(n)])
                pw = np.concatenate([pw, rng.random(n) * 2 * np.pi])
                pl = np.concatenate([pl, (rng.random(n) - .5) * ((GAP_R - GAP_L) * 0.92)])

        if len(px):
            tx = np.full(len(px), SANGAM[0]); ty = np.full(len(py), SANGAM[1])
            m1 = py < FUNNEL[1]; tx[m1] = FUNNEL[0] + pl[m1]; ty[m1] = FUNNEL[1]
            m2 = (~m1) & (py < EXIT[1]); tx[m2] = EXIT[0] + pl[m2]; ty[m2] = EXIT[1]
            m3 = py >= EXIT[1]; tx[m3] = SANGAM[0] + pl[m3]
            dx = tx - px; dy = ty - py
            dist = np.hypot(dx, dy); dist[dist == 0] = 1
            dx /= dist; dy /= dist
            rx = -(d_of(px + 1.5, py) - d_of(px - 1.5, py))
            ry = -(d_of(px, py + 1.5) - d_of(px, py - 1.5))
            rm = np.hypot(rx, ry)
            sc = np.minimum(1.0, rm * k_rep) / np.maximum(rm, 1e-9)
            rx *= sc; ry *= sc
            vx = dx * (1 - w_rep) + rx * w_rep
            vy = dy * (1 - w_rep) + ry * w_rep
            vn = np.hypot(vx, vy); vn[vn == 0] = 1
            vx /= vn; vy /= vn
            pw += dt * 1.6; wob = np.sin(pw) * .22
            ahead = d_of(px, py) * .4 + d_of(px + dx * 3, py + dy * 3) * .6
            cong = np.clip(ahead / jam, 0, 1)
            ts_v = pv * (1 - cong)
            ps += (ts_v - ps) * min(1, dt * 4)
            px += (vx + wob * -vy) * ps * dt
            py += (vy + wob * vx) * ps * dt
            px = np.clip(px, 1, W - 1); py = np.clip(py, 1, H - 1)
            k = py <= 87
            px, py, pv, ps, pw, pl = px[k], py[k], pv[k], ps[k], pw[k], pl[k]

        t += dt
        recompute()

        if abs(t % 10) < dt and len(px) > 0:
            pd = person_density()
            clock = 5 * 3600 + t
            hh = int(clock // 3600) % 24
            mm = int(clock // 60) % 60
            ss = int(clock % 60)
            row = {
                'sim_clock': f"{hh:02d}:{mm:02d}:{ss:02d}",
                'elapsed_s': int(t),
                'pilgrims_total': len(px),
                'worst_person_density': round(float(pd.max()), 2),
                'p95_person_density': round(float(np.percentile(pd, 95)), 2),
            }
            for name, x1, y1, x2, y2 in ZONES:
                m = (px >= x1) & (px <= x2) & (py >= y1) & (py <= y2)
                row[name] = round(float(pd[m].max()), 2) if m.any() else 0.0
            rows.append(row)
    return rows


rows = simulate()
cols = list(rows[0].keys())
with open('sample_zone_readings.csv', 'w', newline='') as f:
    w = csv.DictWriter(f, fieldnames=cols)
    w.writeheader()
    w.writerows(rows)

print(f"wrote sample_zone_readings.csv  ({len(rows)} rows, {len(cols)} columns)")
print("columns:", ", ".join(cols))
print()
print("peak readings:")
for c in ['FUNNEL (12 m gap)', 'South corridor', 'worst_person_density']:
    vals = [r[c] for r in rows]
    print(f"  {c:24} max {max(vals):.2f}")
print()
print("sample rows around the surge:")
for r in rows:
    if 280 <= r['elapsed_s'] <= 430 and r['elapsed_s'] % 30 == 0:
        print(f"  {r['sim_clock']}  pilgrims={r['pilgrims_total']:5d}  "
              f"FUNNEL={r['FUNNEL (12 m gap)']:5.2f}  worst={r['worst_person_density']:5.2f}")
