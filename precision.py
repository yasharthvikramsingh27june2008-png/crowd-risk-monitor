"""Is the forecast actually useful, or is it just always alarming?

The previous run reported a 6.4 min median lead time. That looked too good.

Suspicion: the forecast criterion is eta < 1800 s (warn if a cell is predicted
to breach within 30 minutes). During a slow, steady buildup, MANY cells sit
permanently in that "predicted" state. If so, the system is not warning —
it is crying wolf continuously, and "lead time" just measures how long the
alarm was stuck on.

A lead-time number WITHOUT a false-alarm number is worthless.
A jury will ask exactly this.

So measure both:
  PRECISION  = of cells warned, what fraction actually breached?
  RECALL     = of cells that breached, what fraction were warned first?
  LEAD TIME  = for true positives only, how early was the warning?

And test stricter criteria to see if we can buy precision without losing
too much lead time.
"""
import numpy as np


def run(eta_cap=1800.0, rate_min=0.002, baseline=12, surge_mult=3.0,
        surge_at=360, surge_dur=60, minutes=20, dt=0.2, seed=7,
        thresh=5.0, hist_every=5.0, hist_keep=12):
    rng = np.random.default_rng(seed)
    W, H, CELL = 120.0, 100.0, 2.0
    COLS, ROWS = int(W / CELL), int(H / CELL)
    GATE_L, GATE_R = np.array([34., 3.]), np.array([86., 3.])
    FUNNEL = np.array([60., 46.]); EXIT = np.array([60., 56.]); SANGAM = np.array([60., 90.])
    GAP_L, GAP_R = 54., 66.; VS = 1.35
    jam, k_rep, w_rep = 6.8, 0.75, 0.45

    px = np.zeros(0); py = np.zeros(0); pv = np.zeros(0)
    ps = np.zeros(0); pw = np.zeros(0); pl = np.zeros(0)
    t = 0.; acc = 0.; dens = np.zeros((ROWS, COLS))
    hist = []
    warned = {}          # cell -> first warning time
    breach_times = {}
    lead_times = []
    cells_in_warning = []   # how many cells are in warning state, per snapshot

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
            hist.append((t, dens.flatten().copy()))
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
                rising = (newest < thresh) & (newest >= 1.5) & (rate > rate_min)
                eta = np.where(rising, (thresh - newest) / np.maximum(rate, 1e-9), np.inf)
                predicted = rising & (eta > 0) & (eta < eta_cap)

                idx_pred = np.nonzero(predicted)[0]
                cells_in_warning.append(len(idx_pred))
                for i in idx_pred:
                    if i not in warned:
                        warned[i] = t

                for i in np.nonzero(newest >= thresh)[0]:
                    if i not in breach_times:
                        breach_times[i] = t
                        if i in warned:
                            lead = t - warned[i]
                            if lead > 0:
                                lead_times.append(lead)

    n_warned = len(warned)
    n_breached = len(breach_times)
    true_pos = len(lead_times)
    precision = true_pos / n_warned if n_warned else 0.0
    recall = true_pos / n_breached if n_breached else 0.0
    med_lead = float(np.median(lead_times)) if lead_times else 0.0
    avg_in_warning = float(np.mean(cells_in_warning)) if cells_in_warning else 0.0
    return dict(n_warned=n_warned, n_breached=n_breached, true_pos=true_pos,
                precision=precision, recall=recall, med_lead=med_lead,
                avg_in_warning=avg_in_warning)


print("DOES THE FORECAST ACTUALLY WORK?")
print("=" * 78)
print(f"{'criterion':<28} {'warned':>7} {'breached':>9} {'precision':>10} {'recall':>7} {'lead':>8} {'avg cells':>10}")
print("-" * 78)

configs = [
    ("eta<30min (current build)", 1800.0, 0.002),
    ("eta<10min", 600.0, 0.002),
    ("eta<5min", 300.0, 0.002),
    ("eta<3min", 180.0, 0.002),
    ("eta<10min + rate>0.01", 600.0, 0.01),
    ("eta<5min + rate>0.02", 300.0, 0.02),
]
for name, cap, rmin in configs:
    r = run(eta_cap=cap, rate_min=rmin)
    print(f"{name:<28} {r['n_warned']:>7} {r['n_breached']:>9} "
          f"{r['precision']*100:>9.1f}% {r['recall']*100:>6.1f}% "
          f"{r['med_lead']:>7.1f}s {r['avg_in_warning']:>10.1f}")

print()
print("HOW TO READ THIS")
print("-" * 78)
print("'warned'   = cells the system flagged as at-risk at any point")
print("'breached' = cells that actually crossed 5.0 p/m2")
print("precision  = of the cells we flagged, how many really breached")
print("             LOW precision = crying wolf")
print("recall     = of the cells that breached, how many we flagged")
print("             LOW recall = we missed events")
print("lead       = median warning time for the cells we got right")
print("avg cells  = average number of cells sitting in warning state")
print("             (if this is huge, the alarm is effectively always on)")
