"""Why is the lead time only 5-10 seconds, and why 21 warnings for 2 real events?

Diagnosis:

The user's screenshot showed: 21 warnings issued, only 2 real, lead times 5 s and 10 s.

Hypothesis: the DEMO SCENARIO IS TOO ABRUPT.
Our surge is "3x spawn rate for 60 SIMULATED seconds". But the sim runs at 20x
compression, so those 60 simulated seconds pass in 3 real seconds. A zone goes
from safe to dangerous in ~10 simulated seconds.

If the event only takes 10 seconds, there is no 15-minute warning to give.
You cannot forecast an event that has no runway. The poor lead time is a
property of the SCENARIO, not only of the model.

A real bathing-hour surge builds over 15-45 minutes as pilgrims arrive.

So: replace the step-surge with a GRADUAL RAMP and re-measure.
Also test a stricter trigger (sustained rise) to cut false alarms.
"""
import numpy as np
from scipy.spatial import cKDTree


def ramp_mult(t, t0=240, t1=1140, hold_to=1440, peak=3.2, t_end=1800):
    """Spawn multiplier: 1.0 -> peak linearly over t0..t1, hold, decay back."""
    if t < t0: return 1.0
    if t < t1: return 1.0 + (peak - 1.0) * (t - t0) / (t1 - t0)
    if t < hold_to: return peak
    if t < t_end: return 1.0 + (peak - 1.0) * max(0.0, (t_end - t) / (t_end - hold_to))
    return 1.0


def run(minutes=30, dt=0.2, seed=7, baseline=12, jam=6.8,
        thresh=5.0, pd_radius=1.0, sustained=3, rate_min=0.01,
        min_dens=2.5, eta_cap=900, eta_floor=30, verbose=False):
    """sustained: how many consecutive snapshots must show a rise to trigger."""
    rng = np.random.default_rng(seed)
    W, H, CELL = 120.0, 100.0, 2.0
    COLS, ROWS = int(W / CELL), int(H / CELL)
    GATE_L, GATE_R = np.array([34., 3.]), np.array([86., 3.])
    FUNNEL = np.array([60., 46.]); EXIT = np.array([60., 56.]); SANGAM = np.array([60., 90.])
    GAP_L, GAP_R = 54., 66.; VS = 1.35
    k_rep, w_rep = 0.75, 0.45
    PD_AREA = np.pi * pd_radius * pd_radius

    ZONES = [
        ('Gate A approach', 18, 0, 48, 32),
        ('Gate B approach', 72, 0, 102, 32),
        ('FUNNEL (12 m gap)', 50, 36, 70, 56),
        ('South corridor', 46, 56, 74, 78),
        ('Ghat / Sangam', 28, 78, 92, 92),
    ]
    NZ = len(ZONES)

    px = np.zeros(0); py = np.zeros(0); pv = np.zeros(0)
    ps = np.zeros(0); pw = np.zeros(0); pl = np.zeros(0)
    t = 0.0; acc = 0.0
    dens = np.zeros((ROWS, COLS))
    hist = []                       # list of (t, zone values array)

    warned = [None] * NZ            # when the current warning episode started
    episodes = []                   # dicts describing each warning episode
    ever_breached = [False] * NZ
    peak_series = []

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
        tree = cKDTree(np.column_stack([px, py]))
        cnts = tree.query_ball_point(np.column_stack([px, py]), pd_radius,
                                     return_length=True)
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

    while t < minutes * 60:
        rate = baseline * ramp_mult(t)
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

        if abs(t % 5) < dt:
            pd = person_density()
            zvals = zone_maxima(pd)
            hist.append((t, zvals))
            if len(hist) > 13:
                hist.pop(0)
            peak_series.append((t, float(pd.max()) if len(pd) else 0.0))

        # ---- forecast ----
        if len(hist) >= 8:
            n = len(hist)
            ts_ = np.array([h[0] for h in hist])
            tm = ts_.mean(); toff = ts_ - tm
            denom = float((toff ** 2).sum())
            newest = hist[-1][1]
            if denom > 1e-9:
                stack = np.stack([h[1] for h in hist])
                num = (toff[:, None] * stack).sum(axis=0)
                rate = num / denom
                # sustained-rise test: the last `sustained` deltas all positive
                recent = stack[-(sustained + 1):]
                deltas = np.diff(recent, axis=0)
                rising_all = (deltas > 0).all(axis=0)

                for z in range(NZ):
                    now = newest[z]
                    if now >= thresh:
                        if warned[z] is not None and not ever_breached[z]:
                            lead = t - warned[z]
                            episodes[-1].update(real=True, lead=lead, breach_t=t)
                            ever_breached[z] = True
                        continue
                    ok = (rising_all[z] and rate[z] > rate_min and now >= min_dens)
                    if ok:
                        eta = (thresh - now) / rate[z]
                        if eta_floor < eta < eta_cap:
                            if warned[z] is None:
                                warned[z] = t
                                episodes.append(dict(zone=ZONES[z][0], warn_t=t,
                                                     now=float(now), eta=float(eta),
                                                     real=False, lead=None))
                    else:
                        # warning expired without a breach -> false alarm
                        if warned[z] is not None and not ever_breached[z]:
                            warned[z] = None
                        if ever_breached[z] and now < thresh - 0.5:
                            ever_breached[z] = False

    return episodes, peak_series


print("SCENARIO REDESIGN — gradual ramp instead of an abrupt 60 s step")
print("=" * 84)

for label, kw in [
    ("old: 60 s step surge, loose trigger", dict(minutes=20)),
    ("new: gradual ramp, loose trigger", dict(minutes=30, sustained=1)),
    ("new: gradual ramp, sustained rise x3", dict(minutes=30, sustained=3)),
    ("new: gradual ramp, sustained x4 + rate>0.015", dict(minutes=30, sustained=4, rate_min=0.015)),
]:
    if "step" in label:
        # keep the old abrupt behaviour for comparison
        globals()['ramp_mult'] = (lambda t, **k: 3.0 if 360 <= t < 420 else 1.0)
    else:
        globals()['ramp_mult'] = ramp_mult

    eps, peaks = run(**kw)
    real = [e for e in eps if e['real']]
    false = [e for e in eps if not e['real']]
    leads = [e['lead'] for e in real if e['lead']]
    pmax = max(p for _, p in peaks)
    prec = len(real) / len(eps) * 100 if eps else 0
    med = np.median(leads) if leads else 0

    print(f"\n{label}")
    print(f"   warnings issued : {len(eps)}")
    print(f"   real events     : {len(real)}")
    print(f"   false alarms    : {len(false)}   precision {prec:.0f}%")
    print(f"   peak person-density : {pmax:.2f} p/m2")
    if leads:
        print(f"   lead times      : median {med:.0f} s ({med/60:.1f} min), max {max(leads):.0f} s")
    else:
        print("   lead times      : none recorded")
    for e in real[:6]:
        print(f"      -> {e['zone']}: warned at t={e['warn_t']:.0f}s at {e['now']:.1f} p/m2, "
              f"breached t={e['breach_t']:.0f}s, lead {e['lead']:.0f}s")
