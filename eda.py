"""
Exploratory Data Analysis module — 7 story-driven views.

Field-wide analytical views that complement the per-well time-series
charts in charts.py. Every view operates on the full production_data
table, not a single well.

Views:
    1. Feature Importance   — which sensors the Random Forest relies on
    2. Failure Precursors   — sensor trends in the 5 days BEFORE failure
    3. Decline Curve        — Water Cut vs Oil Rate (petroleum classic)
    4. Health Radar         — 5-axis health fingerprint per well
    5. Health Score         — composite 0-100 score, colored by tier
    6. 7-Day Forecast       — linear trend projection per well
    7. Production Loss      — barrels lost to failures, per well
"""

import os
import datetime

import numpy as np
import tkinter as tk

from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

from config import COLORS, REPORTS_DIR, RISK_THRESHOLD, MODEL_PATH
from data_loader import load_all_data
from logger import log_gui_event, log_system_error

# ---------------------------------------------------------------------
# Public interface
# ---------------------------------------------------------------------

EDA_VIEWS = [
    'Feature Importance',
    'Failure Precursors',
    'Decline Curve',
    'Health Radar',
    'Health Score',
    '7-Day Forecast',
    'Production Loss',
]

SENSOR_COLUMNS = ['Oil_Rate', 'Pressure', 'Water_Cut', 'Temperature']

# 5 distinct colors for the 5 wells; reuses the shared palette.
WELL_COLOR_KEYS = ['accent', 'pressure', 'water', 'temperature', 'normal']


# ---------------------------------------------------------------------
# Lazy ML model loader (only used by the Feature Importance view)
# ---------------------------------------------------------------------
_model = None
_model_artifact = None

def _get_model():
    """
    Load the trained model.

    Supports both:
    1. Legacy format: estimator saved directly
    2. Current format: dictionary containing the estimator and metadata
    """
    global _model, _model_artifact

    if _model is not None:
        return _model

    import joblib

    _model_artifact = joblib.load(MODEL_PATH)

    # New model artifact format
    if isinstance(_model_artifact, dict):
        if "model" not in _model_artifact:
            raise ValueError(
                "Model artifact is a dictionary but does not contain "
                "a 'model' entry."
            )

        _model = _model_artifact["model"]

    # Legacy model format
    else:
        _model = _model_artifact

    return _model

# Add Feature name handling

def _get_model_feature_names():
    """
    Return the exact feature names used by the trained model.
    """
    global _model_artifact

    if isinstance(_model_artifact, dict):
        feature_cols = _model_artifact.get("feature_cols")

        if feature_cols:
            return list(feature_cols)

    model = _get_model()

    if hasattr(model, "feature_names_in_"):
        return list(model.feature_names_in_)

    # Legacy fallback
    return SENSOR_COLUMNS

# ---------------------------------------------------------------------
# Panel class
# ---------------------------------------------------------------------

class EDAPanel(tk.Frame):
    """A Tkinter frame holding a single reusable Matplotlib figure."""

    def __init__(self, parent):
        super().__init__(parent, bg=COLORS['bg'])

        self.fig = Figure(figsize=(9, 4.5), dpi=100, facecolor=COLORS['bg'])
        self.canvas = FigureCanvasTkAgg(self.fig, master=self)
        self.canvas.get_tk_widget().pack(fill='both', expand=True)

        self.current_view = EDA_VIEWS[0]
        self.show_placeholder()

    # ---------------------------------------------------------------- styling

    def _style_axes(self, ax, title, xlabel='', ylabel=''):
        ax.set_facecolor(COLORS['bg'])
        ax.set_title(title, color=COLORS['text'], fontsize=11, pad=12)
        if xlabel:
            ax.set_xlabel(xlabel, color=COLORS['muted'], fontsize=9)
        if ylabel:
            ax.set_ylabel(ylabel, color=COLORS['muted'], fontsize=9)
        ax.tick_params(colors=COLORS['muted'], labelsize=8)
        ax.grid(True, color=COLORS['border'], linestyle='--',
                linewidth=0.5, alpha=0.5)
        ax.set_axisbelow(True)
        for spine in ax.spines.values():
            spine.set_color(COLORS['border'])

    def _empty_message(self, ax, message):
        ax.text(0.5, 0.5, message, transform=ax.transAxes,
                ha='center', va='center', color=COLORS['muted'], fontsize=11)
        ax.set_facecolor(COLORS['bg'])
        ax.set_xticks([]); ax.set_yticks([])
        for spine in ax.spines.values():
            spine.set_visible(False)
        self.canvas.draw()

    def _finalize(self):
        self.fig.tight_layout()
        self.canvas.draw()

    def _well_color(self, index):
        return COLORS[WELL_COLOR_KEYS[index % len(WELL_COLOR_KEYS)]]

    # ---------------------------------------------------------------- view 1

    def plot_feature_importance(self):
        """Bar chart of Random Forest feature importances."""
        self.fig.clear()

        try:
            model = _get_model()

            # Make sure the loaded object is actually a model
            if not hasattr(model, "feature_importances_"):
                raise ValueError(
                    "Loaded model does not expose feature_importances_. "
                    "Check the saved model artifact."
                )

            importances = np.asarray(
                model.feature_importances_,
                dtype=float
            )

            # sklearn stores the exact feature names used during training.
            if hasattr(model, "feature_names_in_"):
                names = list(model.feature_names_in_)
            else:
                names = [
                    "Oil_Rate",
                    "Pressure",
                    "Water_Cut",
                    "Temperature"
                ]

            if len(names) != len(importances):
                raise ValueError(
                    f"Feature mismatch: {len(names)} names "
                    f"but {len(importances)} importance values."
                )

        except Exception as e:
            self._empty_message(
                self.fig.add_subplot(111),
                f"Feature importance unavailable:\n{e}"
            )
            return

        order = np.argsort(importances)

        sorted_names = [
            names[i]
            for i in order
        ]

        sorted_values = [
            importances[i] * 100
            for i in order
        ]

        ax = self.fig.add_subplot(111)

        max_value = max(sorted_values) if sorted_values else 1

        colors = [
            COLORS["accent"] if v == max_value
            else COLORS["pressure"]
            for v in sorted_values
        ]

        bars = ax.barh(
            sorted_names,
            sorted_values,
            color=colors,
            alpha=0.85,
            edgecolor=COLORS["bg"],
            linewidth=0.8
        )

        for bar, v in zip(bars, sorted_values):
            ax.text(
                v + max_value * 0.02,
                bar.get_y() + bar.get_height() / 2,
                f"{v:.1f}%",
                va="center",
                color=COLORS["text"],
                fontsize=9,
                fontweight="bold"
            )

        self._style_axes(
            ax,
            "Random Forest Feature Importance",
            xlabel="Importance (%)"
        )

        ax.set_xlim(
            0,
            max_value * 1.2 if max_value > 0 else 100
        )

        self._finalize()

        log_gui_event(
            "eda_view",
            "Feature importance displayed"
        )

    # ---------------------------------------------------------------- view 2

    def plot_failure_precursors(self):
        """Average sensor trend in the 5 days leading up to a failure."""
        df = load_all_data()
        self.fig.clear()
        if df.empty:
            self._empty_message(self.fig.add_subplot(111), 'No data loaded')
            return

        df = df.sort_values(['Well_ID', 'Date']).reset_index(drop=True)
        window = 5  # days before failure

        # Collect per-failure-event windows, aligned so the last row is day 0.
        sensor_windows = {col: [] for col in SENSOR_COLUMNS}
        event_count = 0

        for well, group in df.groupby('Well_ID'):
            group = group.reset_index(drop=True)
            failure_idx = group.index[group['Pump_Status'] == 1].tolist()
            for idx in failure_idx:
                if idx < window:
                    continue
                win = group.iloc[idx - window: idx + 1]
                for col in SENSOR_COLUMNS:
                    sensor_windows[col].append(win[col].values)
                event_count += 1

        if event_count == 0:
            self._empty_message(self.fig.add_subplot(111),
                                'No failure events to analyse')
            return

        # Average each sensor's window across all events, then normalize 0-100.
        offsets = list(range(-window, 1))
        ax = self.fig.add_subplot(111)

        for i, col in enumerate(SENSOR_COLUMNS):
            stack = np.vstack(sensor_windows[col])   # (events, window+1)
            mean_series = stack.mean(axis=0)
            lo, hi = mean_series.min(), mean_series.max()
            if hi - lo < 1e-9:
                normalized = np.full_like(mean_series, 50.0)
            else:
                normalized = (mean_series - lo) / (hi - lo) * 100

            ax.plot(offsets, normalized,
                    color=self._well_color(i), linewidth=2.2,
                    marker='o', markersize=5, label=col)

        ax.axvline(0, color=COLORS['critical'], linestyle='--',
                   linewidth=1, alpha=0.7)
        ax.text(0.05, 5, 'failure', color=COLORS['critical'],
                fontsize=8, rotation=90, va='bottom')

        self._style_axes(
            ax,
            f'Failure Precursors — averaged over {event_count} events',
            xlabel='Days before failure',
            ylabel='Normalized sensor value (0-100)',
        )
        ax.legend(facecolor=COLORS['panel'], edgecolor=COLORS['border'],
                  labelcolor=COLORS['text'], fontsize=8,
                  loc='upper left', ncol=2)
        ax.set_xticks(offsets)

        self._finalize()
        log_gui_event('eda_view', f'Failure precursors ({event_count} events)')

    # ---------------------------------------------------------------- view 3

    def plot_decline_curve(self):
        """Water Cut vs Oil Rate — classic petroleum decline signature."""
        df = load_all_data()
        self.fig.clear()
        if df.empty:
            self._empty_message(self.fig.add_subplot(111), 'No data loaded')
            return

        ax = self.fig.add_subplot(111)
        normal = df[df['Pump_Status'] == 0]
        failure = df[df['Pump_Status'] == 1]

        ax.scatter(normal['Water_Cut'], normal['Oil_Rate'],
                   color=COLORS['normal'], s=40, alpha=0.7,
                   edgecolors=COLORS['bg'], linewidths=0.5, label='Normal')
        ax.scatter(failure['Water_Cut'], failure['Oil_Rate'],
                   color=COLORS['critical'], s=70, alpha=0.9, marker='X',
                   edgecolors=COLORS['bg'], linewidths=0.8, label='Failure')

        self._style_axes(ax, 'Decline Curve — Water Cut vs Oil Rate',
                         xlabel='Water Cut (%)', ylabel='Oil Rate (bbl/day)')
        ax.legend(facecolor=COLORS['panel'], edgecolor=COLORS['border'],
                  labelcolor=COLORS['text'], fontsize=9, loc='upper right')

        self._finalize()
        log_gui_event('eda_view', 'Decline curve displayed')

    # ---------------------------------------------------------------- view 4

    def plot_health_radar(self):
        """Radar chart: one 5-axis fingerprint per well, all overlaid."""
        df = load_all_data()
        self.fig.clear()
        if df.empty:
            self._empty_message(self.fig.add_subplot(111), 'No data loaded')
            return

        # Compose a composite per well: normalized sensor scores 0-100.
        wells = sorted(df['Well_ID'].unique().tolist())
        categories = ['Oil Rate', 'Pressure', 'Low Water', 'Stable Temp', 'Uptime']

        # Field-wide min/max for min-max normalization.
        def _norm(values, invert=False):
            lo, hi = values.min(), values.max()
            if hi - lo < 1e-9:
                return np.full_like(values, 50.0, dtype=float)
            out = (values - lo) / (hi - lo) * 100
            return 100 - out if invert else out

        well_scores = {}
        for well in wells:
            g = df[df['Well_ID'] == well]
            oil = _norm(np.array([g['Oil_Rate'].mean()]))[0]
            pres = _norm(np.array([g['Pressure'].mean()]))[0]
            water = _norm(np.array([g['Water_Cut'].mean()]), invert=True)[0]
            # Temperature: distance from field median is "instability"
            field_median_temp = df['Temperature'].median()
            temp_penalty = abs(g['Temperature'].mean() - field_median_temp)
            temp = max(0, 100 - temp_penalty * 2)
            uptime = (len(g) - g['Pump_Status'].sum()) / len(g) * 100
            well_scores[well] = [oil, pres, water, temp, uptime]

        angles = np.linspace(0, 2 * np.pi, len(categories),
                             endpoint=False).tolist()
        angles += angles[:1]  # close the loop

        ax = self.fig.add_subplot(111, polar=True)
        ax.set_facecolor(COLORS['bg'])

        for i, well in enumerate(wells):
            values = well_scores[well] + well_scores[well][:1]
            color = self._well_color(i)
            ax.plot(angles, values, color=color, linewidth=1.8,
                    marker='o', markersize=4, label=well)
            ax.fill(angles, values, color=color, alpha=0.10)

        ax.set_xticks(angles[:-1])
        ax.set_xticklabels(categories, color=COLORS['muted'], fontsize=9)
        ax.set_yticks([25, 50, 75, 100])
        ax.set_yticklabels(['25', '50', '75', '100'],
                           color=COLORS['muted'], fontsize=7)
        ax.set_ylim(0, 100)
        ax.tick_params(colors=COLORS['muted'])
        ax.grid(color=COLORS['border'], linestyle='--',
                linewidth=0.5, alpha=0.5)
        ax.spines['polar'].set_color(COLORS['border'])
        ax.set_title('Well Health Fingerprint — 5-axis radar',
                     color=COLORS['text'], fontsize=11, pad=20)
        ax.legend(facecolor=COLORS['panel'], edgecolor=COLORS['border'],
                  labelcolor=COLORS['text'], fontsize=8,
                  loc='upper right', bbox_to_anchor=(1.25, 1.10))

        self._finalize()
        log_gui_event('eda_view', 'Health radar displayed')

    # ---------------------------------------------------------------- view 5

    def plot_health_score(self):
        """Composite 0-100 health score per well, colored by tier."""
        df = load_all_data()
        self.fig.clear()
        if df.empty:
            self._empty_message(self.fig.add_subplot(111), 'No data loaded')
            return

        wells = sorted(df['Well_ID'].unique().tolist())
        scores = []

        for well in wells:
            g = df[df['Well_ID'] == well]
            oil = np.clip(g['Oil_Rate'].mean() / 500 * 100, 0, 100)
            pres = np.clip((g['Pressure'].mean() - 1000) / 1800 * 100, 0, 100)
            water = np.clip(100 - g['Water_Cut'].mean(), 0, 100)
            temp = np.clip(100 - abs(g['Temperature'].mean() - 90) * 2, 0, 100)
            uptime = (len(g) - g['Pump_Status'].sum()) / len(g) * 100

            composite = (0.25 * oil + 0.25 * pres + 0.15 * water
                         + 0.10 * temp + 0.25 * uptime)
            scores.append(composite)

        ax = self.fig.add_subplot(111)
        colors = []
        for s in scores:
            if s >= 75:
                colors.append(COLORS['normal'])
            elif s >= 50:
                colors.append(COLORS['warning'])
            else:
                colors.append(COLORS['critical'])

        bars = ax.bar(wells, scores, color=colors,
                      alpha=0.85, edgecolor=COLORS['bg'], linewidth=0.8)

        for bar, s in zip(bars, scores):
            ax.text(bar.get_x() + bar.get_width() / 2, s + 2,
                    f'{s:.0f}', ha='center', color=COLORS['text'],
                    fontsize=10, fontweight='bold')

        ax.axhline(75, color=COLORS['normal'], linestyle='--',
                   linewidth=1, alpha=0.6, label='Healthy (≥75)')
        ax.axhline(50, color=COLORS['warning'], linestyle='--',
                   linewidth=1, alpha=0.6, label='Warning (≥50)')

        self._style_axes(ax, 'Composite Well Health Score',
                         xlabel='Well', ylabel='Health score (0-100)')
        ax.set_ylim(0, 110)
        ax.legend(facecolor=COLORS['panel'], edgecolor=COLORS['border'],
                  labelcolor=COLORS['text'], fontsize=8, loc='lower right')

        self._finalize()
        log_gui_event('eda_view', 'Health score displayed')

    # ---------------------------------------------------------------- view 6

    def plot_forecast(self):
        """Linear projection of Oil Rate 7 days forward, per well."""
        df = load_all_data()
        self.fig.clear()
        if df.empty:
            self._empty_message(self.fig.add_subplot(111), 'No data loaded')
            return

        ax = self.fig.add_subplot(111)
        wells = sorted(df['Well_ID'].unique().tolist())
        history_days = 10
        forecast_days = 7

        for i, well in enumerate(wells):
            g = df[df['Well_ID'] == well].sort_values('Date')
            y = g['Oil_Rate'].values[-history_days:]
            x = np.arange(len(y))

            if len(y) < 2:
                continue

            slope, intercept = np.polyfit(x, y, 1)

            future_x = np.arange(len(y), len(y) + forecast_days)
            future_y = slope * future_x + intercept

            color = self._well_color(i)
            ax.plot(x, y, color=color, linewidth=1.8,
                    marker='o', markersize=4, label=well)
            ax.plot(future_x, future_y, color=color, linewidth=1.4,
                    linestyle='--', alpha=0.75)

        ax.axvline(history_days - 1, color=COLORS['border'],
                   linestyle=':', linewidth=1)
        ax.text(history_days - 0.7, ax.get_ylim()[1] * 0.95,
                'today', color=COLORS['muted'], fontsize=8)

        self._style_axes(ax, 'Oil Rate Forecast — 7 days forward',
                         xlabel='Days (0 = 10 days ago)', ylabel='Oil Rate (bbl/day)')
        ax.legend(facecolor=COLORS['panel'], edgecolor=COLORS['border'],
                  labelcolor=COLORS['text'], fontsize=8,
                  loc='upper right', ncol=2)

        self._finalize()
        log_gui_event('eda_view', 'Forecast displayed')

    # ---------------------------------------------------------------- view 7

    def plot_production_loss(self):
        """Barrels lost to pump failures, per well."""
        df = load_all_data()
        self.fig.clear()
        if df.empty:
            self._empty_message(self.fig.add_subplot(111), 'No data loaded')
            return

        wells = sorted(df['Well_ID'].unique().tolist())
        losses = []

        for well in wells:
            g = df[df['Well_ID'] == well]
            normal_days = g[g['Pump_Status'] == 0]
            failure_days = g[g['Pump_Status'] == 1]
            if failure_days.empty or normal_days.empty:
                losses.append(0.0)
                continue
            expected = normal_days['Oil_Rate'].mean() * len(failure_days)
            actual = failure_days['Oil_Rate'].sum()
            losses.append(max(0.0, expected - actual))

        ax = self.fig.add_subplot(111)
        bars = ax.bar(wells, losses, color=COLORS['critical'],
                      alpha=0.80, edgecolor=COLORS['bg'], linewidth=0.8)

        for bar, loss in zip(bars, losses):
            if loss > 0:
                ax.text(bar.get_x() + bar.get_width() / 2, loss + max(losses) * 0.02,
                        f'{loss:,.0f}', ha='center', color=COLORS['text'],
                        fontsize=9, fontweight='bold')

        total = sum(losses)
        self._style_axes(ax, f'Production Loss to Failures — field total: {total:,.0f} bbl',
                         xlabel='Well', ylabel='Barrels lost (bbl)')
        ax.set_ylim(0, max(losses) * 1.2 if losses and max(losses) > 0 else 10)

        self._finalize()
        log_gui_event('eda_view', f'Production loss displayed (total {total:.0f} bbl)')

    # ---------------------------------------------------------------- dispatch

    def plot(self, view_name):
        """Dispatch by name; errors surface to the GUI as status messages."""
        self.current_view = view_name
        dispatch = {
            'Feature Importance': self.plot_feature_importance,
            'Failure Precursors': self.plot_failure_precursors,
            'Decline Curve':      self.plot_decline_curve,
            'Health Radar':       self.plot_health_radar,
            'Health Score':       self.plot_health_score,
            '7-Day Forecast':     self.plot_forecast,
            'Production Loss':    self.plot_production_loss,
        }
        try:
            dispatch[view_name]()
        except Exception as error:
            log_system_error('eda_error',
                             f'EDA view "{view_name}" failed: {error}', error)
            raise

    def show_placeholder(self):
        self.fig.clear()
        ax = self.fig.add_subplot(111)
        self._empty_message(ax, 'Choose an EDA view from the toolbar above')

    def save_png(self, path=None):
        """Save the current view to reports/ with a timestamped filename."""
        if path is None:
            timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
            safe = self.current_view.replace(' ', '_').lower()
            os.makedirs(REPORTS_DIR, exist_ok=True)
            path = os.path.join(REPORTS_DIR, f'eda_{safe}_{timestamp}.png')
        self.fig.savefig(path, facecolor=COLORS['bg'], dpi=120)
        log_gui_event('eda_export', f'Saved EDA view to {path}')
        return path