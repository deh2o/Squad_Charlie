"""
eda.py
Exploratory Data Analysis module.

Field-wide analytical views to complement the per-well time-series charts
in charts.py. All views operate on the full production_data table.

Follows the same Figure/Canvas lifetime pattern as ChartPanel: one figure
and one canvas created at construction; each plot clears the figure and
redraws.
"""

import os
from datetime import datetime

import tkinter as tk
import pandas as pd

from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

from config import COLORS, REPORTS_DIR, RISK_THRESHOLD
from data_loader import load_all_data
from logger import log_gui_event, log_system_error

# View names exposed to the GUI. app.py builds its EDA toolbar from this list.
EDA_VIEWS = [
    'Correlation',
    'Pressure vs Oil',
    'Distributions',
    'Failure Rates',
    'Well Comparison',
]

SENSOR_COLUMNS = ['Oil_Rate', 'Pressure', 'Water_Cut', 'Temperature']


class EDAPanel(tk.Frame):
    """A Tkinter frame holding a single reusable Matplotlib figure for EDA."""

    def __init__(self, parent):
        super().__init__(parent, bg=COLORS['bg'])

        self.fig = Figure(figsize=(9, 4.5), dpi=100, facecolor=COLORS['bg'])
        self.canvas = FigureCanvasTkAgg(self.fig, master=self)
        self.canvas.get_tk_widget().pack(fill='both', expand=True)

        self.current_view = EDA_VIEWS[0]
        self.show_placeholder()

    # ----- styling helpers -----

    def _style_axes(self, ax, title, xlabel='', ylabel=''):
        ax.set_facecolor(COLORS['bg'])
        ax.set_title(title, color=COLORS['text'], fontsize=11, pad=12)
        if xlabel:
            ax.set_xlabel(xlabel, color=COLORS['muted'], fontsize=9)
        if ylabel:
            ax.set_ylabel(ylabel, color=COLORS['muted'], fontsize=9)
        ax.tick_params(colors=COLORS['muted'], labelsize=8)
        ax.grid(True, color=COLORS['border'], linestyle='--', linewidth=0.5, alpha=0.5)
        ax.set_axisbelow(True)
        for spine in ax.spines.values():
            spine.set_color(COLORS['border'])

    def _empty_message(self, ax, message):
        ax.text(0.5, 0.5, message, transform=ax.transAxes,
                ha='center', va='center', color=COLORS['muted'], fontsize=11)
        ax.set_facecolor(COLORS['bg'])
        ax.set_xticks([])
        ax.set_yticks([])
        for spine in ax.spines.values():
            spine.set_visible(False)
        self.canvas.draw()

    def _finalize(self):
        self.fig.tight_layout()
        self.canvas.draw()

    # ----- charts -----

    def show_placeholder(self):
        self.fig.clear()
        ax = self.fig.add_subplot(111)
        self._empty_message(ax, 'Run an EDA view to explore the field data')

    def plot_correlation(self):
        """Correlation heatmap across all numeric columns."""
        df = load_all_data()
        self.fig.clear()

        if df.empty:
            self._empty_message(self.fig.add_subplot(111), 'No data loaded')
            return

        # Include Pump_Status as a column so its correlations are visible.
        numeric = df[SENSOR_COLUMNS + ['Pump_Status']].corr()

        ax = self.fig.add_subplot(111)
        im = ax.imshow(numeric.values, cmap='coolwarm', vmin=-1, vmax=1, aspect='auto')

        # Tick labels
        labels = list(numeric.columns)
        ax.set_xticks(range(len(labels)))
        ax.set_yticks(range(len(labels)))
        ax.set_xticklabels(labels, rotation=45, ha='right',
                           color=COLORS['muted'], fontsize=9)
        ax.set_yticklabels(labels, color=COLORS['muted'], fontsize=9)

        # Annotate each cell
        for i in range(len(labels)):
            for j in range(len(labels)):
                val = numeric.values[i, j]
                ax.text(j, i, f'{val:.2f}', ha='center', va='center',
                        color='white' if abs(val) > 0.5 else '#0D1117',
                        fontsize=9, fontweight='bold')

        ax.set_facecolor(COLORS['bg'])
        ax.set_title('Feature Correlation Matrix', color=COLORS['text'],
                     fontsize=11, pad=12)
        ax.tick_params(colors=COLORS['muted'], labelsize=8)
        for spine in ax.spines.values():
            spine.set_color(COLORS['border'])

        cbar = self.fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
        cbar.ax.tick_params(colors=COLORS['muted'], labelsize=8)

        self._finalize()
        log_gui_event('eda_view', 'Correlation heatmap displayed')

    def plot_scatter(self):
        """Pressure vs Oil Rate, colored by failure status."""
        df = load_all_data()
        self.fig.clear()

        if df.empty:
            self._empty_message(self.fig.add_subplot(111), 'No data loaded')
            return

        ax = self.fig.add_subplot(111)

        normal = df[df['Pump_Status'] == 0]
        failure = df[df['Pump_Status'] == 1]

        ax.scatter(normal['Pressure'], normal['Oil_Rate'],
                   color=COLORS['normal'], s=40, alpha=0.7,
                   edgecolors=COLORS['bg'], linewidths=0.5, label='Normal')
        ax.scatter(failure['Pressure'], failure['Oil_Rate'],
                   color=COLORS['critical'], s=60, alpha=0.9, marker='X',
                   edgecolors=COLORS['bg'], linewidths=0.8, label='Failure')

        self._style_axes(ax, 'Pressure vs Oil Rate — colored by outcome',
                         xlabel='Pressure (psi)', ylabel='Oil Rate (bbl/day)')
        ax.legend(facecolor=COLORS['panel'], edgecolor=COLORS['border'],
                  labelcolor=COLORS['text'], fontsize=9, loc='upper left')

        self._finalize()
        log_gui_event('eda_view', 'Pressure/Oil scatter displayed')

    def plot_histograms(self):
        """2x2 grid of sensor distributions."""
        df = load_all_data()
        self.fig.clear()

        if df.empty:
            self._empty_message(self.fig.add_subplot(111), 'No data loaded')
            return

        panels = [
            ('Oil_Rate', 'Oil Rate (bbl/day)', COLORS['accent']),
            ('Pressure', 'Pressure (psi)', COLORS['pressure']),
            ('Water_Cut', 'Water Cut (%)', COLORS['water']),
            ('Temperature', 'Temperature (C)', COLORS['temperature']),
        ]

        for position, (column, label, color) in enumerate(panels, start=1):
            ax = self.fig.add_subplot(2, 2, position)
            ax.hist(df[column], bins=15, color=color, alpha=0.75,
                    edgecolor=COLORS['bg'], linewidth=0.5)
            self._style_axes(ax, label)

        self.fig.suptitle('Sensor Distributions — Field Wide',
                          color=COLORS['text'], fontsize=12)

        self._finalize()
        log_gui_event('eda_view', 'Sensor histograms displayed')

    def plot_failure_rates(self):
        """Failure rate per well as a bar chart."""
        df = load_all_data()
        self.fig.clear()

        if df.empty:
            self._empty_message(self.fig.add_subplot(111), 'No data loaded')
            return

        # Compute failure rate per well
        rates = df.groupby('Well_ID')['Pump_Status'].mean().sort_values()
        wells = rates.index.tolist()
        values = [r * 100 for r in rates.values]

        ax = self.fig.add_subplot(111)
        bars = ax.bar(range(len(wells)), values, color=COLORS['accent'],
                      alpha=0.85, edgecolor=COLORS['bg'], linewidth=0.8)

        # Color-code bars above the alert threshold
        for bar, rate in zip(bars, rates.values):
            if rate >= RISK_THRESHOLD:
                bar.set_color(COLORS['critical'])
            elif rate >= 0.5:
                bar.set_color(COLORS['warning'])

        # Value labels above each bar
        for i, v in enumerate(values):
            ax.text(i, v + 1, f'{v:.1f}%', ha='center',
                    color=COLORS['text'], fontsize=9, fontweight='bold')

        ax.set_xticks(range(len(wells)))
        ax.set_xticklabels(wells, rotation=0, color=COLORS['muted'], fontsize=9)
        self._style_axes(ax, 'Historical Failure Rate per Well',
                         xlabel='Well', ylabel='Failure rate (%)')
        ax.set_ylim(0, max(values) * 1.25 if values else 10)

        # Threshold line
        ax.axhline(RISK_THRESHOLD * 100, color=COLORS['critical'],
                   linestyle='--', linewidth=1, alpha=0.7,
                   label=f'Alert threshold ({RISK_THRESHOLD:.0%})')
        ax.legend(facecolor=COLORS['panel'], edgecolor=COLORS['border'],
                  labelcolor=COLORS['text'], fontsize=8, loc='upper left')

        self._finalize()
        log_gui_event('eda_view', 'Failure rate bar chart displayed')

    def plot_boxplots(self):
        """Box plots of each sensor, split by well — 2x2 grid."""
        df = load_all_data()
        self.fig.clear()

        if df.empty:
            self._empty_message(self.fig.add_subplot(111), 'No data loaded')
            return

        panels = [
            ('Oil_Rate', 'Oil Rate (bbl/day)', COLORS['accent']),
            ('Pressure', 'Pressure (psi)', COLORS['pressure']),
            ('Water_Cut', 'Water Cut (%)', COLORS['water']),
            ('Temperature', 'Temperature (C)', COLORS['temperature']),
        ]

        wells = sorted(df['Well_ID'].unique().tolist())

        for position, (column, label, color) in enumerate(panels, start=1):
            ax = self.fig.add_subplot(2, 2, position)
            data_per_well = [df[df['Well_ID'] == w][column].values for w in wells]

            bp = ax.boxplot(
                data_per_well,
                patch_artist=True,
                labels=wells,
                medianprops={'color': COLORS['text'], 'linewidth': 1.5},
                whiskerprops={'color': COLORS['muted']},
                capprops={'color': COLORS['muted']},
                flierprops={'marker': 'o', 'markerfacecolor': COLORS['critical'],
                            'markersize': 3, 'markeredgecolor': 'none'},
            )
            for patch in bp['boxes']:
                patch.set_facecolor(color)
                patch.set_alpha(0.6)
                patch.set_edgecolor(COLORS['border'])

            self._style_axes(ax, label)
            ax.tick_params(axis='x', labelsize=7)

        self.fig.suptitle('Sensor Spread per Well',
                          color=COLORS['text'], fontsize=12)

        self._finalize()
        log_gui_event('eda_view', 'Box plots displayed')

    def plot(self, view_name):
        """Dispatch by the view names in EDA_VIEWS (used by the toolbar)."""
        self.current_view = view_name
        dispatch = {
            'Correlation': self.plot_correlation,
            'Pressure vs Oil': self.plot_scatter,
            'Distributions': self.plot_histograms,
            'Failure Rates': self.plot_failure_rates,
            'Well Comparison': self.plot_boxplots,
        }
        try:
            dispatch[view_name]()
        except Exception as error:
            log_system_error('eda_error', f'EDA view {view_name} failed: {error}', error)
            raise

    def save_png(self, path=None):
        """Save the current EDA view to disk."""
        if path is None:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            safe_view = self.current_view.replace(' ', '_').lower()
            os.makedirs(REPORTS_DIR, exist_ok=True)
            path = os.path.join(REPORTS_DIR, f'eda_{safe_view}_{timestamp}.png')
        self.fig.savefig(path, facecolor=COLORS['bg'], dpi=120)
        log_gui_event('eda_export', f'Saved EDA view to {path}')
        return path