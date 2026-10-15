"""Is the 5 p/m2 threshold even being measured correctly?

Findings so far:
  1. Forecast on 2 m cells -> 3% precision (97% false alarms). Unusable.
  2. Aggregate to larger sectors -> false alarms drop, BUT no sector ever
     reaches 5 p/m2, because averaging over a big area dilutes the peak.

That second result is the clue. It means the 5 p/m2 number depends entirely
on the AREA over which you measure it. This is a known problem in crowd
science: measured density is scale-dependent. A 2 m square can show 6 p/m2
while the 8 m square containing it shows only 3.5.

The standard fix in crowd research is to measure density the way a PERSON
experiences it: for each individual, count how many people are within a
small radius (typically ~1 m). That single number is what determines whether
they can breathe, and it is the quantity the 5 p/m2 guidance actually refers to.

This script compares the two metrics on the same simulation.
"""
import numpy as np


def run(radius=1.0, baseline=12, surge_mult=3.0, surge_at=360, surge_dur=60,
        minutes=20, dt=0.2, seed=7, thresh=5.0):
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
    series = []      # (time, grid_peak, person_peak, person_p95, n_people)
    r2 = radius * radius
    area = np.pi * r2

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

    def person_density(xs, ys):
        """For each person, how many others are within `radius`? -> p/m2."""
        if len(xs) == 0:
            return np.zeros(0)
        order = np.argsort(ys)
        xs_s = xs[order]; ys_s = ys[order]
        out = np.zeros(len(xs_s))
        for i in range(len(xs_s)):
            lo = np.searchsorted(ys_s, ys_s[i] - radius)
            hi = np.searchsorted(ys_s, ys_s[i] + radius)
            dx = xs_s[lo:hi] - xs_s[i]
            dy = ys_s[lo:hi] - ys_s[i]
            n = int(np.sum(dx * dx + dy * dy <= r2))
            out[i] = max(0, n - 1) / area      # exclude self
        return out

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

        if abs(t % 15) < dt and len(px) > 0:
            gp = dens.max()
            pd = person_density(px, py)
            series.append((t, gp, pd.max() if len(pd) else 0,
                           np.percentile(pd, 95) if len(pd) else 0, len(px)))

    return series


print("TWO WAYS TO MEASURE CROWD DENSITY — same simulation, same moment")
print("=" * 84)
print("grid peak  = busiest 2x2 m cell          (what the current build shows)")
print("person max = worst-off individual's own density (what a person FEELS)")
print("person p95 = 95th-percentile individual density")
print()
print(f"{'t(s)':>6} {'people':>8} {'grid peak':>11} {'person max':>12} {'person p95':>12}")
print("-" * 84)
S = run()
for row in S[::8]:
    t, gp, pm, p95, n = row
    flag = "  <-- SURGE" if 360 <= t <= 480 else ""
    print(f"{t:6.0f} {n:8d} {gp:11.2f} {pm:12.2f} {p95:12.2f}{flag}")

gps = np.array([r[1] for r in S])
pms = np.array([r[2] for r in S])
p95s = np.array([r[3] for r in S])
print()
print(f"{'':22} {'grid peak':>12} {'person max':>12} {'person p95':>12}")
print(f"{'steady state (t<360)':22} "
      f"{np.median(gps[[r[0] for r in S] if False else np.array([r[0] for r in S]) < 360]):12.2f} "
      f"{np.median(pms[np.array([r[0] for r in S]) < 360]):12.2f} "
      f"{np.median(p95s[np.array([r[0] for r in S]) < 360]):12.2f}")
surge_mask = (np.array([r[0] for r in S]) >= 360) & (np.array([r[0] for r in S]) <= 480)
print(f"{'during surge':22} {gps[surge_mask].max():12.2f} {pms[surge_mask].max():12.2f} {p95s[surge_mask].max():12.2f}")
