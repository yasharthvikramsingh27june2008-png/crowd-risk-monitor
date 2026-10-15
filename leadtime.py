"""Measure the ACTUAL early-warning lead time.

The Gemini playbook claimed 15-30 minutes of lead time.
We need the honest number for the pitch, not a hopeful one.

Method: same simulation, same forecast logic as the browser version
(least-squares trend fit over the last 60 s of density history).
For every grid cell that eventually breaches 5.0 p/m2, record when the
forecast FIRST predicted it.
Lead time = (time it breached) - (time it was first predicted).
"""
import numpy as np


def run(baseline=12, surge_mult=3.0, surge_at=360, surge_dur=60,
        minutes=20, dt=0.2, seed=7, jam=6.8, k_rep=0.75, w_rep=0.45,
        thresh=5.0, hist_every=5.0, hist_keep=12, verbose=False):
    rng = np.random.default_rng(seed)
    W, H, CELL = 120.0, 100.0, 2.0
    COLS, ROWS = int(W / CELL), int(H / CELL)
    GATE_L, GATE_R = np.array([34., 3.]), np.array([86., 3.])
    FUNNEL = np.array([60., 46.]); EXIT = np.array([60., 56.]); SANGAM = np.array([60., 90.])
    GAP_L, GAP_R = 54., 66.; VS = 1.35

    px = np.zeros(0); py = np.zeros(0); pv = np.zeros(0)
    ps = np.zeros(0); pw = np.zeros(0); pl = np.zeros(0)
    t = 0.; acc = 0.; dens = np.zeros((ROWS, COLS))
    hist = []            # list of (time, flattened density grid)
    warned = {}          # cell index -> first time a prediction was made
    lead_times = []      # measured lead times
    breach_times = {}    # cell index -> time it first crossed the threshold

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

        # ---- snapshot history (same cadence as the browser build) ----
        if abs(t % hist_every) < dt:
            hist.append((t, dens.flatten().copy()))
            if len(hist) > hist_keep:
                hist.pop(0)

        # ---- forecast: least-squares trend fit, same as the browser ----
        if len(hist) >= 6:
            ts_ = np.array([h[0] for h in hist])
            tm = ts_.mean()
            toff = ts_ - tm
            denom = float((toff ** 2).sum())
            newest = hist[-1][1]
            if denom > 1e-9:
                stack = np.stack([h[1] for h in hist])
                num = (toff[:, None] * stack).sum(axis=0)
                rate = num / denom
                rising = (newest < thresh) & (newest >= 1.5) & (rate > 0.002)
                eta = np.where(rising, (thresh - newest) / np.maximum(rate, 1e-9), np.inf)
                predicted = rising & (eta > 0) & (eta < 1800)

                for i in np.nonzero(predicted)[0]:
                    if i not in warned:
                        warned[i] = t

                breached = np.nonzero(newest >= thresh)[0]
                for i in breached:
                    if i not in breach_times:
                        breach_times[i] = t
                        if i in warned:
                            lead = t - warned[i]
                            if lead > 0:
                                lead_times.append(lead)

    if verbose:
        print(f"  surge window: {surge_at}s .. {surge_at + surge_dur}s")
        print(f"  cells that breached the threshold : {len(breach_times)}")
        print(f"  cells warned BEFORE they breached  : {len(lead_times)} / {len(breach_times)}")
    return lead_times, breach_times, warned


print("EARLY-WARNING LEAD TIME — measured, not claimed")
print("=" * 52)
LT, BT, WN = run(verbose=True)
if LT:
    a = np.array(LT)
    print(f"\n  lead times measured : {len(a)}")
    print(f"  MEDIAN : {np.median(a):6.1f} s   ({np.median(a)/60:.2f} min)")
    print(f"  MEAN   : {a.mean():6.1f} s")
    print(f"  MAX    : {a.max():6.1f} s   ({a.max()/60:.2f} min)")
    print(f"  MIN    : {a.min():6.1f} s")
    print(f"\n  >> honest headline: about {np.median(a)/60:.1f} minute(s) of warning")
else:
    print("  NO lead times recorded.")

print("\nSensitivity check across surge sizes:")
for mult, dur in [(2.6, 60), (3.0, 60), (3.0, 120), (3.5, 90), (4.0, 120)]:
    lt, _, _ = run(surge_mult=mult, surge_dur=dur)
    if lt:
        a = np.array(lt)
        print(f"  surge {mult}x for {dur:3d}s -> median {np.median(a):5.1f}s | max {a.max():6.1f}s | n={len(a)}")
    else:
        print(f"  surge {mult}x for {dur:3d}s -> no warnings recorded")
