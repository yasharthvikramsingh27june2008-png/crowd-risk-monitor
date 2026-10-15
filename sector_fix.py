"""THE FIX: forecast by SECTOR, not by 2 m x 2 m cell.

Finding from precision.py:
  The current build flags 574 cells as "at risk"; only 17 actually breach.
  That is a 3% precision rate - 97% false alarms. Useless operationally.
  The "6.4 min lead time" was an artefact of the alarm being stuck on.

Why it fails: a 2 m x 2 m cell holds 4-30 people. Its density jitters wildly
from random movement, so tiny meaningless trends get flagged constantly.

The fix is the one real control rooms already use: think in SECTORS.
Aggregate the grid into larger operational zones (e.g. 8 m x 8 m, or named
zones such as "funnel", "gate A approach", "ghat steps"), then forecast on
sector-average density. Bigger area = stable statistics = real signal.

This script tests several sector sizes to find the sweet spot.
"""
import numpy as np


def run(sector_cells=4, eta_cap=600.0, rate_min=0.01, min_dens=2.5,
        baseline=12, surge_mult=3.0, surge_at=360, surge_dur=60,
        minutes=20, dt=0.2, seed=7, thresh=5.0,
        hist_every=5.0, hist_keep=12):
    """sector_cells: how many 2 m cells per side make one sector (4 -> 8 m sector)"""
    rng = np.random.default_rng(seed)
    W, H, CELL = 120.0, 100.0, 2.0
    COLS, ROWS = int(W / CELL), int(H / CELL)
    SC = sector_cells
    S_COLS, S_ROWS = COLS // SC, ROWS // SC
    GATE_L, GATE_R = np.array([34., 3.]), np.array([86., 3.])
    FUNNEL = np.array([60., 46.]); EXIT = np.array([60., 56.]); SANGAM = np.array([60., 90.])
    GAP_L, GAP_R = 54., 66.; VS = 1.35
    jam, k_rep, w_rep = 6.8, 0.75, 0.45

    px = np.zeros(0); py = np.zeros(0); pv = np.zeros(0)
    ps = np.zeros(0); pw = np.zeros(0); pl = np.zeros(0)
    t = 0.; acc = 0.; dens = np.zeros((ROWS, COLS))
    hist = []
    warned = {}; breach_times = {}; lead_times = []; in_warn = []

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

    def sectors():
        # average density over each sector block
        d = dens[:S_ROWS * SC, :S_COLS * SC].reshape(S_ROWS, SC, S_COLS, SC)
        return d.mean(axis=(1, 3))

    while t < minutes * 60:
        rate = baseline * (surge_mult if surge_at <= t < surge_at + surge_dur else 1.0)
        acc += dt * rate * 2
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
            ts = pv * (1 - cong)
            ps += (ts - ps) * min(1, dt * 4)
            px += (vx + wob * -vy) * ps * dt
            py += (vy + wob * vx) * ps * dt
            px = np.clip(px, 1, W - 1); py = np.clip(py, 1, H - 1)
            k = py <= 87
            px, py, pv, ps, pw, pl = px[k], py[k], pv[k], ps[k], pw[k], pl[k]

        t += dt
        recompute()

        if abs(t % hist_every) < dt:
            hist.append((t, sectors().flatten().copy()))
            if len(hist) > hist_keep:
                hist.pop(0)

        if len(hist) >= 6:
            ts_ = np.array([h[0] for h in hist])
            tm = ts_.mean(); toff = ts_ - tm
            denom = float((toff ** 2).sum())
            newest = hist[-1][1]
            if denom > 1e-9:
                stack = np.stack([h[1] for h in hist])
                num = (toff[:, None] * stack).sum(axis=0)
                rate = num / denom
                rising = (newest < thresh) & (newest >= min_dens) & (rate > rate_min)
                eta = np.where(rising, (thresh - newest) / np.maximum(rate, 1e-9), np.inf)
                predicted = rising & (eta > 0) & (eta < eta_cap)
                idx = np.nonzero(predicted)[0]
                in_warn.append(len(idx))
                for i in idx:
                    if i not in warned:
                        warned[i] = t
                for i in np.nonzero(newest >= thresh)[0]:
                    if i not in breach_times:
                        breach_times[i] = t
                        if i in warned:
                            lead = t - warned[i]
                            if lead > 0:
                                lead_times.append(lead)

    n_w = len(warned); n_b = len(breach_times); tp = len(lead_times)
    return dict(
        n_warned=n_w, n_breached=n_b, true_pos=tp,
        precision=tp / n_w if n_w else 0.0,
        recall=tp / n_b if n_b else 0.0,
        med_lead=float(np.median(lead_times)) if lead_times else 0.0,
        avg_in_warn=float(np.mean(in_warn)) if in_warn else 0.0,
        n_sectors=S_COLS * S_ROWS,
    )


print("FORECAST BY SECTOR — does aggregating fix the false alarms?")
print("=" * 92)
print(f"{'sector size':<14} {'#sectors':>9} {'warned':>7} {'breached':>9} "
      f"{'precision':>10} {'recall':>7} {'lead':>8} {'avg in warn':>12}")
print("-" * 92)

for sc in [2, 4, 6, 8]:
    r = run(sector_cells=sc)
    size_m = sc * 2
    print(f"{size_m:>3d} m sector   {r['n_sectors']:>9} {r['n_warned']:>7} {r['n_breached']:>9} "
          f"{r['precision']*100:>9.1f}% {r['recall']*100:>6.1f}% "
          f"{r['med_lead']:>7.1f}s {r['avg_in_warn']:>12.2f}")

print()
print("Tuning the best sector size (8 m) with different trigger settings:")
print(f"{'setting':<34} {'precision':>10} {'recall':>7} {'lead':>8} {'avg warn':>9}")
print("-" * 74)
for label, cap, rmin, md in [
    ("eta<10min, rate>0.01, d>2.5", 600.0, 0.01, 2.5),
    ("eta<5min,  rate>0.02, d>3.0", 300.0, 0.02, 3.0),
    ("eta<3min,  rate>0.03, d>3.5", 180.0, 0.03, 3.5),
    ("eta<10min, rate>0.05, d>3.5", 600.0, 0.05, 3.5),
    ("eta<5min,  rate>0.05, d>4.0", 300.0, 0.05, 4.0),
]:
    r = run(sector_cells=4, eta_cap=cap, rate_min=rmin, min_dens=md)
    print(f"{label:<34} {r['precision']*100:>9.1f}% {r['recall']*100:>6.1f}% "
          f"{r['med_lead']:>7.1f}s {r['avg_in_warn']:>9.2f}")
