# Architecture and behavior

This is one inline browser application, not a connected monitoring service. Its layers share synthetic state. No real sensor, venue-control, emergency-dispatch, public-safety, or route-planning integration is present.

## Layers

1. **Map and location** — shows the built-in venue list and optional public raster map tiles. A bundled illustrative background remains when tile requests fail. The home map's markers, colors, and numbers are demo presets. The local search checks the preset event/city list; there is no geocoder or remote venue search.
2. **Venue presets** — each event selects a hand-authored crowd-layout archetype, map position, footprint, and scenario-scale number. Preset sizes and preview colors are not attendance measurements or verified current event facts.
3. **Crowd model** — deterministic synthetic agents move through a simplified ground layout. AUTO admissions use the existing gradual feed and a synthetic density governor (`NATURAL_CROWD=1000`, `NATURAL_HOLD=3.5`, `NATURAL_CEIL=4.7`). MANUAL input is a separate synthetic display signal: it is applied uniformly to the zones and does not edit the agent list. Surge is a distinct cumulative eight-step arrival pulse. All are software behaviors, not measurements or venue calibration.
4. **Risk and display** — density bands come from one shared helper, so the dial, map, zones, and text use the same boundaries. Orange/high begins at 5.0; red begins at 6.5. Separately, the alarm timer starts at 5.0, accumulates simulated time, and latches at 45 seconds. Clearing uses the 4.5 hysteresis line. This difference is intentional: **alarm line and red color band are not the same threshold**.
5. **Response prototype** — gate mode and unit-dispatch mode are independent. Each can be MANUAL or AUTO. The simulator records gate toggles and unit commits; a closed gate only scales or stops admissions and does not reroute the crowd. Unit status, ETA, and plotted evacuation routes are illustrative, not live or validated.

## Timing and charts

- The application advances its model in 0.5-second simulation slices. The 1×, 2×, and 4× control changes how quickly those slices run against wall time.
- Entry and exit rates are computed from changes in cumulative counts divided by simulated elapsed time, then shown per simulated minute. The density chart uses a rolling 60-second **wall-clock** window; its trace can continue to show the last values while the simulation is paused.
- Alarm confirmation and clearing use simulated time, so they stop while the simulation is paused. MANUAL slider changes update the displayed synthetic signal and density trace without changing the model-agent count.
- The eight Surge presses are cumulative within a scenario. They reset when the operator returns Home or opens another venue; there is no RUSH selector.

## Input and accessibility

Search results are created as DOM nodes and inserted with `textContent`; the typed query is not used as HTML. Arrow keys move through results, Enter chooses one, and Escape closes the list. The venue picker returns focus to its trigger when closed. Map zoom, layer toggles, gate controls, zone selection, and the guidance disclosure have keyboard paths and accessible labels/states. The density slider exposes its current value and band. Charts expose text labels, but the canvas graphics themselves are not fully navigable data tables.

## Network, cache, and offline limits

- Only map imagery is fetched externally, from the selected public tile service. There is no API request for crowd, sensor, venue, unit, or route data.
- Tile load failures are tracked separately from initial loading. Failed tiles are retried; the app switches to its built-in illustrative map only when it has recorded tile failure. The fallback image is embedded in the runnable file.
- There is no service worker, application-managed persistent tile cache, bundled offline map, or guarantee that a browser's ordinary cache will retain map imagery. The local synthetic simulation and preset navigation remain usable without the external map tiles.

## Product boundary

This prototype has no validated calibration, operational controls, measured response-time model, legal review, privacy review, or field testing. Before any real-world use, it would require substantial integration and independent site-specific engineering, validation, and operational approval. The current code does not establish that it is safe, accurate, or ready for deployment.
