"""
VERIFICATION SCRIPT — does the funnel actually go red?

This is a Python port of the JavaScript simulation in prototype/index.html.
I'm running it here because I can't watch the browser, and I claimed in my last
message that the barrier gap becomes the bottleneck.

If this script says otherwise, my claim was wrong and I need to fix the sim.

Goal: find out (a) where peak density occurs, (b) when it crosses 5 persons/m2,
(c) how much warning time the forecast gives us.
"""

import numpy as np

# ---- world geometry (matches the JS) ----
W, H, CELL = 120.0, 100.0, 2.0
COLS, ROWS = int(W / CELL), int(H / CELL)
THRESHOLD = 5.0
GAP_L, GAP_R, BARRIER_Y = 52.0, 68.0, 50.0
GATE_L = np.array([34.0, 3.0])
GATE_R = np.array([86.0, 3.0])
FUNNEL = np.array([60.0, 46.0])
EXIT   = np.array([60.0, 56.0])
SANGAM = np.array([60.0, 90.0])

SPAWN_RATE = 9.0
MAX_AGENTS = 2200
WALK_SPEED = 1.35

rng = np.random.default_rng(7)


def make(n_records=0):
    return dict(
        x=np.zeros(0), y=np.zeros(0), v=np.zeros(0), speed=np.zeros(0),
        wob=np.zeros(0)
    )


class Sim:
    def __init__(self):
        self.t = 0.0
        self.spawn_acc = 0.0
        self.px = np.zeros(0); self.py = np.zeros(0)
        self.pv = np.zeros(0); self.ps = np.zeros(0)
        self.pw = np.zeros(0); self.pl = np.zeros(0)
        self.density = np.zeros((ROWS, COLS))
        self.peak_hist = []

    def spawn(self, n):
        if len(self.px) + n > MAX_AGENTS:
            n = max(0, MAX_AGENTS - len(self.px))
        if n == 0:
            return
        gate = rng.random(n) < 0.5
        gx = np.where(gate, GATE_L[0], GATE_R[0])
        gy = np.where(gate, GATE_L[1], GATE_R[1])
        self.px = np.concatenate([self.px, gx + (rng.random(n) - 0.5) * 14])
        self.py = np.concatenate([self.py, gy + (rng.random(n) - 0.5) * 4])
        self.pv = np.concatenate([self.pv, WALK_SPEED * (0.85 + rng.random(n) * 0.3)])
        self.ps = np.concatenate([self.ps, np.zeros(n)])
        self.pw = np.concatenate([self.pw, rng.random(n) * 2 * np.pi])
        self.pl = np.concatenate([self.pl, (rng.random(n) - 0.5) * 13.0])

    def compute_density(self):
        c = np.clip((self.px / CELL).astype(int), 0, COLS - 1)
        r = np.clip((self.py / CELL).astype(int), 0, ROWS - 1)
        flat = np.bincount(r * COLS + c, minlength=ROWS * COLS).astype(float)
        self.density = (flat / (CELL * CELL)).reshape(ROWS, COLS)

    def sample(self, x, y):
        c = np.clip((x / CELL).astype(int), 0, COLS - 1)
        r = np.clip((y / CELL).astype(int), 0, ROWS - 1)
        return self.density[r, c]

    def step(self, dt):
        # spawn
        self.spawn_acc += dt * SPAWN_RATE * 2
        n_new = int(self.spawn_acc)
        if n_new:
            self.spawn_acc -= n_new
            self.spawn(n_new)

        if len(self.px) == 0:
            self.t += dt
            return

        # route target by band
        tx = np.full(len(self.px), SANGAM[0])
        ty = np.full(len(self.py), SANGAM[1])
        m1 = self.py < FUNNEL[1]
        tx[m1], ty[m1] = FUNNEL[0] + self.pl[m1], FUNNEL[1]
        m2 = (~m1) & (self.py < EXIT[1])
        tx[m2], ty[m2] = EXIT[0] + self.pl[m2], EXIT[1]
        m3 = self.py >= EXIT[1]
        tx[m3] = SANGAM[0] + self.pl[m3] * 2.2

        dx = tx - self.px; dy = ty - self.py
        dist = np.hypot(dx, dy); dist[dist == 0] = 1.0
        dx /= dist; dy /= dist

        self.pw += dt * 1.6
        wob = np.sin(self.pw) * 0.22

        # THE RULE: look 3 m ahead
        ax = self.px + dx * 3.0
        ay = self.py + dy * 3.0
        ahead = self.sample(self.px, self.py) * 0.4 + self.sample(ax, ay) * 0.6

        congestion = np.clip((ahead - 1.5) / 4.5, 0.0, 1.0)
        target_speed = self.pv * (1.0 - 0.94 * congestion)
        self.ps += (target_speed - self.ps) * min(1.0, dt * 4.0)

        self.px += (dx + wob * -dy) * self.ps * dt
        self.py += (dy + wob *  dx) * self.ps * dt

        self.px = np.clip(self.px, 1, W - 1)
        self.py = np.clip(self.py, 1, H - 1)

        # arrived at the ghat -> out of the simulation
        keep = self.py <= 87.0
        self.px, self.py, self.pv, self.ps, self.pw, self.pl = (
            self.px[keep], self.py[keep], self.pv[keep], self.ps[keep],
            self.pw[keep], self.pl[keep]
        )
        self.t += dt


sim = Sim()
DT = 0.2
peak_log = []

print("t(s)   agents   peak  where(x,y m)   at-gap?")
print("-" * 58)

while sim.t < 900:
    sim.step(DT)
    sim.compute_density()
    if abs(sim.t % 30) < DT:
        peak = sim.density.max()
        r, c = np.unravel_index(sim.density.argmax(), sim.density.shape)
        x, y = c * CELL + 1, r * CELL + 1
        at_gap = GAP_L <= x <= GAP_R and 44 <= y <= 56
        peak_log.append((sim.t, len(sim.px), peak, x, y, at_gap))
        print(f"{sim.t:5.0f}  {len(sim.px):6d}  {peak:5.2f}  ({x:5.0f},{y:4.0f})    {'YES' if at_gap else 'no'}")

print()
first_breach = next((p for p in peak_log if p[2] >= THRESHOLD), None)
if first_breach:
    print(f">>> Peak density crossed {THRESHOLD} p/m2 at t={first_breach[0]:.0f}s")
    print(f"    at ({first_breach[3]:.0f} m, {first_breach[4]:.0f} m) — near the barrier gap? {first_breach[5]}")
else:
    print(f">>> Peak density NEVER crossed {THRESHOLD} p/m2 in 900 s")

# where did peak density ever occur?
gap_peaks = sum(1 for p in peak_log if p[5])
print(f">>> Peak density was located at the barrier gap in {gap_peaks}/{len(peak_log)} samples")

# ---- ASCII map at the end ----
print("\nDensity map at t=%.0fs  (rows = y, cols = x; each cell 2m)" % sim.t)
print("legend:  . <1    - 1-2    + 2-3    * 3-5    # >5 (CRUSH RISK)")
chars = ". -+*#"
for r in range(ROWS):
    line = []
    for c in range(COLS):
        d = sim.density[r, c]
        idx = 0 if d < 1 else 1 if d < 2 else 2 if d < 3 else 3 if d < 5 else 4
        line.append(chars[idx])
    marker = ""
    if abs(r * CELL - BARRIER_Y) < CELL:
        marker = "  <-- BARRIER"
    print("".join(line) + marker)
