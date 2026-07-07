# Trial: daily-tool-drop *with* a roadmap vs *without* — evaluation

**Date:** 2026-07-07 · **Trial build:** `sources/outages.py` (Powercor VIC live electricity outages)

## The experiment

Run one `/daily-tool-drop` that **picks from the new `ROADMAP.md`** and compare it against the
counterfactual: the ad-hoc "pick whatever looks interesting today" process that produced the prior 54
sources. The counterfactual isn't hypothetical — its behaviour is recorded in `backlog.md`, so this is
a real before/after, not a thought experiment.

## Criteria (fixed before judging)

1. **Gap-fill** — opens new white space (domain / mechanic / geography / reusable class)?
2. **Hoard value** — H/M/L on the core filter (ephemeral × un-rebuildable).
3. **Gate efficiency** — recon spent on targets that turn out fenced.
4. **Strategic compounding** — leverage created (a reusable class) vs a one-off.
5. **Decision cost** — share of the run spent *choosing* a target vs *building* it.

## Result

| criterion | with roadmap → **outages** | without (ad-hoc, per `backlog.md`) |
|---|---|---|
| gap-fill | **new domain** (utilities, 12th genre) + **new reusable class** (ArcGIS FS) + AU | recent batches piled onto already-deep genres (weather/geohazard hit 14; more transit/electricity) — "interesting" defaults to the familiar |
| hoard value | **H** (per-outage lifecycle, nobody archives it) | mixed; several accidental **L** later corrected (octopus tagged HIGH→low-med; frankfurter; awattar) |
| gate efficiency | pre-screened: the ⛔ list steered me *past* NWS/OpenAQ/QLD-Health before I spent a request; still verified live | ~8 recorded dead-end recons (NWS, CoinGecko, BGG, Open-Meteo, DOC, Auckland Airport, WaterNSW, nswair-too-slow) |
| compounding | opened the **ArcGIS-FeatureService class** → dozens of NZ/AU utility+council instances are now ~30-line reskins (roadmap §2, row #2) | one-offs; each new source re-derived from zero |
| decision cost | **low** — took the top Tier-1 ✅ row; the run went into the *build* | **high** — target re-chosen from scratch every run |

**Better on 4 of 5, decisively on compounding + decision-cost. Neutral on one thing (below).**

## Honest counter-view (don't overclaim)

- **The roadmap selects; it does not build.** outages still needed live recon — the Playwright browser
  dead-end, cracking the service-worker-obfuscated Experience Builder config, discovering the point
  layer is id **1** not 0, and culling CitiPower/United Energy when their FeatureServers wouldn't
  query. The roadmap made the *target* better and cheaper to choose; the *build* was exactly as hard.
- **n = 1.** "Roadmap → better" rests on this single trial plus the *pattern* in the skip log, not a
  controlled A/B. Treat it as a strong prior, not proof.
- **A roadmap can anchor.** Committing to a list risks missing a serendipitous better target that
  wasn't on it. Mitigated by `ROADMAP.md` §4: re-verify gates live, and feed new finds back in.
- **It can't manufacture a clean high-value gate that doesn't exist.** The two *highest*-value gaps
  (health ED-waits, streaming rotation, real estate) are all 🟡/⛔; the two build-ready ✅ rows
  (USGS, NOAA) are low-hoard/archived. The roadmap's real service here is making that scarcity
  **visible and ranked** instead of discovering it by accident mid-build — which is *why* the trial
  correctly skipped the safe-but-low USGS/NOAA options for the higher-value ArcGIS-outages target.

## Verdict

**Yes — the roadmap-guided drop produced a better result than the likely ad-hoc pick**, and the win is
concentrated in *selection and de-risking*: it steered to genuine white space (a new domain) and a
reusable class, and it pre-marked the fences the ad-hoc process kept walking into. The build effort
itself is unchanged, and the evidence is one trial, so the honest claim is "better target selection
with lower decision cost and compounding leverage," not "strictly dominant every run." Adopt the
roadmap; keep the live-gate re-verification and the feed-back loop so it can't ossify.

## Follow-ups surfaced

- Grow the ArcGIS class (roadmap #2) next — highest leverage, gate mostly green per-org.
- Do one recon pass on **health ED wait times** (roadmap #6) — the single highest-value *new domain*
  still open; needs a state with a keyless page-called feed (ACT/SA/TAS/NSW).
- `outages` currently ships one network (Powercor). Add confirmed siblings as they're verified; the
  registry + runtime layer-resolution already support them.
