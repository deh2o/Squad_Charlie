"""
charts.py
Member 3 (GUI Developer) | Tuesday deliverable.

Matplotlib charts embedded inside a Tkinter frame. The class owns one
Figure and one canvas for its whole lifetime; drawing a different chart
clears the axes and redraws rather than creating new widgets, which is
what keeps switching charts instant and leak-free.

Every plotting method follows the same four steps:
    1. pull the well's rows from the database (data_loader)
    2. fig.clear()         - wipe the previous chart
    3. ax.plot(...)        - draw the new series and restyle the axes
    4. canvas.draw()       - push the figure to the screen
Skipping step 2 stacks charts on top of each other; skipping step 4
leaves the window showing the old chart. fig.clear() rather than
ax.clear() because the overview chart swaps between a 1x1 and a 2x2
grid of axes.
"""

import tkinter as tk

from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

from config import COLORS
from data_loader import load_well_data

# Chart names exposed to the GUI. app.py builds its toolbar buttons from
# this list, so adding a chart here is enough to add a button for it.
CHART_TYPES = ['Overview', 'Oil Rate', 'Pressure', 'Water Cut', 'Temperature']


class ChartPanel(tk.Frame):
    """A Tkinter frame holding a single reusable Matplotlib figure."""

    def __init__(self, parent):
        super().__init__(parent, bg=COLORS['bg'])

        # Figure and canvas are created ONCE. Recreating them per redraw is
        # the usual cause of Tkinter memory growth and flickering charts.
        self.fig = Figure(figsize=(9, 4.5), dpi=100, facecolor=COLORS['bg'])
        self.canvas = FigureCanvasTkAgg(self.fig, master=self)
        self.canvas.get_tk_widget().pack(fill='both', expand=True)

        self.show_placeholder()

    # ---------------------------------------------------------------- utils

    def _style_axes(self, ax, title, ylabel):
        """Apply the dark theme to one axes object.

        The Figure facecolor alone is not enough: without setting the axes
        facecolor and tick colours too, the plot area stays white and the
        numbers become unreadable on the dark window.
        """
        ax.set_facecolor(COLORS['bg'])
        ax.set_title(title, color=COLORS['text'], fontsize=11, pad=12)
        ax.set_ylabel(ylabel, color=COLORS['muted'], fontsize=9)
        ax.tick_params(colors=COLORS['muted'], labelsize=8)
        ax.grid(True, color=COLORS['border'], linestyle='--', linewidth=0.5, alpha=0.6)
        ax.set_axisbelow(True)  # grid behind the data, not over it
        for spine in ax.spines.values():
            spine.set_color(COLORS['border'])

    def _style_dates(self, ax, dates):
        """Thin out and rotate the x labels.

        30 daily labels overlap into an unreadable smear, so only every
        fifth date is shown.
        """
        step = max(1, len(dates) // 6)
        ax.set_xticks(range(0, len(dates), step))
        ax.set_xticklabels(dates[::step], rotation=45, ha='right', fontsize=7)

    def _mark_failures(self, ax, df, series):
        """Overlay a red dot on every day the pump was recorded as failed."""
        failures = df[df['Pump_Status'] == 1]
        if failures.empty:
            return
        ax.scatter(
            failures.index, failures[series],
            color=COLORS['critical'], s=45, zorder=5,
            label='Pump failure', edgecolors=COLORS['bg'], linewidths=0.8,
        )
        ax.legend(
            facecolor=COLORS['panel'], edgecolor=COLORS['border'],
            labelcolor=COLORS['text'], fontsize=8, loc='upper right',
        )

    def _draw_series(self, well_id, column, title, ylabel, color):
        """Shared body of the single-metric charts."""
        df = load_well_data(well_id)

        self.fig.clear()
        ax = self.fig.add_subplot(111)

        if df.empty:
            self._empty_message(ax, f'No data for {well_id}')
            return

        ax.plot(
            df.index, df[column],
            color=color, linewidth=1.8, marker='o', markersize=3.5,
        )
        ax.fill_between(df.index, df[column], color=color, alpha=0.12)
        self._mark_failures(ax, df, column)
        self._style_axes(ax, f'{well_id} — {title}', ylabel)
        self._style_dates(ax, df['Date'].tolist())

        self.fig.tight_layout()
        self.canvas.draw()

    def _empty_message(self, ax, message):
        """Render a centred message instead of an empty grid."""
        ax.text(
            0.5, 0.5, message, transform=ax.transAxes,
            ha='center', va='center', color=COLORS['muted'], fontsize=11,
        )
        ax.set_facecolor(COLORS['bg'])
        ax.set_xticks([])
        ax.set_yticks([])
        for spine in ax.spines.values():
            spine.set_visible(False)
        self.canvas.draw()

    # --------------------------------------------------------------- charts

    def show_placeholder(self):
        """First-run state, before any well has been selected."""
        self.fig.clear()
        ax = self.fig.add_subplot(111)
        self._empty_message(ax, 'Select a well and run diagnostics')

    def plot_oil_rate(self, well_id):
        self._draw_series(well_id, 'Oil_Rate', 'Oil Production',
                          'bbl/day', COLORS['accent'])

    def plot_pressure(self, well_id):
        self._draw_series(well_id, 'Pressure', 'Wellhead Pressure',
                          'psi', COLORS['pressure'])

    def plot_water_cut(self, well_id):
        self._draw_series(well_id, 'Water_Cut', 'Water Cut',
                          '%', COLORS['water'])

    def plot_temperature(self, well_id):
        self._draw_series(well_id, 'Temperature', 'Temperature',
                          '°C', COLORS['temperature'])

    def plot_overview(self, well_id):
        """All four sensors as a 2x2 grid, for a single-glance health check."""
        df = load_well_data(well_id)

        self.fig.clear()
        if df.empty:
            self._empty_message(self.fig.add_subplot(111), f'No data for {well_id}')
            return

        panels = [
            ('Oil_Rate', 'Oil Rate', 'bbl/day', COLORS['accent']),
            ('Pressure', 'Pressure', 'psi', COLORS['pressure']),
            ('Water_Cut', 'Water Cut', '%', COLORS['water']),
            ('Temperature', 'Temperature', '°C', COLORS['temperature']),
        ]

        for position, (column, title, ylabel, color) in enumerate(panels, start=1):
            ax = self.fig.add_subplot(2, 2, position)
            ax.plot(df.index, df[column], color=color, linewidth=1.4)
            self._style_axes(ax, title, ylabel)
            ax.set_xticks([])  # dates are shared across panels; labels would crowd

        self.fig.suptitle(f'{well_id} — 30-Day Overview',
                          color=COLORS['text'], fontsize=12)
        self.fig.tight_layout()
        self.canvas.draw()

    def plot(self, chart_type, well_id):
        """Dispatch by the chart names in CHART_TYPES (used by the toolbar)."""
        dispatch = {
            'Oil Rate': self.plot_oil_rate,
            'Pressure': self.plot_pressure,
            'Water Cut': self.plot_water_cut,
            'Temperature': self.plot_temperature,
            'Overview': self.plot_overview,
        }
        dispatch[chart_type](well_id)

    def save_png(self, path):
        """Write the chart currently on screen to disk, for email attachments."""
        self.fig.savefig(path, facecolor=COLORS['bg'], dpi=120)
        return path
