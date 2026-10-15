"""Does a REALISTIC timeline fix the lead time?

Hypothesis (raised when the user asked "what is the sim clock?"):
The scenario runs far too fast in simulated time. The surge is "3x spawn for
60 simulated seconds" - a real bathing-hour surge builds over 30-60 minutes.
You cannot forecast an event that has no runway.

So: give the same model a realistic timeline and see whether lead time improves.

Key accompanying insight: the forecast fits a trend line over a HISTORY WINDOW.
If the event now takes 60 minutes, a 60-SECOND history window is blind to it -
the slope over 60 s is buried in noise. The history window must match the
timescale of the event.

This script tests the current fast scenario against a realistic one, and
sweeps the history window for the realistic case.
"""
import numpy as np
from scipy.spatial import cKDTree

ZONES = [
    ('Gate A approach', 18, 0, 48, 32),
    ('Gate B approach', 72, 0, 102, 32),
    ('FUNNEL (12 m gap)', 50, 36, 70, 56),
    ('South corridor', 46, 56, 74, 78),
    ('Ghat / Sangam', 28, 78, 92, 92),
]
NZ = len(ZONES)


def spawn_mult_fast(t):
    """current build: abrupt 3x for 60 s at t=360"""
    return 3.0 if 360 <= t < 420 else 1.0


def spawn_mult_realistic(t):
    """realistic bathing-day timeline:
       0-1800     baseline                (30 min quiet build)
       1800-5400  ramp 1.0 -> 3.5         (60 min build-up)
       5400-6600  hold 3.5                (20 min peak)
       6600-7800  decay back to 1.0       (20 min dispersal)
    """
    if t < 1800: return 1.0
    if t < 5400: return 1.0 + 2.5 * (t - 1800) / 3600.0
    if t < 6600: return 3.5
    if t < 7800: return 1.0 + 2.5 * max(0.0, (7800 - t) / 1200.0)
    return 1.0


def run(mult_fn, minutes, hist_window_s, hist_every=10.0, dt=0.2, seed=7,
        baseline=12, jam=6.8, thresh=5.0, pd_radius=1.0,
        rate_min=0.0015, min_dens=2.0, eta_cap=1800.0, eta_floor=20.0,
        sustained=2, verbose=False):
    rng = np.random.default_rng(seed)
    W, H, CELL = 120.0, 100.0, 2.0
    COLS, ROWS = int(W / CELL), int(H / CELL)
    GATE_L, GATE_R = np.array([34., 3.]), np.array([86., 3.])
    FUNNEL = np.array([60., 46.]); EXIT = np.array([60., 56.]); SANGAM = np.array([60., 90.])
    GAP_L, GAP_R = 54., 66.; VS = 1.35
    k_rep, w_rep = 0.75, 0.45
    PD_AREA = np.pi * pd_radius * pd_radius
    KEEP = max(4, int(hist_window_s / hist_every))

    px = np.zeros(0); py = np.zeros(0); pv = np.zeros(0)
    ps = np.zeros(0); pw = np.zeros(0); pl = np.zeros(0)
    t = 0.0; acc = 0.0
    dens = np.zeros((ROWS, COLS))
    hist = []
    warned = [None] * NZ
    ever_breached = [False] * NZ
    episodes = []

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
        tree = cKDTree(pts)
        cnts = tree.query_ball_point(pts, pd_radius, return_length=True)
        return np.maximum(0, cnts - 1) / PD_AREA

    def zone_maxima(pd):
        vals = np.zeros(NZ)
        if len(pd) == 0:
            return vals
        for z, (nm, x1, y1, x2, y2) in enumerate(ZONES):
            m = (px >= x1) & (px <= x2) & (py >= y1) & (py <= y2)
            if m.any():
                vals[z] = pd[m].max()
        return vals

    nex = 0
    while t < minutes * 60:
        rate = baseline * mult_fn(t)
        acc += dt * rate * 2
        n = int(acc)
        if n:
            acc -= n
            if len(px) + n <= 3200:
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
            pd = person_density()
            hist.append((t, zone_maxima(pd)))
            if len(hist) > KEEP:
                hist.pop(0)

        if len(hist) >= KEEP:
            n_ = len(hist)
            ts_ = np.array([h[0] for h in hist])
            tm = ts_.mean(); toff = ts_ - tm
            denom = float((toff ** 2).sum())
            newest = hist[-1][1]
            if denom > 1e-9:
                stack = np.stack([h[1] for h in hist])
                num = (toff[:, None] * stack).sum(axis=0)
                rate = num / denom
                recent = stack[-(sustained + 1):]
                rising_all = (np.diff(recent, axis=0) > 0).all(axis=0)

                for z in range(NZ):
                    now = newest[z]
                    if now >= thresh:
                        if warned[z] is not None and not ever_breached[z]:
                            episodes[-1].update(real=True, lead=t - warned[z], breach_t=t)
                            ever_breached[z] = True
                            nex += 1
                        continue
                    if rising_all[z] and rate[z] > rate_min and now >= min_dens:
                        eta = (thresh - now) / rate[z]
                        if eta_floor < eta < eta_cap and warned[z] is None:
                            warned[z] = t
                            episodes.append(dict(zone=ZONES[z][0], warn_t=t,
                                                 now=float(now), eta=float(eta),
                                                 real=False, lead=None))
                    else:
                        if warned[z] is not None and not ever_breached[z]:
                            warned[z] = None
                        if ever_breached[z] and now < thresh - 0.8:
                            ever_breached[z] = False

    return episodes


def report(label, eps):
    real = [e for e in eps if e['real']]
    leads = [e['lead'] for e in real]
    prec = (len(real) / len(eps) * 100) if eps else 0
    med = np.median(leads) if leads else 0
    line = (f"{label:<44} warn={len(eps):>3}  real={len(real):>2}  "
            f"prec={prec:>5.0f}%  median lead={med:>6.0f}s")
    print(line)
    for e in real[:4]:
        print(f"      {e['zone']:<20} warned t={e['warn_t']:>6.0f}s at {e['now']:.1f} p/m2"
              f" -> breached t={e['breach_t']:>6.0f}s  (lead {e['lead']:.0f}s)")


print("FAST SCENARIO vs REALISTIC TIMELINE")
print("=" * 92)
report("CURRENT: 60 s step surge, 60 s history",
       run(spawn_mult_fast, minutes=20, hist_window_s=60))

print()
print("REALISTIC TIMELINE — sweeping the forecast history window")
print("=" * 92)
for hw in [60, 180, 300, 600, 900]:
    report(f"ramp over 60 min, history window {hw}s",
           run(spawn_mult_realistic, minutes=140, hist_window_s=hw))
