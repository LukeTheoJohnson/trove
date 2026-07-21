"""Well-coupled example for DashboardStudio: rainfall -> river flow (catchment lag).

The honest causal pair from trove's "wide data" set: metno's forecast/observed rainfall
and gwrivers' river flow. Rain doesn't hit the gauge instantly - it soaks the catchment
and drains through it, so flow is rainfall *convolved with a decaying impulse response*
(a unit hydrograph) plus baseflow. The coupling is real but lagged: same-hour rain barely
predicts flow; an exponentially-weighted sum of recent rain (a standard antecedent-rainfall
index) predicts it tightly.

trove's own series is data-starved until the pollers accumulate, so this simulates the
mechanism the two sources would hoard - two Wellington catchments with different lag and
flashiness - then feeds it to DashboardStudio and opens the rendered HTML. Correlations are
computed *within* each catchment (pooling gauges of different scale would mask the link) and
the numbers in the insight cards are recomputed from the generated frame, not asserted.
"""
from __future__ import annotations

import os
import sys
import webbrowser
from pathlib import Path

import numpy as np
import pandas as pd

# Import DashboardStudio without needing it pip-installed. Override the checkout location with
# DASHBOARD_STUDIO_PATH; falls back to the local default so a bare clone still runs on this box.
sys.path.insert(0, os.environ.get("DASHBOARD_STUDIO_PATH", r"C:\Users\lukej\dashboard-studio"))
from dashboard_studio import Dashboard  # noqa: E402

HERE = Path(__file__).resolve().parent
RNG = np.random.default_rng(42)
HOURS = 24 * 21  # three weeks, hourly


def _unit_hydrograph(peak_h: float, length: int = 72) -> np.ndarray:
    """Gamma-shaped catchment impulse response peaking ~peak_h hours after rain."""
    t = np.arange(length)
    a, b = 2.2, peak_h / 2.2          # gamma peak sits at a*b = peak_h
    h = (t ** a) * np.exp(-t / b)
    return h / h.sum()


def _storms(n_hours: int) -> np.ndarray:
    """Sparse, bursty rainfall (mm/h): mostly dry with a handful of storm cells."""
    rain = np.zeros(n_hours)
    for start in RNG.integers(0, n_hours - 12, size=9):
        dur = int(RNG.integers(3, 10))
        peak = RNG.uniform(2, 11)
        shape = np.sin(np.linspace(0, np.pi, dur)) ** 2
        rain[start:start + dur] += peak * shape * RNG.uniform(0.7, 1.3, dur)
    return np.round(rain, 2)


def _catchment(name: str, rain: np.ndarray, peak_h: float, baseflow: float,
               gain: float) -> pd.DataFrame:
    """One gauge: flow = baseflow + gain * (rain * unit_hydrograph) + noise."""
    resp = np.convolve(rain, _unit_hydrograph(peak_h), mode="full")[:len(rain)]
    flow = baseflow + gain * resp + RNG.normal(0, baseflow * 0.02, len(rain))
    flow = np.round(np.maximum(flow, baseflow * 0.6), 2)

    # Antecedent rainfall index: exp-weighted sum of the prior ~2 days of rain, with the
    # catchment's own memory (tau ~ its lag). This is the physical driver of flow.
    tau = peak_h * 1.5
    ak = np.exp(-np.arange(48) / tau)
    antecedent = np.convolve(rain, ak, mode="full")[:len(rain)]

    df = pd.DataFrame({"hour": np.arange(len(rain)), "catchment": name,
                       "rain_mm": rain, "antecedent_mm": np.round(antecedent, 2),
                       "flow_cumecs": flow})
    delta = np.diff(flow, prepend=flow[0])
    df["rising"] = np.where(delta > baseflow * 0.02, "yes", "no")
    thresh = baseflow * 1.1
    df["regime"] = np.where(flow < thresh, "baseflow",
                            np.where(delta > 0, "rising", "receding"))
    return df


def _within_catchment_corr(df: pd.DataFrame, col: str) -> float:
    """Mean of the per-catchment corr(col, flow) - pooling gauges of different scale masks it."""
    rs = [g[col].corr(g["flow_cumecs"]) for _, g in df.groupby("catchment")]
    return float(np.mean(rs))


def _lag_of_peak_corr(df: pd.DataFrame, max_lag: int = 18) -> int:
    """Hours of shift that maximises corr(rain shifted forward, flow) - the catchment lag."""
    best_lag, best_r = 0, -1.0
    for lag in range(max_lag + 1):
        r = df["rain_mm"].shift(lag).corr(df["flow_cumecs"])
        if pd.notna(r) and r > best_r:
            best_lag, best_r = lag, r
    return best_lag


def build() -> pd.DataFrame:
    rain_a = _storms(HOURS)
    rain_b = _storms(HOURS)
    a = _catchment("Hutt @ Kaitoke", rain_a, peak_h=3.0, baseflow=2.5, gain=1.4)     # flashy
    b = _catchment("Ruamahanga @ Wardells", rain_b, peak_h=10.0, baseflow=9.0, gain=3.1)  # slow
    return pd.concat([a, b], ignore_index=True)


def main() -> None:
    df = build()
    df.to_csv(HERE / "rain_river_coupling.csv", index=False, encoding="utf-8")

    # Numbers for the insight cards - recomputed within catchment, not asserted.
    r_same = _within_catchment_corr(df, "rain_mm")
    r_ante = _within_catchment_corr(df, "antecedent_mm")
    lag_a = _lag_of_peak_corr(df[df.catchment == "Hutt @ Kaitoke"])
    lag_b = _lag_of_peak_corr(df[df.catchment == "Ruamahanga @ Wardells"])
    wet = df["antecedent_mm"] > df["antecedent_mm"].quantile(0.9)
    rise_wet = (df.loc[wet, "rising"] == "yes").mean()
    rise_dry = (df.loc[~wet, "rising"] == "yes").mean()
    print(f"within-catchment r: same-hour rain {r_same:.2f}   antecedent {r_ante:.2f}")
    print(f"peak-corr lag: Hutt {lag_a}h, Ruamahanga {lag_b}h")
    print(f"rise prob: wettest decile {rise_wet:.0%} vs rest {rise_dry:.0%}")

    dash = (Dashboard("Rainfall -> River Flow", df, client="trove - metno x gwrivers",
                      theme="midnight")
            .story(title="Flow follows rain on a lag - the catchment is a low-pass filter",
                   thesis=f"Same-hour rain barely predicts flow (r={r_same:.2f}); an exp-weighted "
                          f"sum of recent rain predicts it tightly (r={r_ante:.2f}). The flashy "
                          f"Hutt peaks ~{lag_a}h after rain; the larger Ruamahanga ~{lag_b}h.",
                   thread="Illustrative simulation of the metno x gwrivers coupling (a catchment "
                          "unit-hydrograph). The real as-issued series needs the pollers armed to "
                          "accumulate - this shows the shape the wide-data study would measure.")
            .kpi("Rain total (mm)", "rain_mm", agg="sum", fmt="number")
            .kpi("Peak flow (cumecs)", "flow_cumecs", agg="max", fmt="number")
            .kpi("Gauge-hours logged", "hour", agg="count", fmt="integer")
            .scatter("Flow tracks antecedent (recent, exp-weighted) rain", x="antecedent_mm",
                     y="flow_cumecs", color="catchment")
            .scatter("...but the current hour of rain hardly moves it (the lag hides the link)",
                     x="rain_mm", y="flow_cumecs", color="catchment")
            .rate("Probability the river is rising, by antecedent rainfall",
                  x="antecedent_mm", target="rising")
            .box("Flow by hydrological regime", x="regime", y="flow_cumecs")
            .heatmap("Numeric correlations (antecedent rain >> same-hour rain)")
            .order("regime", ["baseflow", "rising", "receding"])
            .filter_by("catchment")
            .slider("hour")
            .insight("Why doesn't flow spike the moment it rains?",
                     "The catchment stores and drains the water, so flow is rain passed through "
                     f"a lag. Same-hour correlation is only {r_same:.2f}; an exp-weighted sum of "
                     f"recent rain lifts it to {r_ante:.2f}.",
                     [f"r(same-hour) = {r_same:.2f}", f"r(antecedent) = {r_ante:.2f}"])
            .insight("Do the two catchments respond at the same speed?",
                     f"No. The small, steep Hutt is flashy - flow peaks about {lag_a}h after rain - "
                     f"while the larger Ruamahanga lags ~{lag_b}h. Same physics, different time "
                     "constant.",
                     [f"Hutt peak-lag ~{lag_a}h", f"Ruamahanga peak-lag ~{lag_b}h"])
            .insight("Does antecedent rain predict a rising river?",
                     f"Strongly. In the wettest decile of antecedent rain the river is rising "
                     f"{rise_wet:.0%} of the time, versus {rise_dry:.0%} otherwise.",
                     [f"wettest decile {rise_wet:.0%}", f"rest {rise_dry:.0%}"]))

    out = dash.save(str(HERE / "rain_river_coupling.html"))
    print("wrote", out)
    webbrowser.open(Path(out).resolve().as_uri())


if __name__ == "__main__":
    main()
