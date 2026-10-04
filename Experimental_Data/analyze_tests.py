"""
analysis_gui.py
General experimental-data analysis GUI for the VR teleoperation project.

Modules:
- IMU
- Haptic
- Buttons
- Bluetooth
- Complete Controller

Input and output are selected entirely through the GUI.
Each exported figure is a separate 300-DPI PNG.
"""

from pathlib import Path
import re
import traceback
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

import numpy as np
import pandas as pd
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk


APP_TITLE = "Teleoperation - Experimental Data Analysis"
VERSION = "2.0 - Complete"
DPI = 300

TESTS = ["IMU", "Haptic", "Buttons", "Bluetooth", "Complete Controller"]

REQUIRED = {
    "IMU": {"sample", "timestamp", "elapsed_s", "pitch_deg", "roll_deg", "test"},
    "Haptic": {"timestamp", "elapsed_s", "command"},
    "Buttons": {"event", "timestamp", "elapsed_s", "grab", "forward", "backward"},
    "Bluetooth": {"timestamp", "elapsed_s", "type", "value_1", "value_2"},
    "Complete Controller": {
        "timestamp", "elapsed_s", "type", "packet", "pitch_deg", "roll_deg",
        "linear", "angular", "grab", "forward", "backward", "extra"
    },
}


# ============================================================
# Helpers
# ============================================================

def num(s):
    return pd.to_numeric(s, errors="coerce")


def clean_num(s):
    return num(s).dropna()


def fmt(x, n=3):
    return "N/A" if pd.isna(x) else f"{x:.{n}f}"


def safe_mean(s):
    x = clean_num(s)
    return x.mean() if len(x) else np.nan


def safe_std(s):
    x = clean_num(s)
    return x.std(ddof=1) if len(x) > 1 else np.nan


def safe_min(s):
    x = clean_num(s)
    return x.min() if len(x) else np.nan


def safe_max(s):
    x = clean_num(s)
    return x.max() if len(x) else np.nan


def duration(df):
    t = clean_num(df["elapsed_s"])
    return float(t.max() - t.min()) if len(t) > 1 else 0.0


def positive_dt(df):
    t = num(df["elapsed_s"]).dropna().sort_values()
    return t.diff().dropna().loc[lambda x: x > 0]


def sample_rate(df):
    dt = positive_dt(df)
    return 1.0 / dt.mean() if len(dt) and dt.mean() > 0 else np.nan


def base_figure(title, xlabel, ylabel, size=(8.0, 4.8)):
    fig = Figure(figsize=size, dpi=100)
    ax = fig.add_subplot(111)
    ax.set_title(title)
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.grid(True, alpha=0.3)
    return fig, ax


def save_figure(fig, path):
    fig.savefig(path, dpi=DPI, bbox_inches="tight")


def transitions_from_binary(s):
    x = num(s).fillna(0).astype(int)
    prev = x.shift(1, fill_value=0)
    rising = int(((x == 1) & (prev == 0)).sum())
    falling = int(((x == 0) & (prev == 1)).sum())
    return rising, falling


def sequence_metrics(seq):
    s = num(seq).dropna().astype(int).reset_index(drop=True)
    if len(s) == 0:
        return {
            "count": 0, "first": np.nan, "last": np.nan,
            "expected": 0, "missing": 0, "discontinuities": 0
        }

    diffs = s.diff().dropna()
    forward_gaps = diffs[diffs > 1]
    missing = int((forward_gaps - 1).sum())
    discontinuities = int((diffs != 1).sum())

    # Expected count assumes a monotonic sequence range. Missing is calculated
    # only from positive forward gaps, so resets/reordering are not miscounted.
    expected = int(s.max() - s.min() + 1)

    return {
        "count": len(s),
        "first": int(s.iloc[0]),
        "last": int(s.iloc[-1]),
        "expected": expected,
        "missing": missing,
        "discontinuities": discontinuities,
    }


class BaseAnalyzer:
    def __init__(self, df, path):
        self.df = df.copy()
        self.path = Path(path)
        self.prepare()

    def prepare(self):
        self.df["elapsed_s"] = num(self.df["elapsed_s"])

    def info(self):
        return {
            "rows": len(self.df),
            "duration_s": duration(self.df),
        }

    def figures(self):
        return list(self.figure_map().keys())

    def create_figure(self, name):
        fmap = self.figure_map()
        if name not in fmap:
            raise ValueError(f"Unknown figure: {name}")
        return fmap[name][1]()

    def export_all(self, selected_folder):
        root = Path(selected_folder)
        stem = re.sub(r"[^A-Za-z0-9_.-]+", "_", self.path.stem)
        out = root / stem
        out.mkdir(parents=True, exist_ok=True)

        exported = []
        for name, (filename, func) in self.figure_map().items():
            fig = func()
            p = out / filename
            save_figure(fig, p)
            exported.append(p)

        summary = out / "summary.csv"
        self.summary_dataframe().to_csv(summary, index=False)
        exported.append(summary)

        report = out / "analysis.txt"
        report.write_text(self.text_report(), encoding="utf-8")
        exported.append(report)

        return out, exported


# ============================================================
# IMU
# ============================================================

class IMUAnalyzer(BaseAnalyzer):
    def prepare(self):
        super().prepare()
        for c in ["sample", "pitch_deg", "roll_deg"]:
            self.df[c] = num(self.df[c])
        self.df["test"] = self.df["test"].fillna("UNLABELED").astype(str).str.strip().str.upper()
        self.df = self.df.dropna(subset=["elapsed_s", "pitch_deg", "roll_deg"]).sort_values("elapsed_s").reset_index(drop=True)
        if self.df.empty:
            raise ValueError("No valid IMU samples.")
        self.df["t"] = self.df["elapsed_s"] - self.df["elapsed_s"].iloc[0]

    def summary_dataframe(self):
        rows = []
        for label, g in self.df.groupby("test", sort=False):
            rows.append({
                "test": label, "samples": len(g), "duration_s": duration(g),
                "pitch_mean_deg": safe_mean(g.pitch_deg), "pitch_std_deg": safe_std(g.pitch_deg),
                "pitch_min_deg": safe_min(g.pitch_deg), "pitch_max_deg": safe_max(g.pitch_deg),
                "roll_mean_deg": safe_mean(g.roll_deg), "roll_std_deg": safe_std(g.roll_deg),
                "roll_min_deg": safe_min(g.roll_deg), "roll_max_deg": safe_max(g.roll_deg),
            })
        return pd.DataFrame(rows)

    def text_report(self):
        s = self.summary_dataframe()
        lines = [
            "=" * 72, "IMU EXPERIMENTAL DATA ANALYSIS", "=" * 72,
            f"Source: {self.path.name}",
            f"Valid samples: {len(self.df)}",
            f"Duration [s]: {fmt(duration(self.df),4)}",
            f"Estimated sample rate [Hz]: {fmt(sample_rate(self.df),3)}", ""
        ]
        for _, r in s.iterrows():
            lines += [
                f"TEST: {r['test']}",
                f"  Samples: {int(r['samples'])}",
                f"  Pitch mean/std/min/max [deg]: {fmt(r['pitch_mean_deg'])} / {fmt(r['pitch_std_deg'])} / {fmt(r['pitch_min_deg'])} / {fmt(r['pitch_max_deg'])}",
                f"  Roll  mean/std/min/max [deg]: {fmt(r['roll_mean_deg'])} / {fmt(r['roll_std_deg'])} / {fmt(r['roll_min_deg'])} / {fmt(r['roll_max_deg'])}",
                ""
            ]
        return "\n".join(lines)

    def fig_orientation_time(self):
        fig, ax = base_figure("IMU Orientation vs Time", "Time [s]", "Angle [deg]")
        ax.plot(self.df.t, self.df.pitch_deg, label="Pitch", linewidth=1.1)
        ax.plot(self.df.t, self.df.roll_deg, label="Roll", linewidth=1.1)
        ax.axhline(0, linestyle="--", linewidth=0.8)
        ax.legend()
        fig.tight_layout()
        return fig

    def fig_pitch_time(self):
        fig, ax = base_figure("Pitch vs Time", "Time [s]", "Pitch [deg]")
        ax.plot(self.df.t, self.df.pitch_deg, linewidth=1.1)
        ax.axhline(0, linestyle="--", linewidth=0.8)
        fig.tight_layout()
        return fig

    def fig_roll_time(self):
        fig, ax = base_figure("Roll vs Time", "Time [s]", "Roll [deg]")
        ax.plot(self.df.t, self.df.roll_deg, linewidth=1.1)
        ax.axhline(0, linestyle="--", linewidth=0.8)
        fig.tight_layout()
        return fig

    def fig_means(self):
        s = self.summary_dataframe()
        fig, ax = base_figure("Mean Orientation by Test", "Test", "Mean angle [deg]", (8.5, 5.0))
        x = np.arange(len(s)); w = 0.36
        ax.bar(x-w/2, s.pitch_mean_deg, w, label="Pitch")
        ax.bar(x+w/2, s.roll_mean_deg, w, label="Roll")
        ax.set_xticks(x, s.test, rotation=30, ha="right")
        ax.axhline(0, linewidth=0.8)
        ax.legend()
        fig.tight_layout()
        return fig

    def fig_pitch_box(self):
        labels = list(self.df.test.drop_duplicates())
        data = [self.df.loc[self.df.test == x, "pitch_deg"].dropna() for x in labels]
        fig, ax = base_figure("Pitch Distribution by Test", "Test", "Pitch [deg]", (8.5, 5.0))
        ax.boxplot(data, tick_labels=labels, showfliers=False)
        ax.tick_params(axis="x", rotation=30)
        fig.tight_layout()
        return fig

    def fig_roll_box(self):
        labels = list(self.df.test.drop_duplicates())
        data = [self.df.loc[self.df.test == x, "roll_deg"].dropna() for x in labels]
        fig, ax = base_figure("Roll Distribution by Test", "Test", "Roll [deg]", (8.5, 5.0))
        ax.boxplot(data, tick_labels=labels, showfliers=False)
        ax.tick_params(axis="x", rotation=30)
        fig.tight_layout()
        return fig

    def fig_neutral(self):
        g = self.df[self.df.test.str.contains("NEUTRAL", na=False)].copy()
        if g.empty:
            raise ValueError("No NEUTRAL samples in this file.")
        g["tn"] = np.arange(len(g))
        fig, ax = base_figure("Neutral-State Stability", "Neutral sample index", "Angle [deg]")
        ax.plot(g.tn, g.pitch_deg, label="Pitch", linewidth=1.0)
        ax.plot(g.tn, g.roll_deg, label="Roll", linewidth=1.0)
        ax.axhline(0, linestyle="--", linewidth=0.8)
        ax.legend()
        fig.tight_layout()
        return fig

    def figure_map(self):
        m = {
            "Orientation vs Time": ("01_orientation_time.png", self.fig_orientation_time),
            "Pitch vs Time": ("02_pitch_time.png", self.fig_pitch_time),
            "Roll vs Time": ("03_roll_time.png", self.fig_roll_time),
            "Mean Orientation by Test": ("04_mean_orientation_by_test.png", self.fig_means),
            "Pitch Distribution by Test": ("05_pitch_distribution.png", self.fig_pitch_box),
            "Roll Distribution by Test": ("06_roll_distribution.png", self.fig_roll_box),
        }
        if self.df.test.str.contains("NEUTRAL", na=False).any():
            m["Neutral Stability"] = ("07_neutral_stability.png", self.fig_neutral)
        return m


# ============================================================
# Haptic
# ============================================================

class HapticAnalyzer(BaseAnalyzer):
    def prepare(self):
        super().prepare()
        self.df["command"] = self.df["command"].fillna("").astype(str).str.strip().str.upper()
        self.df = self.df.dropna(subset=["elapsed_s"]).sort_values("elapsed_s").reset_index(drop=True)
        if self.df.empty:
            raise ValueError("No valid haptic records.")

        def parse(c):
            m = re.fullmatch(r"(M1|M2|BOTH),(\d+(?:\.\d+)?)", c)
            if m:
                return m.group(1), float(m.group(2))
            if c in {"H0", "H1", "H2", "STOP", "STATUS"}:
                return c, np.nan
            return "OTHER", np.nan

        parsed = self.df.command.map(parse)
        self.df["category"] = [x[0] for x in parsed]
        self.df["intensity_pct"] = [x[1] for x in parsed]
        self.df["t"] = self.df.elapsed_s - self.df.elapsed_s.iloc[0]

    def summary_dataframe(self):
        rows = []
        for cat, g in self.df.groupby("category", sort=False):
            vals = g.intensity_pct.dropna()
            rows.append({
                "category": cat, "count": len(g),
                "mean_intensity_pct": vals.mean() if len(vals) else np.nan,
                "min_intensity_pct": vals.min() if len(vals) else np.nan,
                "max_intensity_pct": vals.max() if len(vals) else np.nan,
            })
        return pd.DataFrame(rows)

    def text_report(self):
        counts = self.df.category.value_counts()
        lines = [
            "="*72, "HAPTIC EXPERIMENTAL DATA ANALYSIS", "="*72,
            f"Source: {self.path.name}", f"Records: {len(self.df)}",
            f"Duration [s]: {fmt(duration(self.df),4)}", "",
            "COMMAND COUNTS"
        ]
        for k, v in counts.items():
            lines.append(f"  {k}: {v}")
        for ch in ["M1", "M2", "BOTH"]:
            x = self.df.loc[self.df.category == ch, "intensity_pct"].dropna()
            if len(x):
                lines += ["", f"{ch} intensity [%]: mean={fmt(x.mean())}, min={fmt(x.min())}, max={fmt(x.max())}"]
        return "\n".join(lines)

    def fig_intensity(self):
        g = self.df[self.df.category.isin(["M1", "M2", "BOTH"])].copy()
        fig, ax = base_figure("Manual Haptic Intensity Commands", "Time [s]", "Commanded intensity [%]")
        for cat in ["M1", "M2", "BOTH"]:
            q = g[g.category == cat]
            if len(q):
                ax.scatter(q.t, q.intensity_pct, label=cat, s=28)
        ax.set_ylim(-5, 105)
        ax.legend()
        fig.tight_layout()
        return fig

    def fig_counts(self):
        order = ["M1", "M2", "BOTH", "H0", "H1", "H2", "STOP", "STATUS", "OTHER"]
        counts = self.df.category.value_counts()
        labels = [x for x in order if x in counts.index]
        values = [counts[x] for x in labels]
        fig, ax = base_figure("Haptic Command Counts", "Command type", "Count")
        ax.bar(labels, values)
        fig.tight_layout()
        return fig

    def fig_patterns(self):
        g = self.df[self.df.category.isin(["H0", "H1", "H2"])].copy()
        mapping = {"H0": 0, "H1": 1, "H2": 2}
        fig, ax = base_figure("Haptic Pattern Events", "Time [s]", "Pattern")
        ax.scatter(g.t, g.category.map(mapping), s=34)
        ax.set_yticks([0, 1, 2], ["H0", "H1", "H2"])
        fig.tight_layout()
        return fig

    def figure_map(self):
        return {
            "Manual Intensity Commands": ("01_manual_intensity_commands.png", self.fig_intensity),
            "Command Counts": ("02_command_counts.png", self.fig_counts),
            "Haptic Pattern Events": ("03_haptic_pattern_events.png", self.fig_patterns),
        }


# ============================================================
# Buttons
# ============================================================

class ButtonsAnalyzer(BaseAnalyzer):
    def prepare(self):
        super().prepare()
        for c in ["event", "grab", "forward", "backward"]:
            self.df[c] = num(self.df[c])
        self.df = self.df.dropna(subset=["elapsed_s", "grab", "forward", "backward"]).sort_values("elapsed_s").reset_index(drop=True)
        for c in ["grab", "forward", "backward"]:
            self.df[c] = self.df[c].astype(int)
        if self.df.empty:
            raise ValueError("No valid button records.")
        self.df["t"] = self.df.elapsed_s - self.df.elapsed_s.iloc[0]
        self.df["combination"] = self.df.apply(
            lambda r: f"G{r.grab} F{r.forward} B{r.backward}", axis=1
        )

    def summary_dataframe(self):
        rows = []
        for c in ["grab", "forward", "backward"]:
            rising, falling = transitions_from_binary(self.df[c])
            rows.append({
                "button": c, "presses_rising_edges": rising,
                "releases_falling_edges": falling,
                "records_active": int((self.df[c] == 1).sum())
            })
        return pd.DataFrame(rows)

    def text_report(self):
        s = self.summary_dataframe()
        lines = [
            "="*72, "BUTTONS EXPERIMENTAL DATA ANALYSIS", "="*72,
            f"Source: {self.path.name}", f"Recorded state-change rows: {len(self.df)}",
            f"Duration [s]: {fmt(duration(self.df),4)}", ""
        ]
        for _, r in s.iterrows():
            lines.append(
                f"{r.button}: presses={int(r.presses_rising_edges)}, "
                f"releases={int(r.releases_falling_edges)}, active rows={int(r.records_active)}"
            )
        lines += ["", "STATE COMBINATIONS"]
        for k, v in self.df.combination.value_counts().items():
            lines.append(f"  {k}: {v}")
        return "\n".join(lines)

    def fig_states(self):
        fig, ax = base_figure("Button States vs Time", "Time [s]", "State")
        ax.step(self.df.t, self.df.grab + 2, where="post", label="Grab")
        ax.step(self.df.t, self.df.forward + 1, where="post", label="Forward")
        ax.step(self.df.t, self.df.backward, where="post", label="Backward")
        ax.set_yticks([0,1,2,3], ["B:0","B:1 / F:0","F:1 / G:0","G:1"])
        ax.legend()
        fig.tight_layout()
        return fig

    def fig_presses(self):
        s = self.summary_dataframe()
        fig, ax = base_figure("Detected Button Presses", "Button", "Rising-edge count")
        ax.bar(["Grab", "Forward", "Backward"], s.presses_rising_edges)
        fig.tight_layout()
        return fig

    def fig_combinations(self):
        counts = self.df.combination.value_counts().sort_index()
        fig, ax = base_figure("Recorded Button-State Combinations", "State combination", "Recorded events", (8.2, 4.8))
        ax.bar(counts.index, counts.values)
        ax.tick_params(axis="x", rotation=30)
        fig.tight_layout()
        return fig

    def figure_map(self):
        return {
            "Button States vs Time": ("01_button_states_time.png", self.fig_states),
            "Detected Button Presses": ("02_button_presses.png", self.fig_presses),
            "State Combinations": ("03_state_combinations.png", self.fig_combinations),
        }


# ============================================================
# Bluetooth
# ============================================================

class BluetoothAnalyzer(BaseAnalyzer):
    def prepare(self):
        super().prepare()
        self.df["type"] = self.df["type"].fillna("").astype(str).str.strip().str.upper()
        self.df = self.df.dropna(subset=["elapsed_s"]).sort_values("elapsed_s").reset_index(drop=True)
        self.data = self.df[self.df.type == "DATA"].copy()
        self.pong = self.df[self.df.type == "PONG"].copy()
        if self.data.empty:
            raise ValueError("No DATA packets found.")
        self.data["sequence"] = num(self.data.value_1)
        self.data["device_time"] = num(self.data.value_2)
        self.data = self.data.dropna(subset=["sequence"])
        self.data["sequence"] = self.data.sequence.astype(int)
        self.data["dt_s"] = self.data.elapsed_s.diff()
        self.data["t"] = self.data.elapsed_s - self.data.elapsed_s.iloc[0]
        self.pong["rtt_ms"] = num(self.pong.value_2)

    def summary_dataframe(self):
        sm = sequence_metrics(self.data.sequence)
        dt = self.data.dt_s[(self.data.dt_s > 0)]
        rtt = self.pong.rtt_ms.dropna()
        return pd.DataFrame([{
            "data_packets": len(self.data),
            "duration_s": duration(self.data),
            "average_receive_rate_hz": (len(self.data)-1)/duration(self.data) if duration(self.data) > 0 else np.nan,
            "mean_interarrival_ms": dt.mean()*1000 if len(dt) else np.nan,
            "std_interarrival_ms": dt.std(ddof=1)*1000 if len(dt)>1 else np.nan,
            "sequence_first": sm["first"], "sequence_last": sm["last"],
            "missing_sequence_numbers": sm["missing"],
            "sequence_discontinuities": sm["discontinuities"],
            "rtt_samples": len(rtt),
            "rtt_mean_ms": rtt.mean() if len(rtt) else np.nan,
            "rtt_std_ms": rtt.std(ddof=1) if len(rtt)>1 else np.nan,
            "rtt_min_ms": rtt.min() if len(rtt) else np.nan,
            "rtt_max_ms": rtt.max() if len(rtt) else np.nan,
        }])

    def text_report(self):
        r = self.summary_dataframe().iloc[0]
        return "\n".join([
            "="*72, "BLUETOOTH EXPERIMENTAL DATA ANALYSIS", "="*72,
            f"Source: {self.path.name}",
            f"DATA packets: {int(r.data_packets)}",
            f"DATA duration [s]: {fmt(r.duration_s,4)}",
            f"Average receive rate [packet/s]: {fmt(r.average_receive_rate_hz,3)}",
            f"Mean inter-arrival [ms]: {fmt(r.mean_interarrival_ms,3)}",
            f"Sequence: {int(r.sequence_first)} -> {int(r.sequence_last)}",
            f"Missing sequence numbers from forward gaps: {int(r.missing_sequence_numbers)}",
            f"Sequence discontinuities: {int(r.sequence_discontinuities)}",
            "",
            f"RTT samples: {int(r.rtt_samples)}",
            f"RTT mean/std/min/max [ms]: {fmt(r.rtt_mean_ms)} / {fmt(r.rtt_std_ms)} / {fmt(r.rtt_min_ms)} / {fmt(r.rtt_max_ms)}",
            "",
            "NOTE: RTT is round-trip time; it is not one-way latency."
        ])

    def fig_interarrival(self):
        g = self.data[(self.data.dt_s > 0) & (self.data.dt_s < self.data.dt_s.quantile(0.9995))]
        fig, ax = base_figure("Bluetooth Packet Inter-arrival Time", "Time [s]", "Inter-arrival time [ms]")
        ax.plot(g.t, g.dt_s*1000, linewidth=0.7)
        fig.tight_layout()
        return fig

    def fig_rate(self):
        g = self.data.copy()
        start = np.floor(g.elapsed_s.min())
        end = np.ceil(g.elapsed_s.max())
        bins = np.arange(start, end + 1, 1.0)
        counts, edges = np.histogram(g.elapsed_s, bins=bins)
        centers = edges[:-1] - edges[0] + 0.5
        fig, ax = base_figure("Bluetooth Receive Rate", "Time [s]", "Packets received per second")
        ax.plot(centers, counts, linewidth=1.0)
        fig.tight_layout()
        return fig

    def fig_rtt(self):
        g = self.pong.dropna(subset=["rtt_ms"]).copy()
        if g.empty:
            raise ValueError("No RTT measurements.")
        t = g.elapsed_s - self.df.elapsed_s.iloc[0]
        fig, ax = base_figure("Bluetooth RTT Measurements", "Time [s]", "RTT [ms]")
        ax.plot(t, g.rtt_ms, marker="o", linewidth=1.0)
        fig.tight_layout()
        return fig

    def fig_gaps(self):
        g = self.data.copy()
        g["seq_diff"] = g.sequence.diff()
        gaps = g[g.seq_diff != 1].dropna(subset=["seq_diff"])
        fig, ax = base_figure("Bluetooth Sequence Discontinuities", "Time [s]", "Sequence step")
        if len(gaps):
            ax.scatter(gaps.t, gaps.seq_diff, s=28)
            ax.axhline(1, linestyle="--", linewidth=0.8)
        else:
            ax.text(0.5, 0.5, "No sequence discontinuities detected",
                    transform=ax.transAxes, ha="center", va="center")
        fig.tight_layout()
        return fig

    def figure_map(self):
        m = {
            "Receive Rate": ("01_receive_rate.png", self.fig_rate),
            "Packet Inter-arrival Time": ("02_interarrival_time.png", self.fig_interarrival),
            "Sequence Discontinuities": ("03_sequence_discontinuities.png", self.fig_gaps),
        }
        if self.pong.rtt_ms.notna().any():
            m["RTT Measurements"] = ("04_rtt_measurements.png", self.fig_rtt)
        return m


# ============================================================
# Complete Controller
# ============================================================

class ControllerAnalyzer(BaseAnalyzer):
    def prepare(self):
        super().prepare()
        self.df["type"] = self.df["type"].fillna("").astype(str).str.strip().str.upper()
        self.df["extra"] = self.df["extra"].fillna("").astype(str)
        self.df = self.df.dropna(subset=["elapsed_s"]).sort_values("elapsed_s").reset_index(drop=True)

        self.ctrl = self.df[self.df.type == "CTRL"].copy()
        if self.ctrl.empty:
            raise ValueError("No CTRL records found.")

        for c in ["packet","pitch_deg","roll_deg","linear","angular","grab","forward","backward"]:
            self.ctrl[c] = num(self.ctrl[c])
        self.ctrl = self.ctrl.dropna(subset=["packet","pitch_deg","roll_deg","linear","angular"])
        self.ctrl["packet"] = self.ctrl.packet.astype(int)
        self.ctrl["t"] = self.ctrl.elapsed_s - self.ctrl.elapsed_s.iloc[0]

        self.rtt = self.df[self.df.type == "RTT"].copy()
        self.rtt["rtt_ms"] = num(self.rtt.extra)

        self.haptic = self.df[
            self.df.extra.str.fullmatch(r"EVENT,H[012]", case=False, na=False)
        ].copy()
        self.haptic["event"] = self.haptic.extra.str.upper().str.replace("EVENT,", "", regex=False)

    def summary_dataframe(self):
        sm = sequence_metrics(self.ctrl.packet)
        dt = self.ctrl.elapsed_s.diff()
        dt = dt[dt > 0]
        rtt = self.rtt.rtt_ms.dropna()
        return pd.DataFrame([{
            "ctrl_packets": len(self.ctrl),
            "duration_s": duration(self.ctrl),
            "average_receive_rate_hz": (len(self.ctrl)-1)/duration(self.ctrl) if duration(self.ctrl)>0 else np.nan,
            "pitch_min_deg": self.ctrl.pitch_deg.min(), "pitch_max_deg": self.ctrl.pitch_deg.max(),
            "roll_min_deg": self.ctrl.roll_deg.min(), "roll_max_deg": self.ctrl.roll_deg.max(),
            "linear_min": self.ctrl.linear.min(), "linear_max": self.ctrl.linear.max(),
            "angular_min": self.ctrl.angular.min(), "angular_max": self.ctrl.angular.max(),
            "grab_active_records": int((self.ctrl.grab == 1).sum()),
            "forward_active_records": int((self.ctrl.forward == 1).sum()),
            "backward_active_records": int((self.ctrl.backward == 1).sum()),
            "missing_sequence_numbers": sm["missing"],
            "sequence_discontinuities": sm["discontinuities"],
            "haptic_events": len(self.haptic),
            "rtt_samples": len(rtt),
            "rtt_mean_ms": rtt.mean() if len(rtt) else np.nan,
        }])

    def text_report(self):
        r = self.summary_dataframe().iloc[0]
        counts = self.df.type.value_counts()
        lines = [
            "="*72, "COMPLETE CONTROLLER EXPERIMENTAL DATA ANALYSIS", "="*72,
            f"Source: {self.path.name}",
            f"CTRL packets: {int(r.ctrl_packets)}",
            f"CTRL duration [s]: {fmt(r.duration_s,4)}",
            f"Average receive rate [packet/s]: {fmt(r.average_receive_rate_hz,3)}",
            f"Pitch range [deg]: {fmt(r.pitch_min_deg)} to {fmt(r.pitch_max_deg)}",
            f"Roll range [deg]: {fmt(r.roll_min_deg)} to {fmt(r.roll_max_deg)}",
            f"Linear command range: {fmt(r.linear_min)} to {fmt(r.linear_max)}",
            f"Angular command range: {fmt(r.angular_min)} to {fmt(r.angular_max)}",
            f"Missing sequence numbers from forward gaps: {int(r.missing_sequence_numbers)}",
            f"Sequence discontinuities: {int(r.sequence_discontinuities)}",
            f"Haptic EVENT messages: {int(r.haptic_events)}",
            f"RTT samples: {int(r.rtt_samples)}",
            f"RTT mean [ms]: {fmt(r.rtt_mean_ms)}",
            "", "RECORD TYPES"
        ]
        for k, v in counts.items():
            lines.append(f"  {k}: {v}")
        return "\n".join(lines)

    def fig_orientation(self):
        fig, ax = base_figure("Complete Controller: Orientation", "Time [s]", "Angle [deg]")
        ax.plot(self.ctrl.t, self.ctrl.pitch_deg, label="Pitch", linewidth=1.0)
        ax.plot(self.ctrl.t, self.ctrl.roll_deg, label="Roll", linewidth=1.0)
        ax.axhline(0, linestyle="--", linewidth=0.8)
        ax.legend()
        fig.tight_layout()
        return fig

    def fig_commands(self):
        fig, ax = base_figure("Complete Controller: Normalized Commands", "Time [s]", "Normalized command")
        ax.plot(self.ctrl.t, self.ctrl.linear, label="Linear", linewidth=1.0)
        ax.plot(self.ctrl.t, self.ctrl.angular, label="Angular", linewidth=1.0)
        ax.set_ylim(-1.1, 1.1)
        ax.axhline(0, linestyle="--", linewidth=0.8)
        ax.legend()
        fig.tight_layout()
        return fig

    def fig_buttons(self):
        g = self.ctrl.copy()
        fig, ax = base_figure("Complete Controller: Button States", "Time [s]", "State")
        ax.step(g.t, g.grab.fillna(0)+2, where="post", label="Grab")
        ax.step(g.t, g.forward.fillna(0)+1, where="post", label="Forward")
        ax.step(g.t, g.backward.fillna(0), where="post", label="Backward")
        ax.set_yticks([0,1,2,3], ["B:0","B:1 / F:0","F:1 / G:0","G:1"])
        ax.legend()
        fig.tight_layout()
        return fig

    def fig_pitch_mapping(self):
        fig, ax = base_figure("Pitch to Linear-Command Mapping", "Pitch [deg]", "Linear command")
        ax.scatter(self.ctrl.pitch_deg, self.ctrl.linear, s=8, alpha=0.55)
        ax.set_ylim(-1.1, 1.1)
        fig.tight_layout()
        return fig

    def fig_roll_mapping(self):
        fig, ax = base_figure("Roll to Angular-Command Mapping", "Roll [deg]", "Angular command")
        ax.scatter(self.ctrl.roll_deg, self.ctrl.angular, s=8, alpha=0.55)
        ax.set_ylim(-1.1, 1.1)
        fig.tight_layout()
        return fig

    def fig_haptic(self):
        if self.haptic.empty:
            raise ValueError("No EVENT,H0/H1/H2 messages found.")
        mapping = {"H0":0, "H1":1, "H2":2}
        t0 = self.ctrl.elapsed_s.iloc[0]
        fig, ax = base_figure("Complete Controller: Haptic Events", "Time [s]", "Event")
        ax.scatter(self.haptic.elapsed_s-t0, self.haptic.event.map(mapping), s=38)
        ax.set_yticks([0,1,2], ["H0","H1","H2"])
        fig.tight_layout()
        return fig

    def figure_map(self):
        m = {
            "Orientation": ("01_orientation.png", self.fig_orientation),
            "Normalized Commands": ("02_normalized_commands.png", self.fig_commands),
            "Button States": ("03_button_states.png", self.fig_buttons),
            "Pitch to Linear Mapping": ("04_pitch_linear_mapping.png", self.fig_pitch_mapping),
            "Roll to Angular Mapping": ("05_roll_angular_mapping.png", self.fig_roll_mapping),
        }
        if not self.haptic.empty:
            m["Haptic Events"] = ("06_haptic_events.png", self.fig_haptic)
        return m


ANALYZERS = {
    "IMU": IMUAnalyzer,
    "Haptic": HapticAnalyzer,
    "Buttons": ButtonsAnalyzer,
    "Bluetooth": BluetoothAnalyzer,
    "Complete Controller": ControllerAnalyzer,
}


# ============================================================
# GUI
# ============================================================

class AnalysisGUI:
    def __init__(self, root):
        self.root = root
        self.root.title(f"{APP_TITLE} - {VERSION}")
        self.root.geometry("1380x880")
        self.root.minsize(1120, 720)

        self.current_file = None
        self.raw_df = None
        self.analyzer = None
        self.figure = None
        self.canvas = None
        self.toolbar = None

        self.test_var = tk.StringVar(value="IMU")
        self.file_var = tk.StringVar(value="No CSV selected")
        self.path_var = tk.StringVar(value="")
        self.compat_var = tk.StringVar(value="Select a CSV file.")
        self.figure_var = tk.StringVar(value="")
        self.status_var = tk.StringVar(value="Ready.")

        self.build()

    def build(self):
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(1, weight=1)

        header = ttk.Frame(self.root, padding=10)
        header.grid(row=0, column=0, sticky="ew")
        ttk.Label(header, text="Teleoperation Experimental Data Analysis",
                  font=("Segoe UI", 18, "bold")).pack(side="left")
        ttk.Label(header, text=VERSION).pack(side="right")

        main = ttk.Frame(self.root, padding=10)
        main.grid(row=1, column=0, sticky="nsew")
        main.columnconfigure(1, weight=1)
        main.rowconfigure(0, weight=1)

        left = ttk.LabelFrame(main, text="Dataset and Analysis", padding=12)
        left.grid(row=0, column=0, sticky="nsw", padx=(0,10))

        ttk.Label(left, text="Test type:", font=("Segoe UI",10,"bold")).pack(anchor="w")
        for test in TESTS:
            ttk.Radiobutton(left, text=test, value=test, variable=self.test_var,
                            command=self.on_test_change).pack(anchor="w", pady=2)

        ttk.Separator(left).pack(fill="x", pady=10)
        ttk.Label(left, text="Selected CSV:", font=("Segoe UI",10,"bold")).pack(anchor="w")
        ttk.Entry(left, textvariable=self.file_var, width=42, state="readonly").pack(fill="x", pady=4)
        ttk.Button(left, text="Select CSV File...", command=self.select_csv).pack(fill="x", pady=3)
        ttk.Label(left, textvariable=self.path_var, wraplength=320, justify="left").pack(anchor="w", pady=4)

        self.compat_label = ttk.Label(left, textvariable=self.compat_var, wraplength=320, justify="left")
        self.compat_label.pack(anchor="w", pady=(8,4))

        ttk.Button(left, text="Analyze Dataset", command=self.analyze).pack(fill="x", pady=(10,3))

        ttk.Separator(left).pack(fill="x", pady=10)
        ttk.Label(left, text="Figure:", font=("Segoe UI",10,"bold")).pack(anchor="w")
        self.figure_combo = ttk.Combobox(left, textvariable=self.figure_var, width=39, state="readonly")
        self.figure_combo.pack(fill="x", pady=4)
        self.figure_combo.bind("<<ComboboxSelected>>", lambda e: self.show_figure())
        ttk.Button(left, text="Save Current Figure...", command=self.save_current).pack(fill="x", pady=3)
        ttk.Button(left, text="Export Complete Analysis...", command=self.export_all).pack(fill="x", pady=3)

        right = ttk.Frame(main)
        right.grid(row=0, column=1, sticky="nsew")
        right.columnconfigure(0, weight=1)
        right.rowconfigure(1, weight=3)
        right.rowconfigure(3, weight=2)

        info = ttk.LabelFrame(right, text="Dataset Information", padding=8)
        info.grid(row=0, column=0, sticky="ew", pady=(0,8))
        self.info_label = ttk.Label(info, text="No dataset loaded.", justify="left")
        self.info_label.pack(anchor="w")

        self.preview = ttk.LabelFrame(right, text="Figure Preview", padding=5)
        self.preview.grid(row=1, column=0, sticky="nsew")
        self.preview.columnconfigure(0, weight=1)
        self.preview.rowconfigure(0, weight=1)

        ttk.Label(right, text="Analysis Results", font=("Segoe UI",10,"bold")).grid(
            row=2, column=0, sticky="w", pady=(8,3))

        tf = ttk.Frame(right)
        tf.grid(row=3, column=0, sticky="nsew")
        tf.columnconfigure(0, weight=1); tf.rowconfigure(0, weight=1)
        self.text = tk.Text(tf, wrap="none", font=("Consolas",9))
        self.text.grid(row=0, column=0, sticky="nsew")
        ys = ttk.Scrollbar(tf, orient="vertical", command=self.text.yview)
        xs = ttk.Scrollbar(tf, orient="horizontal", command=self.text.xview)
        ys.grid(row=0,column=1,sticky="ns"); xs.grid(row=1,column=0,sticky="ew")
        self.text.configure(yscrollcommand=ys.set, xscrollcommand=xs.set)

        ttk.Label(self.root, textvariable=self.status_var, relief="sunken",
                  anchor="w", padding=5).grid(row=2,column=0,sticky="ew")

    def on_test_change(self):
        self.analyzer = None
        self.clear_figure()
        self.figure_combo["values"] = []
        self.figure_var.set("")
        self.text.delete("1.0", tk.END)
        if self.raw_df is not None:
            self.check_compatibility()

    def select_csv(self):
        name = filedialog.askopenfilename(
            title="Select Experimental CSV",
            filetypes=[("CSV files","*.csv"),("All files","*.*")]
        )
        if not name:
            return
        try:
            self.current_file = Path(name)
            self.raw_df = pd.read_csv(self.current_file)
            self.file_var.set(self.current_file.name)
            self.path_var.set(str(self.current_file))
            cols = ", ".join(self.raw_df.columns)
            self.info_label.configure(
                text=f"Rows: {len(self.raw_df)}    Columns: {len(self.raw_df.columns)}\nDetected columns: {cols}"
            )
            self.check_compatibility()
        except Exception as e:
            messagebox.showerror("CSV Error", str(e))

    def check_compatibility(self):
        if self.raw_df is None:
            return False
        test = self.test_var.get()
        missing = REQUIRED[test] - set(self.raw_df.columns)
        if missing:
            self.compat_var.set("✗ CSV incompatible with selected analyzer.\nMissing: " + ", ".join(sorted(missing)))
            self.status_var.set("Incompatible CSV.")
            return False
        self.compat_var.set(f"✓ CSV compatible with {test} analyzer.")
        self.status_var.set("CSV ready for analysis.")
        return True

    def analyze(self):
        if self.current_file is None or self.raw_df is None:
            messagebox.showwarning("No CSV", "Select a CSV file first.")
            return
        if not self.check_compatibility():
            messagebox.showerror("Incompatible CSV", self.compat_var.get())
            return
        try:
            self.status_var.set("Analyzing...")
            self.root.update_idletasks()
            cls = ANALYZERS[self.test_var.get()]
            self.analyzer = cls(self.raw_df, self.current_file)
            self.text.delete("1.0", tk.END)
            self.text.insert(tk.END, self.analyzer.text_report())
            figs = self.analyzer.figures()
            self.figure_combo["values"] = figs
            if figs:
                self.figure_combo.current(0)
                self.figure_var.set(figs[0])
                self.show_figure()
            self.status_var.set("Analysis completed.")
        except Exception as e:
            traceback.print_exc()
            messagebox.showerror("Analysis Error", str(e))
            self.status_var.set("Analysis failed.")

    def clear_figure(self):
        for child in self.preview.winfo_children():
            child.destroy()
        self.canvas = None
        self.toolbar = None
        self.figure = None

    def show_figure(self):
        if self.analyzer is None or not self.figure_var.get():
            return
        try:
            self.clear_figure()
            self.figure = self.analyzer.create_figure(self.figure_var.get())
            cf = ttk.Frame(self.preview)
            cf.pack(fill="both", expand=True)
            self.canvas = FigureCanvasTkAgg(self.figure, master=cf)
            self.canvas.draw()
            self.canvas.get_tk_widget().pack(fill="both", expand=True)
            tb = ttk.Frame(self.preview)
            tb.pack(fill="x")
            self.toolbar = NavigationToolbar2Tk(self.canvas, tb, pack_toolbar=False)
            self.toolbar.update()
            self.toolbar.pack(side="left")
        except Exception as e:
            messagebox.showerror("Figure Error", str(e))

    def save_current(self):
        if self.figure is None:
            messagebox.showwarning("No Figure", "Analyze a dataset and select a figure first.")
            return
        name = filedialog.asksaveasfilename(
            title="Save Figure", defaultextension=".png",
            filetypes=[("PNG image","*.png")]
        )
        if not name:
            return
        save_figure(self.figure, name)
        self.status_var.set("Figure saved as 300-DPI PNG.")

    def export_all(self):
        if self.analyzer is None:
            messagebox.showwarning("No Analysis", "Analyze a dataset first.")
            return
        folder = filedialog.askdirectory(title="Select Parent Folder for Analysis Export")
        if not folder:
            return
        try:
            self.status_var.set("Exporting...")
            self.root.update_idletasks()
            out, files = self.analyzer.export_all(folder)
            messagebox.showinfo(
                "Export Complete",
                f"Created:\n{out}\n\n" + "\n".join(p.name for p in files)
            )
            self.status_var.set(f"Exported to {out}")
        except Exception as e:
            traceback.print_exc()
            messagebox.showerror("Export Error", str(e))


def main():
    root = tk.Tk()
    AnalysisGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
