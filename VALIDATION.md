# Validation record and limitations

**Checked:** 2026-10-14  
**Status:** automated prototype checks passed; no claim of real-world accuracy or readiness.

## Automated regression checks

Run `npm test`. It uses Node.js's built-in test runner and needs no installed packages. The current suite checks:

- JavaScript syntax and exact shared density-band boundaries.
- MANUAL's 0–8 signal path into the red band, uniform zone values, alarm confirmation, and unchanged model-agent count when the signal is applied.
- Natural AUTO governor interpolation below the alarm line and MANUAL bypass behavior.
- Gate closure stopping admissions, the ordinary-mode last-gate guard, and gate-only versus dispatch-only AUTO behavior—including switches made during an active plan and accurate status wording.
- The cumulative eight-step Surge path crossing the 5.0 alarm line and latching the alarm at application-like 4-second display intervals built from 0.5-second simulation slices.
- Per-simulated-minute flow-rate conversion, safe query rendering with `textContent`, keyboard search behavior, and absence of the unvalidated forecast feature.
- Venue-change gate-list rebuilding and response/alarm reset hooks.

These tests exercise selected JavaScript functions in a Node VM. They are not a substitute for browser, sensor, venue, or emergency-response testing.

## Synthetic AUTO spot runs

The current source was exercised for 5,000 simulated seconds per preset, at 4× playback, using 0.5-second simulation slices and 1,250 density/risk samples (one sample per 4 simulated seconds):

| Preset | Peak sampled density | Ending model agents | Samples at/above 5.0 | Samples in red (6.5+) | Alarm latched |
| --- | ---: | ---: | ---: | ---: | --- |
| Maha Kumbh Mela | 4.138029 p/m² | 1,003 | 0 | 0 | No |
| Theresienwiese (Oktoberfest) | 4.456338 p/m² | 1,004 | 0 | 0 | No |
| Nairobi City Centre Gathering | 4.138029 p/m² | 1,001 | 0 | 0 | No |

These are three deterministic synthetic examples, not a sweep of all presets, crowd conditions, frame schedules, or real-world data. They do not prove a universal AUTO ceiling or a safety limit. The governor settings (3.5/4.7) are software choices, not calibrated values.

## Other behavior observations

- In the application-cadence eight-step Surge smoke run, the alarm latched after about 116 simulated seconds. The maximum sampled reading was about 6.05 p/m² in that run: it crossed the 5.0 alarm line but did **not** enter the 6.5 red color band. MANUAL has a separate explicit path to the red band; the test also confirms its value alone does not alter the agent count.
- AUTO path and MANUAL test signals are different controls. A high manual value latches the alarm only after the confirmation timer accumulates enough simulated time; pausing stops that timer.
- Gates affect only the model's admission throughput. The tests do not simulate real crowd rerouting, actual gate machinery, or deployed response units.

## Not tested or established

- No browser automation, cross-browser, mobile-screen-reader, or visual regression suite was run for this audit.
- No live sensors, venue attendance, camera/Wi-Fi/telecom feeds, incident records, dispatch systems, or route services were connected.
- No independent calibration, ground-truth comparison, epidemiological/engineering review, field exercise, privacy/security review, or operational approval was performed.
- Public map-tile availability and any browser-managed caching were not guaranteed. The application has no offline tile pack or service worker.
- Older research scripts and CSVs in this folder are exploratory synthetic artifacts and are not validation evidence for the shipped interface.

Passing these checks means only that the listed prototype behaviors were exercised. It does not certify crowd-safety performance, alarm suitability, density calibration, or operational readiness.
