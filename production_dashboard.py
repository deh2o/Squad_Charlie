"""Production analytics workspace for the Squad Charlie control center.

This module provides a dashboard inspired by modern oil & gas BI layouts:
filters, production KPIs, operational charts, downtime distribution,
performance-to-target, and a well performance matrix.

The dashboard is deliberately data-driven: it reads the project's SQLite
production table and never hard-codes the well metrics shown on screen.
"""
from __future__ import annotations

import math
import tkinter as tk
from tkinter import ttk

import customtkinter as ctk
import pandas as pd
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
from matplotlib.patches import Wedge

from data_loader import load_all_data


NAVY = "#10213A"
NAVY_2 = "#172D4D"
PAGE_BG = "#0D1117"
CARD = "#FFFFFF"
TEXT = "#172033"
MUTED = "#667085"
GRID = "#DCE5EF"
BLUE = "#1683F7"
BLUE_2 = "#38bdf8"
BLUE_3 = "#78B8F2"
GREEN = "#18A957"
AMBER = "#E7A51A"
RED = "#E5484D"


class ProductionDashboard(ctk.CTkFrame):
    """Lightweight production-performance dashboard embedded in the app."""

    def __init__(self, parent, status_callback=None):
        super().__init__(parent, fg_color=PAGE_BG, corner_radius=0)
        self.status_callback = status_callback
        self.df = pd.DataFrame()
        self.filtered_df = pd.DataFrame()
        self.selected_wells: set[str] = set()
        self._well_vars: dict[str, tk.BooleanVar] = {}
        self._status_vars: dict[str, tk.BooleanVar] = {}
        self._build_ui()
        self.refresh()

    def _status(self, message, level="muted"):
        if self.status_callback:
            self.status_callback(message, level)

    def _build_ui(self):
        scroll = ctk.CTkScrollableFrame(self, fg_color=PAGE_BG, corner_radius=0)
        scroll.pack(fill="both", expand=True, padx=10, pady=8)
        self.scroll = scroll

        # Header / filter bar
        header = ctk.CTkFrame(scroll, fg_color=PAGE_BG)
        header.pack(fill="x", pady=(2, 8))
        title_box = ctk.CTkFrame(header, fg_color="transparent")
        title_box.pack(side="left", fill="x", expand=True)
        ctk.CTkLabel(title_box, text="OIL WELL PRODUCTION PERFORMANCE ANALYSIS",
                     text_color=BLUE_2, font=ctk.CTkFont(size=23, weight="bold")).pack(anchor="w")
        ctk.CTkLabel(title_box, text="Monitor production rates, well performance, downtime and operational efficiency",
                     text_color=MUTED, font=ctk.CTkFont(size=11)).pack(anchor="w", pady=(2, 0))

        controls = ctk.CTkFrame(header, fg_color=CARD, corner_radius=10,
                                border_width=1, border_color=GRID)
        controls.pack(side="right", padx=(12, 0))
        self.start_var = tk.StringVar()
        self.end_var = tk.StringVar()
        for label, var, width in [("FROM", self.start_var, 92), ("TO", self.end_var, 92)]:
            ctk.CTkLabel(controls, text=label, text_color=MUTED,
                         font=ctk.CTkFont(size=8, weight="bold")).pack(side="left", padx=(9, 2))
            ctk.CTkEntry(controls, textvariable=var, width=width, height=30,
                         border_color=GRID, fg_color="#F8FAFC", text_color=TEXT).pack(side="left", padx=(0, 5), pady=7)
        ctk.CTkButton(controls, text="Apply", width=65, height=30, fg_color=BLUE,
                      hover_color=BLUE_2, command=self.apply_filters).pack(side="left", padx=5)
        ctk.CTkButton(controls, text="Reset", width=55, height=30, fg_color="#EEF3F8",
                      hover_color="#DCE5EF", text_color=NAVY, command=self.reset_filters).pack(side="left", padx=(0, 7))

        self.filter_card = ctk.CTkFrame(scroll, fg_color=CARD, corner_radius=10,
                                        border_width=1, border_color=GRID)
        self.filter_card.pack(fill="x", pady=(0, 10))
        self.filter_body = ctk.CTkFrame(self.filter_card, fg_color="transparent")
        self.filter_body.pack(fill="x", padx=12, pady=9)

        self.kpi_frame = ctk.CTkFrame(scroll, fg_color="transparent")
        self.kpi_frame.pack(fill="x", pady=(0, 10))
        self.kpi_labels = {}
        self._create_kpi("TOTAL PRODUCTION", "--", "BBL", 0)
        self._create_kpi("TOTAL WELLS", "--", "active wells", 1)
        self._create_kpi("AVG OIL RATE", "--", "BBL/DAY", 2)
        self._create_kpi("AVG WATER CUT", "--", "%", 3)

        # Main chart row
        chart_row = ctk.CTkFrame(scroll, fg_color="transparent")
        chart_row.pack(fill="x", pady=(0, 10))
        chart_row.grid_columnconfigure(0, weight=1)
        chart_row.grid_columnconfigure(1, weight=2)
        chart_row.grid_columnconfigure(2, weight=1)
        self.daily_chart = self._chart_card(chart_row, "DAILY OIL PRODUCTION RATE BY WELL", 0, grid_column=0)
        self.trend_chart = self._chart_card(chart_row, "WEEKLY PRODUCTION TREND", 0, grid_column=1)
        side = ctk.CTkFrame(chart_row, fg_color="transparent")
        side.grid(row=0, column=2, sticky="nsew", padx=(7, 0))
        self.downtime_chart = self._chart_card(side, "DOWNTIME METRICS", 0, height=190, grid_column=0)
        self.target_chart = self._chart_card(side, "PERFORMANCE VS TARGET", 1, height=190, grid_column=0)

        bottom = ctk.CTkFrame(scroll, fg_color="transparent")
        bottom.pack(fill="both", expand=True)
        bottom.grid_columnconfigure(0, weight=1)
        bottom.grid_columnconfigure(1, weight=2)
        self.total_chart = self._chart_card(bottom, "TOTAL OIL PRODUCTION BY WELL", 0, height=270, grid_column=0)
        self.table_card = ctk.CTkFrame(bottom, fg_color=CARD, corner_radius=10,
                                       border_width=1, border_color=GRID)
        self.table_card.grid(row=0, column=1, sticky="nsew", padx=(7, 0))
        self._build_table(self.table_card)

        insight = ctk.CTkFrame(scroll, fg_color=CARD, corner_radius=10,
                               border_width=1, border_color=GRID)
        insight.pack(fill="x", pady=(10, 0))
        ctk.CTkLabel(insight, text="QUICK INSIGHTS", text_color=NAVY,
                     font=ctk.CTkFont(size=12, weight="bold")).pack(side="left", padx=14, pady=10)
        self.insight_label = ctk.CTkLabel(insight, text="Loading…", text_color=MUTED,
                                          font=ctk.CTkFont(size=10), anchor="w", justify="left")
        self.insight_label.pack(side="left", fill="x", expand=True, padx=(4, 14), pady=10)

    def _create_kpi(self, title, value, suffix, column):
        card = ctk.CTkFrame(self.kpi_frame, fg_color=CARD, corner_radius=10,
                            border_width=1, border_color=GRID)
        card.grid(row=0, column=column, sticky="ew", padx=(0 if column == 0 else 6, 0))
        self.kpi_frame.grid_columnconfigure(column, weight=1)
        ctk.CTkLabel(card, text=title, text_color=MUTED,
                     font=ctk.CTkFont(size=9, weight="bold")).pack(anchor="w", padx=14, pady=(11, 2))
        value_label = ctk.CTkLabel(card, text=value, text_color=TEXT,
                                   font=ctk.CTkFont(size=24, weight="bold"))
        value_label.pack(anchor="w", padx=14)
        ctk.CTkLabel(card, text=suffix, text_color=MUTED,
                     font=ctk.CTkFont(size=9)).pack(anchor="w", padx=14, pady=(0, 10))
        self.kpi_labels[title] = value_label

    def _chart_card(self, parent, title, row, height=255, grid_column=0):
        card = ctk.CTkFrame(parent, fg_color=CARD, corner_radius=10,
                            border_width=1, border_color=GRID, height=height)
        card.grid(row=row, column=grid_column, sticky="nsew",
                  padx=(0 if grid_column == 0 else 7, 0),
                  pady=(0, 7) if title != "PERFORMANCE VS TARGET" else 0)
        if hasattr(parent, "grid_rowconfigure"):
            parent.grid_rowconfigure(row, weight=1)
        ctk.CTkLabel(card, text=title, text_color=NAVY,
                     font=ctk.CTkFont(size=10, weight="bold")).pack(anchor="w", padx=12, pady=(10, 2))
        frame = ctk.CTkFrame(card, fg_color=CARD, corner_radius=0, height=height - 30)
        frame.pack(fill="both", expand=True, padx=5, pady=(0, 5))
        frame.pack_propagate(False)
        return frame

    def _build_table(self, parent):
        top = ctk.CTkFrame(parent, fg_color="transparent")
        top.pack(fill="x", padx=12, pady=(10, 4))
        ctk.CTkLabel(top, text="WELL PERFORMANCE MATRIX", text_color=NAVY,
                     font=ctk.CTkFont(size=10, weight="bold")).pack(side="left")
        self.table_search = ctk.CTkEntry(top, width=130, height=28, placeholder_text="Search well…",
                                         fg_color="#F8FAFC", border_color=GRID, text_color=TEXT)
        self.table_search.pack(side="right")
        self.table_search.bind("<KeyRelease>", lambda _e: self._render_table())

        frame = tk.Frame(parent, bg=CARD)
        frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        cols = ("Well_ID", "Total Oil", "Avg Oil", "Min Rate", "Max Rate", "Avg Water", "Avg Pressure", "Avg Temp", "Status")
        self.tree = ttk.Treeview(frame, columns=cols, show="headings", height=7)
        widths = [72, 90, 78, 70, 70, 78, 90, 72, 75]
        for col, width in zip(cols, widths):
            self.tree.heading(col, text=col)
            self.tree.column(col, width=width, anchor="center", stretch=True)
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("Production.Treeview", background="#FFFFFF", foreground=TEXT,
                        fieldbackground="#FFFFFF", rowheight=27, font=("Segoe UI", 9), borderwidth=0)
        style.configure("Production.Treeview.Heading", background=NAVY, foreground="#FFFFFF",
                        font=("Segoe UI", 8, "bold"), relief="flat")
        style.map("Production.Treeview", background=[("selected", "#D9ECFF")], foreground=[("selected", TEXT)])
        self.tree.configure(style="Production.Treeview")
        self.tree.pack(fill="both", expand=True)
        self.tree.bind("<<TreeviewSelect>>", self._table_selected)

    def refresh(self, df=None):
        """Reload production data and rebuild all visualizations."""
        try:
            self.df = (load_all_data() if df is None else df).copy()
            if self.df.empty:
                self.filtered_df = self.df
                self._render_empty()
                return
            self.df["Date"] = pd.to_datetime(self.df["Date"], errors="coerce")
            self.df = self.df.dropna(subset=["Date"])
            wells = sorted(self.df["Well_ID"].dropna().unique().tolist())
            self.selected_wells = set(wells)
            self._rebuild_filters(wells)
            self.start_var.set(self.df["Date"].min().strftime("%d/%m/%Y"))
            self.end_var.set(self.df["Date"].max().strftime("%d/%m/%Y"))
            self.apply_filters()
        except Exception as exc:
            self._status(f"Production dashboard failed: {exc}", "critical")

    def _rebuild_filters(self, wells):
        for child in self.filter_body.winfo_children():
            child.destroy()
        self._well_vars.clear()
        self._status_vars.clear()

        ctk.CTkLabel(self.filter_body, text="SELECT WELLS", text_color=NAVY,
                     font=ctk.CTkFont(size=9, weight="bold")).pack(side="left", padx=(0, 9))
        self.all_wells_var = tk.BooleanVar(value=True)
        ctk.CTkCheckBox(self.filter_body, text="Select all", variable=self.all_wells_var,
                        command=self._toggle_all_wells, text_color=TEXT, fg_color=BLUE,
                        hover_color=BLUE_2, width=80).pack(side="left", padx=(0, 7))
        for well in wells:
            var = tk.BooleanVar(value=True)
            self._well_vars[well] = var
            ctk.CTkCheckBox(self.filter_body, text=well, variable=var,
                            command=self._well_filter_changed, text_color=TEXT,
                            fg_color=BLUE, hover_color=BLUE_2, width=70).pack(side="left", padx=2)

        sep = ctk.CTkFrame(self.filter_body, width=1, height=26, fg_color=GRID)
        sep.pack(side="left", padx=10)
        ctk.CTkLabel(self.filter_body, text="STATUS", text_color=NAVY,
                     font=ctk.CTkFont(size=9, weight="bold")).pack(side="left", padx=(0, 5))
        for status, color in [("Failure", RED), ("Normal", BLUE)]:
            var = tk.BooleanVar(value=True)
            self._status_vars[status] = var
            ctk.CTkCheckBox(self.filter_body, text=status, variable=var,
                            command=self.apply_filters, text_color=TEXT,
                            fg_color=color, hover_color=color, width=72).pack(side="left", padx=2)

    def _toggle_all_wells(self):
        value = self.all_wells_var.get()
        for var in self._well_vars.values():
            var.set(value)
        self.apply_filters()

    def _well_filter_changed(self):
        selected = {well for well, var in self._well_vars.items() if var.get()}
        self.all_wells_var.set(len(selected) == len(self._well_vars))
        self.apply_filters()

    def reset_filters(self):
        if self.df.empty:
            return
        for var in self._well_vars.values():
            var.set(True)
        for var in self._status_vars.values():
            var.set(True)
        self.all_wells_var.set(True)
        self.start_var.set(self.df["Date"].min().strftime("%d/%m/%Y"))
        self.end_var.set(self.df["Date"].max().strftime("%d/%m/%Y"))
        self.apply_filters()

    def apply_filters(self):
        if self.df.empty:
            return
        try:
            start = pd.to_datetime(self.start_var.get().strip(), dayfirst=True)
            end = pd.to_datetime(self.end_var.get().strip(), dayfirst=True)
            if start > end:
                raise ValueError("From date must be before To date")
            wells = {w for w, var in self._well_vars.items() if var.get()}
            statuses = {1 if s == "Failure" else 0 for s, var in self._status_vars.items() if var.get()}
            mask = self.df["Date"].between(start, end) & self.df["Well_ID"].isin(wells) & self.df["Pump_Status"].isin(statuses)
            self.filtered_df = self.df.loc[mask].copy()
            self._render_all()
            self._status(f"Production dashboard updated • {len(self.filtered_df)} observations", "normal")
        except Exception as exc:
            self._status(f"Invalid production filters: {exc}", "warning")

    def _render_all(self):
        df = self.filtered_df
        if df.empty:
            self._render_empty()
            return
        self._render_kpis(df)
        self._draw_daily_rates(df)
        self._draw_weekly_trend(df)
        self._draw_downtime(df)
        self._draw_target(df)
        self._draw_total_by_well(df)
        self._render_table()
        self._render_insights(df)

    def _render_empty(self):
        for widget in [self.daily_chart, self.trend_chart, self.downtime_chart, self.target_chart, self.total_chart]:
            self._clear_widget(widget)
            ctk.CTkLabel(widget, text="No data matches the current filters", text_color=MUTED).pack(expand=True)
        for label in self.kpi_labels.values():
            label.configure(text="--")
        self._render_table()
        self.insight_label.configure(text="No production observations match the current filters.")

    def _render_kpis(self, df):
        self.kpi_labels["TOTAL PRODUCTION"].configure(text=f"{df['Oil_Rate'].sum():,.0f}")
        self.kpi_labels["TOTAL WELLS"].configure(text=str(df["Well_ID"].nunique()))
        self.kpi_labels["AVG OIL RATE"].configure(text=f"{df['Oil_Rate'].mean():,.2f}")
        self.kpi_labels["AVG WATER CUT"].configure(text=f"{df['Water_Cut'].mean():.2f}%")

    def _new_figure(self, widget, figsize=(5, 2.4)):
        self._clear_widget(widget)
        fig = Figure(figsize=figsize, dpi=90, facecolor=CARD)
        ax = fig.add_subplot(111)
        ax.set_facecolor(CARD)
        canvas = FigureCanvasTkAgg(fig, master=widget)
        canvas.get_tk_widget().pack(fill="both", expand=True)
        return fig, ax, canvas

    def _clear_widget(self, widget):
        for child in widget.winfo_children():
            child.destroy()

    def _style_axis(self, ax):
        ax.tick_params(axis="both", labelsize=7, colors=MUTED)
        ax.grid(axis="y", color=GRID, linewidth=0.6)
        ax.set_axisbelow(True)
        for spine in ax.spines.values():
            spine.set_visible(False)

    def _draw_daily_rates(self, df):
        summary = df.groupby("Well_ID")["Oil_Rate"].mean().sort_values()
        fig, ax, canvas = self._new_figure(self.daily_chart)
        bars = ax.barh(summary.index, summary.values, color=BLUE, height=0.55)
        ax.set_xlabel("BBL/DAY", fontsize=7, color=MUTED)
        self._style_axis(ax)
        ax.tick_params(axis="x", labelsize=7)
        for bar, value in zip(bars, summary.values):
            ax.text(value + max(summary.values) * .015, bar.get_y() + bar.get_height()/2,
                    f"{value:.0f}", va="center", fontsize=7, color=TEXT)
        fig.tight_layout(pad=1.0)
        canvas.draw_idle()

    def _draw_weekly_trend(self, df):
        work = df.copy()
        work["Week"] = work["Date"].dt.to_period("W").apply(lambda x: x.start_time)
        weekly = work.groupby(["Week", "Well_ID"])["Oil_Rate"].sum().unstack(fill_value=0).sort_index()
        fig, ax, canvas = self._new_figure(self.trend_chart, (7.5, 2.6))
        if not weekly.empty:
            ax.stackplot(weekly.index, [weekly[c].values for c in weekly.columns], labels=weekly.columns, alpha=0.88)
            ax.set_xticks(list(weekly.index))
            ax.set_xticklabels([d.strftime("%b %d") for d in weekly.index], rotation=0, fontsize=7)
            ax.legend(fontsize=6, ncol=min(5, len(weekly.columns)), loc="upper left", frameon=False)
        ax.set_ylabel("BBL", fontsize=7, color=MUTED)
        self._style_axis(ax)
        fig.tight_layout(pad=1.0)
        canvas.draw_idle()

    def _draw_downtime(self, df):
        counts = df["Pump_Status"].value_counts().to_dict()
        normal = counts.get(0, 0)
        failure = counts.get(1, 0)
        fig, ax, canvas = self._new_figure(self.downtime_chart, (3.2, 2.0))
        if normal + failure:
            ax.pie([normal, failure], startangle=90, counterclock=False,
                   colors=[BLUE, RED], wedgeprops={"width": 0.28, "edgecolor": CARD},
                   textprops={"fontsize": 7})
            ax.text(0, 0.03, f"{normal + failure}", ha="center", va="center",
                    fontsize=16, weight="bold", color=TEXT)
            ax.text(0, -0.18, "readings", ha="center", va="center", fontsize=6, color=MUTED)
            ax.legend([f"Normal ({normal})", f"Failure ({failure})"], fontsize=6,
                      loc="lower center", bbox_to_anchor=(0.5, -0.15), frameon=False)
        ax.set_aspect("equal")
        fig.tight_layout(pad=0.4)
        canvas.draw_idle()

    def _draw_target(self, df):
        total = float(df["Oil_Rate"].sum())
        target = max(total * 1.10, 1.0)
        pct = min(max(total / target, 0.0), 1.0)
        fig, ax, canvas = self._new_figure(self.target_chart, (3.2, 2.0))
        ax.set_xlim(-1.2, 1.2)
        ax.set_ylim(-0.2, 1.15)
        ax.axis("off")

        # A clean half-donut gauge: 0% at the left, 100% at the right.
        ax.add_patch(Wedge((0, 0), 1.0, 0, 180, width=0.25, facecolor="#D8DEE7", edgecolor=CARD))
        ax.add_patch(Wedge((0, 0), 1.0, 180 - 180 * pct, 180, width=0.25, facecolor=BLUE, edgecolor=CARD))
        ax.text(0, 0.34, f"{total:,.0f}", ha="center", va="center",
                fontsize=17, weight="bold", color=TEXT)
        ax.text(0, 0.10, "BBL", ha="center", va="center", fontsize=7, color=MUTED)
        ax.text(-1.03, -0.03, "0", fontsize=7, color=MUTED)
        ax.text(0.68, -0.03, f"{target:,.0f}", fontsize=7, color=MUTED)
        fig.tight_layout(pad=0.2)
        canvas.draw_idle()

    def _draw_total_by_well(self, df):
        summary = df.groupby("Well_ID")["Oil_Rate"].sum().sort_values(ascending=False)
        fig, ax, canvas = self._new_figure(self.total_chart, (5.5, 2.7))
        bars = ax.bar(summary.index, summary.values, color=BLUE, width=0.62)
        ax.set_ylabel("BBL", fontsize=7, color=MUTED)
        self._style_axis(ax)
        ax.tick_params(axis="x", labelsize=7)
        for bar, value in zip(bars, summary.values):
            ax.text(bar.get_x() + bar.get_width()/2, value + max(summary.values) * .02,
                    f"{value:,.0f}", ha="center", fontsize=7, color=TEXT)
        fig.tight_layout(pad=1.0)
        canvas.draw_idle()

    def _render_table(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
        df = self.filtered_df
        if df.empty:
            return
        search = self.table_search.get().strip().lower()
        rows = df.groupby("Well_ID").agg(
            Total_Oil=("Oil_Rate", "sum"),
            Avg_Oil=("Oil_Rate", "mean"),
            Min_Rate=("Oil_Rate", "min"),
            Max_Rate=("Oil_Rate", "max"),
            Avg_Water=("Water_Cut", "mean"),
            Avg_Pressure=("Pressure", "mean"),
            Avg_Temp=("Temperature", "mean"),
            Failure_Rate=("Pump_Status", "mean"),
        ).reset_index()
        rows = rows.sort_values("Total_Oil", ascending=False)
        if search:
            rows = rows[rows["Well_ID"].str.lower().str.contains(search)]
        for _, r in rows.iterrows():
            status = "Failure history" if r["Failure_Rate"] > 0 else "Normal"
            self.tree.insert("", "end", values=(
                r["Well_ID"], f"{r['Total_Oil']:,.2f}", f"{r['Avg_Oil']:,.2f}",
                f"{r['Min_Rate']:,.2f}", f"{r['Max_Rate']:,.2f}", f"{r['Avg_Water']:.2f}%",
                f"{r['Avg_Pressure']:,.2f}", f"{r['Avg_Temp']:.1f}", status,
            ))

    def _render_insights(self, df):
        by_well = df.groupby("Well_ID")["Oil_Rate"].sum().sort_values(ascending=False)
        top = by_well.index[0]
        total = df["Oil_Rate"].sum()
        water = df["Water_Cut"].mean()
        failure_rate = df["Pump_Status"].mean() * 100
        text = (f"{top} has the highest production ({by_well.iloc[0]:,.0f} BBL)  •  "
                f"Field production {total:,.0f} BBL  •  Avg water cut {water:.2f}%  •  "
                f"Historical failure observations {failure_rate:.1f}%")
        self.insight_label.configure(text=text)

    def _table_selected(self, _event=None):
        selection = self.tree.selection()
        if not selection:
            return
        values = self.tree.item(selection[0], "values")
        if values:
            self._status(f"Selected {values[0]} from production matrix", "normal")
            try:
                # Let the parent application react to a selected well when it
                # exposes the standard selection helper.
                root = self.winfo_toplevel()
                if hasattr(root, "_select_well_by_id"):
                    root._select_well_by_id(values[0])
            except Exception:
                pass
