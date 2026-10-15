# Crowd Risk Monitor — simulation prototype

> **Demo only. This is not a real crowd-monitoring, emergency-dispatch, evacuation, or safety system.** It reads no venue sensors, live attendance counts, public-safety feeds, or routing services. It has not been calibrated or validated for real places or real operations. Do not use its readings or suggestions to make safety decisions.

This is a browser-only prototype. It models a small set of venues and crowds so the interface and response controls can be explored. The numbers and actions are synthetic.

## What the demo lets you try

- **Choose a preset venue** from the venue list, search its preset name or city, or select a marker on the home map. Search only checks the built-in list; it does not geocode or query a venue database.
- **AUTO density** runs the existing model-agent feed. Its natural-arrival governor tapers admissions toward a synthetic 4.7 persons/m² ceiling, below the 5.0 alarm line. A separate, cumulative **eight-step Surge** can raise the model and latch the demo alarm.
- **MANUAL density** is a synthetic test slider from 0.0 to 8.0 persons/m². It applies the chosen value uniformly to all zones, can reach the red band, and does not change the model-agent count. It is not a sensor reading. Alarm confirmation advances only while the simulation is playing.
- **Gate control and unit dispatch each have their own MANUAL/AUTO selector.** AUTO for gates does not turn dispatch AUTO on, and vice versa. Closing gates changes only the prototype's admission rate; the model does not reroute people around a closed gate.
- **Response steps, unit availability, ETAs, map routes, and venue presets are illustrative.** Nothing is sent to real gates, teams, or services.
- The prototype includes charts, a density heat layer, an X-Y plot, a separate guidance panel, a visible-but-disabled acknowledgement button until alarm confirmation, and an optional audible alarm.

## Density bands and alarm timing

| Reading (persons/m²) | Display band |
| --- | --- |
| Below 2.0 | Low |
| 2.0 to below 3.5 | Busy |
| 3.5 to below 5.0 | Elevated |
| 5.0 to below 6.5 | High (orange) |
| 6.5 and above | Red |

The **alarm line is 5.0**, so an orange high-band reading can start the alarm timer. The alarm latches after 45 simulated seconds accumulated above the line. It clears only after every zone is below 4.5 and the over-line timer has unwound. MANUAL values use the same bands and alarm logic; the slider itself does not alter the crowd model.

These are prototype settings, not validated safety thresholds. The natural AUTO governor and three sample runs are not proof that every venue or every run stays below a threshold.

## Map and network behavior

The runnable `index.html` embeds an illustrative background image. The detailed satellite or street imagery is requested from public map-tile services when available. Failed tile requests are retried and the built-in illustrative map remains available as a fallback. **No offline tile pack or service worker is included**, and this prototype does not promise that external map tiles will be available or cached offline. The simulation itself does not need a sensor network or backend.

## Run and check

- Open `index.html` in a modern browser. Internet access is only needed for the optional external map tiles.
- Run the regression checks with `npm test` (Node.js built-in test runner; no package install is needed).
- Rebuild the HTML copies and ZIP with `python3 tools/build_artifacts.py --also-app` from this folder. The optional `--also-app` keeps the adjacent `/app/index.html` copy in sync when the workspace source is present.

See [ARCHITECTURE.md](ARCHITECTURE.md) for how the prototype is organized and [VALIDATION.md](VALIDATION.md) for exactly what was checked and what was not.

## Files

- `index.html` — runnable single-file demo with embedded illustrative backdrop.
- `APP_SOURCE_readable.html` — readable source copy with the backdrop kept as a separate asset.
- `assets/aerial_bg.jpg` — illustrative image used by the packaged demo.
- `tests/` — fast logic, accessibility-rendering, and simulation regression checks.
- `tools/build_artifacts.py` — rebuild and consistency-check utility.
- `precision.py`, `leadtime.py`, `person_density.py`, `scenario.py`, `sweep.py`, and related scripts/CSV — older exploratory artifacts. Their outputs are synthetic research experiments, not application features or evidence of real-world accuracy, safety, or readiness.

## License

See [LICENSE](LICENSE).
