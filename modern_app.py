"""
modern_app.py
Modern GUI redesign using CustomTkinter with dashboard analytics theme.

This is a modernized version of the Digital Oilfield Monitoring System
featuring:
- CustomTkinter modern widgets with dark/light mode support
- Dashboard analytics layout with KPI cards
- Improved visual hierarchy and spacing
- Modern typography and color scheme
- Enhanced chart integration
- Responsive design elements
"""

import os
import sqlite3
import datetime
import csv
import threading
from concurrent.futures import ThreadPoolExecutor
import customtkinter as ctk
from tkinter import messagebox, ttk
import tkinter as tk

import charts
import emailer
import reports
import eda
import field_analytics
from charts import ChartPanel
from config import COLORS, FONT_FAMILY, RISK_THRESHOLD, TECH_EMAIL, CSV_PATH, RAW_DATA_DIR, DB_PATH
from data_loader import get_well_ids, load_all_data, load_well_data
from predict import get_risk_level, predict_failure_risk
from load_csv import load_csv_into_db
import generate_data
from logger import log_gui_event, log_system_error, get_recent_logs, clear_logs
import auth
from alert_manager import CriticalAlertManager

# Configure CustomTkinter appearance
ctk.set_appearance_mode("dark")  # Modes: "System" (standard), "Dark", "Light"
ctk.set_default_color_theme("dark-blue")  # Themes: "blue" (standard), "green", "dark-blue"


class ModernDashboardApp(ctk.CTk):
    """Modern dashboard application using CustomTkinter."""

    def __init__(self, current_user=None):
        super().__init__()
        self.current_user = current_user or {"username": "system", "role": "operator"}
        self.title('Squad Charlie — Modern Digital Oilfield Monitoring')
        
        # Calculate window size based on screen dimensions
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        
        # Use 95% of screen size for modern spacious layout
        window_width = max(1200, int(screen_width * 0.95))
        window_height = max(800, int(screen_height * 0.95))
        
        self.geometry(f'{window_width}x{window_height}')
        self.minsize(1000, 700)
        
        # State variables
        self.current_well = None
        self.current_score = None
        self.current_chart = charts.CHART_TYPES[0]
        self.current_eda_view = eda.EDA_VIEWS[0]
        self.alerted_wells = set()
        self.critical_alert_window = None
        self._well_filter = ''
        self._field_snapshot = None
        self._alert_manager = CriticalAlertManager()
        self._executor = ThreadPoolExecutor(max_workers=3, thread_name_prefix="squad-worker")
        self._closing = False
        self._alert_blink_on = False
        self._alert_blink_job = None
        self._alert_scan_job = None
        self._build_background_alert_bar = True
        
        log_gui_event('modern_app_start', 'Modern application started')
        
        self._build_layout()
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self._load_wells()
        self.after(1200, self._start_background_alert_scan)

    def _build_layout(self):
        """Build the modern dashboard layout."""
        # Main container with modern spacing
        self.main_container = ctk.CTkFrame(self)
        self.main_container.pack(fill="both", expand=True, padx=20, pady=20)
        
        # Header section
        self._build_header()
        self._build_alert_notification_bar()
        
        # Content area with sidebar and main dashboard
        self.content_frame = ctk.CTkFrame(self.main_container)
        self.content_frame.pack(fill="both", expand=True, pady=(20, 0))
        
        # Build sidebar and main content
        self._build_sidebar()
        self._build_main_dashboard()
        
        # Status bar
        self._build_status_bar()

    def _build_alert_notification_bar(self):
        """Build the persistent, blinking critical-alert notification bar."""
        self.alert_bar = ctk.CTkFrame(
            self.main_container, height=54, corner_radius=10,
            fg_color="#3B0A0A", border_width=1, border_color="#EF4444"
        )
        self.alert_bar.pack_propagate(False)

        left = ctk.CTkFrame(self.alert_bar, fg_color="transparent")
        left.pack(side="left", fill="both", expand=True, padx=14)
        self.alert_icon = ctk.CTkLabel(left, text="⚠", font=ctk.CTkFont(size=21, weight="bold"), text_color="#FCA5A5")
        self.alert_icon.pack(side="left", padx=(0, 10))
        self.alert_message = ctk.CTkLabel(
            left, text="CRITICAL ALERT", anchor="w",
            font=ctk.CTkFont(size=12, weight="bold"), text_color="#FEE2E2"
        )
        self.alert_message.pack(side="left", fill="x", expand=True)
        self.alert_ack_button = ctk.CTkButton(
            self.alert_bar, text="ACKNOWLEDGE", width=120, height=32,
            fg_color="#FEE2E2", hover_color="#FFFFFF", text_color="#991B1B",
            font=ctk.CTkFont(size=10, weight="bold"), command=self._acknowledge_visible_alert
        )
        self.alert_ack_button.pack(side="right", padx=(6, 14))
        self.alert_view_button = ctk.CTkButton(
            self.alert_bar, text="VIEW WELL", width=90, height=32,
            fg_color="#7F1D1D", hover_color="#991B1B", text_color="#FFFFFF",
            font=ctk.CTkFont(size=10, weight="bold"), command=self._view_visible_alert
        )
        self.alert_view_button.pack(side="right", padx=6)
        self._hide_alert_bar()

    def _hide_alert_bar(self):
        if hasattr(self, "alert_bar"):
            self.alert_bar.pack_forget()
        self._alert_blink_on = False

    def _show_alert_bar(self):
        if not self._alert_manager.pending():
            self._hide_alert_bar()
            return
        if not self.alert_bar.winfo_ismapped():
            self.alert_bar.pack(fill="x", pady=(0, 10), before=self.content_frame)
        self._render_visible_alert()
        self._blink_alert_bar()

    def _render_visible_alert(self):
        pending = self._alert_manager.pending()
        if not pending:
            self._hide_alert_bar()
            return
        alert = pending[0]
        count = len(pending)
        suffix = f"  •  +{count - 1} more" if count > 1 else ""
        self._visible_alert_well = alert["well_id"]
        self.alert_message.configure(
            text=f"CRITICAL • {alert['well_id']}  |  7-day failure risk {alert['score'] * 100:.1f}%{suffix}"
        )

    def _blink_alert_bar(self):
        if self._closing or not self._alert_manager.pending():
            return
        self._alert_blink_on = not self._alert_blink_on
        if self._alert_blink_on:
            self.alert_bar.configure(fg_color="#991B1B", border_color="#F87171")
            self.alert_icon.configure(text_color="#FFFFFF")
        else:
            self.alert_bar.configure(fg_color="#3B0A0A", border_color="#EF4444")
            self.alert_icon.configure(text_color="#FCA5A5")
        self._alert_blink_job = self.after(450, self._blink_alert_bar)

    def _acknowledge_visible_alert(self):
        well_id = getattr(self, "_visible_alert_well", None)
        if not well_id:
            return
        self._alert_manager.acknowledge(well_id)
        log_gui_event("critical_alert_acknowledged", f"Critical alert acknowledged for {well_id}")
        self._render_visible_alert()
        if self._alert_manager.pending():
            self._show_alert_bar()
        else:
            self._hide_alert_bar()
        self.set_status(f"Critical alert acknowledged • {well_id}", "warning")

    def _view_visible_alert(self):
        well_id = getattr(self, "_visible_alert_well", None)
        if well_id:
            self.show_page("Wells")
            self._select_well_by_id(well_id)

    def _process_prediction_alerts(self, predictions):
        """Update alert state and surface newly critical wells."""
        if self._closing:
            return
        new_alerts = self._alert_manager.update(predictions)
        if new_alerts:
            for alert in new_alerts:
                self._raise_alert(alert["well_id"], alert["score"], send_email_async=True)
            self._show_alert_bar()
        elif self._alert_manager.pending():
            self._show_alert_bar()

    def _start_background_alert_scan(self):
        """Start periodic non-blocking field scans for critical conditions."""
        if self._closing:
            return
        self._run_background(
            field_analytics.build_field_snapshot,
            self._background_scan_success,
            self._background_scan_error,
        )

    def _schedule_next_alert_scan(self):
        if not self._closing:
            self._alert_scan_job = self.after(30000, self._start_background_alert_scan)

    def _background_scan_success(self, snapshot):
        self._field_snapshot = snapshot
        self._update_field_metrics(snapshot)
        self._update_field_risk_panel(snapshot)
        self._process_prediction_alerts(snapshot["risk"].get("wells", []))
        self._schedule_next_alert_scan()

    def _background_scan_error(self, error):
        self.set_status(f"Background monitoring error: {error}", "warning")
        self._schedule_next_alert_scan()

    def _run_background(self, work, on_success, on_error):
        """Run blocking I/O/ML work off the Tkinter event loop."""
        future = self._executor.submit(work)

        def poll():
            if self._closing:
                return
            if not future.done():
                self.after(50, poll)
                return
            try:
                result = future.result()
            except Exception as exc:
                on_error(exc)
            else:
                on_success(result)

        self.after(50, poll)

    def _build_header(self):
        """Build modern header with branding and status indicators."""
        header = ctk.CTkFrame(self.main_container, height=80)
        header.pack(fill="x", pady=(0, 20))
        header.pack_propagate(False)
        
        # Left side - Branding
        branding_frame = ctk.CTkFrame(header, fg_color="transparent")
        branding_frame.pack(side="left", padx=30, pady=20)
        
        ctk.CTkLabel(
            branding_frame, 
            text="DIGITAL OILFIELD MONITORING",
            font=ctk.CTkFont(size=24, weight="bold")
        ).pack(anchor="w")
        
        ctk.CTkLabel(
            branding_frame,
            text="Predictive Maintenance  •  Squad Charlie",
            font=ctk.CTkFont(size=12),
            text_color="gray"
        ).pack(anchor="w")
        
        # Right side - Status indicators
        status_frame = ctk.CTkFrame(header, fg_color="transparent")
        status_frame.pack(side="right", padx=30, pady=20)
        
        # Database status
        self.db_status_label = ctk.CTkLabel(
            status_frame,
            text="● DB: Ready",
            font=ctk.CTkFont(size=12),
            text_color="#2ECC71"  # Green
        )
        self.db_status_label.pack(side="right", padx=15)
        
        # Email status
        email_status = "Live" if emailer.is_configured() else "Dry Run"
        email_color = "#2ECC71" if emailer.is_configured() else "#F39C12"
        self.email_status_label = ctk.CTkLabel(
            status_frame,
            text=f"● SMTP: {email_status}",
            font=ctk.CTkFont(size=12),
            text_color=email_color
        )
        self.email_status_label.pack(side="right", padx=15)

        # Authenticated user / session controls
        user_frame = ctk.CTkFrame(status_frame, fg_color="#111827", corner_radius=10)
        user_frame.pack(side="right", padx=8)
        ctk.CTkLabel(
            user_frame,
            text=f"● {self.current_user.get('username', 'user')}  •  {self.current_user.get('role', 'operator').upper()}",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color="#E6EDF3",
        ).pack(side="left", padx=(10, 6), pady=7)
        ctk.CTkButton(
            user_frame, text="Logout", width=65, height=28,
            fg_color="transparent", hover_color="#30363D",
            command=self.logout,
        ).pack(side="left", padx=(0, 6), pady=5)

    def _build_sidebar(self):
        """Build a modern application navigation rail."""
        self.sidebar = ctk.CTkFrame(self.content_frame, width=230, corner_radius=16, fg_color="#0B1220")
        self.sidebar.pack(side="left", fill="y", padx=(0, 16))
        self.sidebar.pack_propagate(False)

        ctk.CTkLabel(self.sidebar, text="SQUAD", text_color="#38BDF8",
                     font=ctk.CTkFont(size=13, weight="bold")).pack(anchor="w", padx=22, pady=(24, 0))
        ctk.CTkLabel(self.sidebar, text="CHARLIE", text_color="#F8FAFC",
                     font=ctk.CTkFont(size=22, weight="bold")).pack(anchor="w", padx=22, pady=(0, 4))
        ctk.CTkLabel(self.sidebar, text="Operations platform", text_color="#64748B",
                     font=ctk.CTkFont(size=10)).pack(anchor="w", padx=22, pady=(0, 22))

        self.nav_buttons = {}
        nav_items = [
            ("⌂", "Overview"), ("◉", "Wells"), ("◈", "Predictions"),
            ("⌁", "Analytics"), ("▤", "Reports"), ("▣", "Data"), ("⚙", "System")
        ]
        for icon, label in nav_items:
            btn = ctk.CTkButton(
                self.sidebar, text=f"  {icon}   {label}", anchor="w", height=42,
                corner_radius=10, fg_color="transparent", hover_color="#172033",
                text_color="#94A3B8", font=ctk.CTkFont(size=12, weight="bold"),
                command=lambda name=label: self.show_page(name)
            )
            btn.pack(fill="x", padx=12, pady=3)
            self.nav_buttons[label] = btn

        ctk.CTkFrame(self.sidebar, height=1, fg_color="#1E293B").pack(fill="x", padx=18, pady=20)
        ctk.CTkLabel(self.sidebar, text="SESSION", text_color="#475569",
                     font=ctk.CTkFont(size=9, weight="bold")).pack(anchor="w", padx=22)
        ctk.CTkLabel(self.sidebar, text=self.current_user.get("username", "user"),
                     text_color="#E2E8F0", font=ctk.CTkFont(size=12, weight="bold")).pack(anchor="w", padx=22, pady=(4, 0))
        ctk.CTkLabel(self.sidebar, text=self.current_user.get("role", "operator").upper(),
                     text_color="#38BDF8", font=ctk.CTkFont(size=9, weight="bold")).pack(anchor="w", padx=22, pady=(0, 18))

        ctk.CTkButton(self.sidebar, text="Sign out", height=34, corner_radius=9,
                      fg_color="#111827", hover_color="#1F2937", text_color="#CBD5E1",
                      command=self.logout).pack(fill="x", padx=16, pady=(0, 18))

    def _add_section_header(self, text):
        """Compatibility helper retained for legacy controls."""
        return None

    def _build_main_dashboard(self):
        """Build a multi-view operations control center."""
        self.dashboard_content = ctk.CTkFrame(self.content_frame, corner_radius=16, fg_color="#0F172A")
        self.dashboard_content.pack(side="left", fill="both", expand=True)

        self.pages = {}
        self.page_titles = {}
        for name in ["Overview", "Wells", "Predictions", "Analytics", "Reports", "Data", "System"]:
            page = ctk.CTkFrame(self.dashboard_content, fg_color="#0F172A", corner_radius=0)
            self.pages[name] = page
            self.page_titles[name] = name

        # Overview is the landing workspace.
        overview = self.pages["Overview"]
        self.main_scroll = ctk.CTkScrollableFrame(overview, fg_color="transparent")
        self.main_scroll.pack(fill="both", expand=True, padx=18, pady=18)
        self._build_command_bar()
        self._build_field_intelligence()
        self._build_risk_summary()
        self._build_kpi_cards()
        self._build_well_insight_panel()
        self._build_chart_section()

        # Dedicated analytics workspace.
        analytics = self.pages["Analytics"]
        analytics_scroll = ctk.CTkScrollableFrame(analytics, fg_color="transparent")
        analytics_scroll.pack(fill="both", expand=True, padx=18, pady=18)
        self.main_scroll = analytics_scroll
        self._build_page_heading(analytics_scroll, "Analytics", "Explore production, reliability and field behaviour")
        self._build_eda_section()

        # Dedicated reports workspace.
        reports_page = self.pages["Reports"]
        reports_scroll = ctk.CTkScrollableFrame(reports_page, fg_color="transparent")
        reports_scroll.pack(fill="both", expand=True, padx=18, pady=18)
        self.main_scroll = reports_scroll
        self._build_page_heading(reports_scroll, "Reports", "Generate technical and stakeholder-ready intelligence")
        self._build_reports_section()

        self._build_wells_page()
        self._build_predictions_page()
        self._build_data_page()
        self._build_system_page()

        self.main_scroll = self.pages["Overview"].winfo_children()[0]
        self.show_page("Overview")

    def _build_page_heading(self, parent, title, subtitle):
        card = ctk.CTkFrame(parent, fg_color="#111C31", corner_radius=14)
        card.pack(fill="x", pady=(0, 16))
        ctk.CTkLabel(card, text=title.upper(), text_color="#38BDF8",
                     font=ctk.CTkFont(size=10, weight="bold")).pack(anchor="w", padx=18, pady=(15, 3))
        ctk.CTkLabel(card, text=subtitle, text_color="#CBD5E1",
                     font=ctk.CTkFont(size=18, weight="bold")).pack(anchor="w", padx=18, pady=(0, 15))

    def _build_wells_page(self):
        page = self.pages["Wells"]
        scroll = ctk.CTkScrollableFrame(page, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=18, pady=18)
        self._build_page_heading(scroll, "Well Operations", "Search, inspect and diagnose individual wells")

        toolbar = ctk.CTkFrame(scroll, fg_color="#111C31", corner_radius=12)
        toolbar.pack(fill="x", pady=(0, 12))
        self.well_search = ctk.CTkEntry(toolbar, height=38, placeholder_text="Search wells…")
        self.well_search.pack(side="left", fill="x", expand=True, padx=12, pady=12)
        self.well_search.bind("<KeyRelease>", lambda _e: self._filter_wells())
        ctk.CTkButton(toolbar, text="Run diagnostics", width=140, height=38,
                      fg_color="#2563EB", hover_color="#1D4ED8",
                      command=self.run_diagnostics).pack(side="right", padx=(6, 12), pady=12)

        body = ctk.CTkFrame(scroll, fg_color="transparent")
        body.pack(fill="both", expand=True)
        body.grid_columnconfigure(0, weight=0)
        body.grid_columnconfigure(1, weight=1)
        list_card = ctk.CTkFrame(body, width=250, fg_color="#111C31", corner_radius=12)
        list_card.grid(row=0, column=0, sticky="ns", padx=(0, 12))
        list_card.grid_propagate(False)
        ctk.CTkLabel(list_card, text="WELLS", text_color="#64748B",
                     font=ctk.CTkFont(size=10, weight="bold")).pack(anchor="w", padx=14, pady=(14, 8))
        self.well_listbox = tk.Listbox(list_card, bg="#0B1220", fg="#E2E8F0",
                                       selectbackground="#2563EB", selectforeground="white",
                                       relief="flat", borderwidth=0, font=(FONT_FAMILY, 11),
                                       activestyle="none")
        self.well_listbox.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        self.well_listbox.bind("<<ListboxSelect>>", self.on_well_selected)

        detail = ctk.CTkFrame(body, fg_color="#111C31", corner_radius=12)
        detail.grid(row=0, column=1, sticky="nsew")
        self._build_page_well_detail(detail)

    def _build_page_well_detail(self, parent):
        ctk.CTkLabel(parent, text="SELECTED WELL", text_color="#64748B",
                     font=ctk.CTkFont(size=10, weight="bold")).pack(anchor="w", padx=20, pady=(18, 2))
        self.well_page_name = ctk.CTkLabel(parent, text="No well selected",
                                           font=ctk.CTkFont(size=24, weight="bold"))
        self.well_page_name.pack(anchor="w", padx=20)
        self.well_page_status = ctk.CTkLabel(parent, text="Select a well from the list",
                                             text_color="#94A3B8", font=ctk.CTkFont(size=11))
        self.well_page_status.pack(anchor="w", padx=20, pady=(2, 16))
        grid = ctk.CTkFrame(parent, fg_color="transparent")
        grid.pack(fill="x", padx=20, pady=(0, 20))
        self.well_page_metrics = {}
        for i, label in enumerate(["Oil Rate", "Pressure", "Water Cut", "Temperature"]):
            card = ctk.CTkFrame(grid, fg_color="#0B1220", corner_radius=10)
            card.grid(row=0, column=i, sticky="ew", padx=(0 if i == 0 else 5, 0))
            grid.grid_columnconfigure(i, weight=1)
            ctk.CTkLabel(card, text=label.upper(), text_color="#64748B",
                         font=ctk.CTkFont(size=9, weight="bold")).pack(anchor="w", padx=10, pady=(10, 2))
            value = ctk.CTkLabel(card, text="--", font=ctk.CTkFont(size=15, weight="bold"))
            value.pack(anchor="w", padx=10, pady=(0, 10))
            self.well_page_metrics[label] = value

    def _build_predictions_page(self):
        page = self.pages["Predictions"]
        scroll = ctk.CTkScrollableFrame(page, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=18, pady=18)
        self._build_page_heading(scroll, "Predictive Monitoring", "7-day pump failure risk across the field")
        top = ctk.CTkFrame(scroll, fg_color="transparent")
        top.pack(fill="x", pady=(0, 14))
        self.prediction_summary = {}
        for i, (label, color) in enumerate([("NORMAL", "#22C55E"), ("WARNING", "#F59E0B"), ("CRITICAL", "#EF4444")]):
            card = ctk.CTkFrame(top, fg_color="#111C31", corner_radius=12)
            card.grid(row=0, column=i, sticky="ew", padx=(0 if i == 0 else 6, 0))
            top.grid_columnconfigure(i, weight=1)
            ctk.CTkLabel(card, text=label, text_color=color, font=ctk.CTkFont(size=10, weight="bold")).pack(anchor="w", padx=14, pady=(12, 2))
            value = ctk.CTkLabel(card, text="--", font=ctk.CTkFont(size=24, weight="bold"))
            value.pack(anchor="w", padx=14, pady=(0, 12))
            self.prediction_summary[label] = value
        table_card = ctk.CTkFrame(scroll, fg_color="#111C31", corner_radius=12)
        table_card.pack(fill="both", expand=True)
        ctk.CTkLabel(table_card, text="FIELD RISK REGISTER", font=ctk.CTkFont(size=13, weight="bold")).pack(anchor="w", padx=16, pady=(14, 8))
        cols = ("well", "risk", "level", "status")
        self.prediction_tree = ttk.Treeview(table_card, columns=cols, show="headings", height=14)
        for col, title, width in [("well", "WELL", 130), ("risk", "7-DAY RISK", 130), ("level", "RISK LEVEL", 130), ("status", "OPERATIONAL STATE", 220)]:
            self.prediction_tree.heading(col, text=title)
            self.prediction_tree.column(col, width=width, anchor="w")
        self.prediction_tree.pack(fill="both", expand=True, padx=12, pady=(0, 14))
        self.prediction_tree.bind("<<TreeviewSelect>>", self._prediction_tree_selected)

    def _build_data_page(self):
        page = self.pages["Data"]
        scroll = ctk.CTkScrollableFrame(page, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=18, pady=18)
        self._build_page_heading(scroll, "Data Management", "Ingest, validate and export field data")
        card = ctk.CTkFrame(scroll, fg_color="#111C31", corner_radius=12)
        card.pack(fill="x", pady=(0, 14))
        ctk.CTkLabel(card, text="SOURCE DATA", font=ctk.CTkFont(size=13, weight="bold")).pack(anchor="w", padx=16, pady=(14, 10))
        row = ctk.CTkFrame(card, fg_color="transparent")
        row.pack(fill="x", padx=16, pady=(0, 16))
        self.csv_var = ctk.StringVar()
        self.csv_dropdown = ctk.CTkComboBox(row, variable=self.csv_var, height=38, width=330)
        self.csv_dropdown.pack(side="left", padx=(0, 8))
        for text, command in [("Generate", self.generate_csv_file), ("Load", self.load_selected_csv), ("Validate", self.validate_selected_csv), ("Export DB", self.export_database_to_csv)]:
            ctk.CTkButton(row, text=text, height=38, command=command).pack(side="left", padx=4)
        self._refresh_csv_list()
        dbcard = ctk.CTkFrame(scroll, fg_color="#111C31", corner_radius=12)
        dbcard.pack(fill="x")
        ctk.CTkLabel(dbcard, text="DATABASE ADMINISTRATION", font=ctk.CTkFont(size=13, weight="bold")).pack(anchor="w", padx=16, pady=(14, 10))
        row2 = ctk.CTkFrame(dbcard, fg_color="transparent")
        row2.pack(fill="x", padx=16, pady=(0, 16))
        ctk.CTkButton(row2, text="View statistics", height=38, command=self.show_database_stats).pack(side="left", padx=(0, 8))
        self.clear_db_btn = ctk.CTkButton(row2, text="Clear all data", height=38, fg_color="#7F1D1D", hover_color="#991B1B", command=self.clear_database)
        self.clear_db_btn.pack(side="left")
        if self.current_user.get("role", "operator").lower() == "viewer":
            self.clear_db_btn.configure(state="disabled")

    def _build_system_page(self):
        page = self.pages["System"]
        scroll = ctk.CTkScrollableFrame(page, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=18, pady=18)
        self._build_page_heading(scroll, "System", "Application health, diagnostics and session controls")
        grid = ctk.CTkFrame(scroll, fg_color="transparent")
        grid.pack(fill="x")
        items = [
            ("Database", "View database statistics", self.show_database_stats),
            ("Application logs", "Inspect recent system events", self.show_system_logs),
            ("SMTP", "Test notification connectivity", self.test_smtp_connection),
            ("Session", "Sign out of the control center", self.logout),
        ]
        for i, (title, desc, command) in enumerate(items):
            card = ctk.CTkFrame(grid, fg_color="#111C31", corner_radius=12)
            card.grid(row=i//2, column=i%2, sticky="ew", padx=(0 if i%2 == 0 else 8, 0), pady=(0, 10))
            grid.grid_columnconfigure(i%2, weight=1)
            ctk.CTkLabel(card, text=title.upper(), text_color="#38BDF8", font=ctk.CTkFont(size=10, weight="bold")).pack(anchor="w", padx=16, pady=(14, 3))
            ctk.CTkLabel(card, text=desc, text_color="#94A3B8", font=ctk.CTkFont(size=11)).pack(anchor="w", padx=16)
            ctk.CTkButton(card, text="Open", height=34, command=command).pack(anchor="w", padx=16, pady=12)

    def show_page(self, page_name):
        """Switch between modern application workspaces."""
        if page_name not in self.pages:
            return
        for name, frame in self.pages.items():
            frame.pack_forget()
        self.pages[page_name].pack(fill="both", expand=True)
        for name, button in self.nav_buttons.items():
            if name == page_name:
                button.configure(fg_color="#172A46", text_color="#F8FAFC")
            else:
                button.configure(fg_color="transparent", text_color="#94A3B8")
        self.current_page = page_name
        if page_name == "Predictions":
            self._refresh_prediction_register()
        elif page_name == "Wells":
            self._refresh_well_page()
        elif page_name == "Analytics":
            try:
                self.eda_panel.plot(self.current_eda_view)
            except Exception:
                pass
        elif page_name == "Reports":
            # Field Overview is the default report view.
            self.tabview.set("Field Overview")

            # Always populate the field report when entering Reports.
            self.refresh_field_summary()

            # Populate well-specific reports if a well is selected.
            if self.current_well:
                self._refresh_reports(
                    self.current_well
                )

    def _prediction_tree_selected(self, _event=None):
        selection = self.prediction_tree.selection()
        if selection:
            values = self.prediction_tree.item(selection[0], "values")
            if values:
                well = values[0]
                self._select_well_by_id(well)

    def _select_well_by_id(self, well_id):
        wells = get_well_ids()
        if well_id in wells:
            self.current_well = well_id
            try:
                idx = wells.index(well_id)
                self.well_listbox.selection_clear(0, "end")
                self.well_listbox.selection_set(idx)
                self.well_listbox.see(idx)
            except Exception:
                pass
            self.on_well_selected()

    def _refresh_well_page(self):
        if not self.current_well:
            return
        well_id = self.current_well
        self._run_background(
            lambda: self._load_well_intelligence(well_id),
            lambda result: self._well_page_intelligence_success(well_id, result),
            lambda error: self.well_page_status.configure(text=f"Unable to load well data: {error}"),
        )

    def _well_page_intelligence_success(self, well_id, result):
        if self.current_well != well_id or result.get("empty"):
            return
        latest = result["latest"]
        self.well_page_name.configure(text=well_id)
        self.well_page_metrics["Oil Rate"].configure(text=f"{latest['Oil_Rate']:,.1f} bbl/day")
        self.well_page_metrics["Pressure"].configure(text=f"{latest['Pressure']:,.1f} psi")
        self.well_page_metrics["Water Cut"].configure(text=f"{latest['Water_Cut']:.1f}%")
        self.well_page_metrics["Temperature"].configure(text=f"{latest['Temperature']:.1f} °C")
        details = result["details"]
        if details.get("score") is not None:
            self.well_page_status.configure(text=f"7-day model risk • {details['level']} • {details['score'] * 100:.1f}%")
        else:
            self.well_page_status.configure(text="Model unavailable")

    def _refresh_prediction_register(self):
        """Refresh the risk register off the Tkinter event loop."""
        self.set_status("Refreshing prediction register…")
        self._run_background(
            lambda: field_analytics.get_field_risk(),
            self._prediction_register_success,
            lambda error: self.set_status(f"Prediction register failed: {error}", "warning"),
        )

    def _prediction_register_success(self, risk):
        try:
            for item in self.prediction_tree.get_children():
                self.prediction_tree.delete(item)
            counts = risk.get("risk_counts", {"NORMAL": 0, "WARNING": 0, "CRITICAL": 0})
            for item in risk.get("wells", []):
                level = item["level"]
                state = "Critical attention" if level == "CRITICAL" else "Elevated monitoring" if level == "WARNING" else "Routine monitoring"
                self.prediction_tree.insert("", "end", values=(item["well_id"], f"{item['score'] * 100:.1f}%", level, state))
            for level, value in counts.items():
                if level in self.prediction_summary:
                    self.prediction_summary[level].configure(text=str(value))
            self._process_prediction_alerts(risk.get("wells", []))
            self.set_status("Prediction register updated", "normal")
        except Exception as error:
            self.set_status(f"Prediction register display failed: {error}", "warning")

    def _build_command_bar(self):
        """Modern command bar for search, refresh, theme and quick actions."""
        bar = ctk.CTkFrame(self.main_scroll, corner_radius=14, fg_color="#111827")
        bar.pack(fill="x", pady=(0, 14))

        left = ctk.CTkFrame(bar, fg_color="transparent")
        left.pack(side="left", fill="x", expand=True, padx=14, pady=12)
        ctk.CTkLabel(left, text="OPERATIONS CONTROL ROOM",
                     font=ctk.CTkFont(size=15, weight="bold")).pack(anchor="w")
        ctk.CTkLabel(left, text="Live field overview • predictive maintenance intelligence",
                     text_color="#94A3B8", font=ctk.CTkFont(size=11)).pack(anchor="w", pady=(2, 0))

        self.overview_well_search = ctk.CTkEntry(bar, width=190, height=36,
                                        placeholder_text="Search well…")
        self.overview_well_search.pack(side="left", padx=6, pady=12)
        self.overview_well_search.bind("<KeyRelease>", lambda _e: self._filter_wells())

        ctk.CTkButton(bar, text="↻ Refresh", width=90, height=36,
                      command=self.refresh_dashboard).pack(side="left", padx=6, pady=12)
        ctk.CTkButton(bar, text="Run Scan", width=90, height=36,
                      fg_color="#2563EB", hover_color="#1D4ED8",
                      command=self.run_field_scan).pack(side="left", padx=(0, 14), pady=12)

    def _build_field_intelligence(self):
        """Compact field-health strip with modern KPI cards."""
        frame = ctk.CTkFrame(self.main_scroll, fg_color="transparent")
        frame.pack(fill="x", pady=(0, 14))
        self.field_metric_labels = {}
        metrics = [
            ("Production", "--", "bbl/day"),
            ("Field Uptime", "--", "historical"),
            ("Failure Risk", "--", "7-day model"),
            ("Critical Wells", "--", "requires attention"),
            ("Data Quality", "--", "ingestion"),
        ]
        for i, (title, value, subtitle) in enumerate(metrics):
            card = ctk.CTkFrame(frame, corner_radius=12, fg_color="#151B23")
            card.grid(row=0, column=i, sticky="nsew", padx=(0 if i == 0 else 5, 0))
            frame.grid_columnconfigure(i, weight=1)
            ctk.CTkLabel(card, text=title.upper(), text_color="#64748B",
                         font=ctk.CTkFont(size=10, weight="bold")).pack(anchor="w", padx=13, pady=(11, 3))
            value_label = ctk.CTkLabel(card, text=value,
                                       font=ctk.CTkFont(size=22, weight="bold"))
            value_label.pack(anchor="w", padx=13)
            ctk.CTkLabel(card, text=subtitle, text_color="#64748B",
                         font=ctk.CTkFont(size=9)).pack(anchor="w", padx=13, pady=(1, 11))
            self.field_metric_labels[title] = value_label

    def _filter_wells(self):
        query = self.well_search.get().strip().lower()
        self._well_filter = query
        try:
            wells = get_well_ids()
        except Exception:
            wells = []
        visible = [w for w in wells if query in w.lower()] if query else wells
        current = self.current_well
        self.well_listbox.delete(0, "end")
        for well in visible:
            self.well_listbox.insert("end", well)
        if current in visible:
            idx = visible.index(current)
            self.well_listbox.selection_set(idx)
        elif visible:
            self.well_listbox.selection_set(0)

    def refresh_dashboard(self):
        """Refresh field intelligence without freezing the interface."""
        self.set_status("Refreshing dashboard…")
        self._run_background(
            field_analytics.build_field_snapshot,
            self._dashboard_refresh_success,
            lambda error: self.set_status(f"Refresh failed: {error}", "critical"),
        )

    def _dashboard_refresh_success(self, snapshot):
        self._field_snapshot = snapshot
        self._update_field_metrics(snapshot)
        self._update_field_risk_panel(snapshot)
        self._process_prediction_alerts(snapshot["risk"].get("wells", []))
        self._load_wells()
        self.set_status("Dashboard refreshed", "normal")

    def run_field_scan(self):
        """Run a field-wide predictive scan without blocking the GUI."""
        self.set_status("Running field predictive scan…")
        self._run_background(
            field_analytics.build_field_snapshot,
            self._background_scan_success_manual,
            lambda error: self.set_status(f"Field scan failed: {error}", "critical"),
        )

    def _background_scan_success_manual(self, snapshot):
        self._background_scan_success(snapshot)
        critical = snapshot["risk"]["risk_counts"].get("CRITICAL", 0)
        warning = snapshot["risk"]["risk_counts"].get("WARNING", 0)
        self.set_status(
            f"Field scan complete • {critical} critical • {warning} warning",
            "critical" if critical else "warning" if warning else "normal",
        )

    def refresh_field_intelligence(self):
        try:
            snapshot = field_analytics.build_field_snapshot()
            self._field_snapshot = snapshot
            self._update_field_metrics(snapshot)
            self._update_field_risk_panel(snapshot)
        except Exception as error:
            self.set_status(f"Field intelligence unavailable: {error}", "warning")

    def _update_field_metrics(self, snapshot):
        k = snapshot["kpis"]
        r = snapshot["risk"]
        labels = self.field_metric_labels
        labels["Production"].configure(text=f"{k['average_daily_oil']:,.0f}")
        labels["Field Uptime"].configure(text=f"{k['field_uptime'] * 100:.1f}%")
        labels["Failure Risk"].configure(text=f"{r['average_failure_risk'] * 100:.1f}%")
        labels["Critical Wells"].configure(text=str(r["risk_counts"].get("CRITICAL", 0)))
        labels["Data Quality"].configure(text=f"{k['data_quality_score']:.0f}%")

    def _update_field_risk_panel(self, snapshot):
        if not hasattr(self, "risk_summary_text"):
            return
        counts = snapshot["risk"]["risk_counts"]
        self.risk_summary_text.configure(
            text=f"NORMAL  {counts.get('NORMAL', 0)}    •    WARNING  {counts.get('WARNING', 0)}    •    CRITICAL  {counts.get('CRITICAL', 0)}"
        )

    def _build_risk_summary(self):
        frame = ctk.CTkFrame(self.main_scroll, corner_radius=12, fg_color="#151B23")
        frame.pack(fill="x", pady=(0, 14))
        top = ctk.CTkFrame(frame, fg_color="transparent")
        top.pack(fill="x", padx=14, pady=(12, 4))
        ctk.CTkLabel(top, text="FIELD RISK MONITOR", font=ctk.CTkFont(size=13, weight="bold")).pack(side="left")
        ctk.CTkLabel(top, text="PREDICTIVE • NEXT 7 DAYS", text_color="#64748B", font=ctk.CTkFont(size=9, weight="bold")).pack(side="right")
        self.risk_summary_text = ctk.CTkLabel(frame, text="NORMAL  --    •    WARNING  --    •    CRITICAL  --",
                                              text_color="#CBD5E1", font=ctk.CTkFont(size=11))
        self.risk_summary_text.pack(anchor="w", padx=14, pady=(0, 12))

    def _build_kpi_cards(self):
        """Build KPI cards for key metrics."""
        kpi_frame = ctk.CTkFrame(self.main_scroll)
        kpi_frame.pack(fill="x", pady=(0, 20))
        
        # Risk Score Card
        self.risk_card = ctk.CTkFrame(kpi_frame, corner_radius=10, fg_color="#2C3E50")
        self.risk_card.pack(side="left", fill="both", expand=True, padx=(0, 10))
        
        ctk.CTkLabel(
            self.risk_card,
            text="FAILURE RISK",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="#3498DB"
        ).pack(pady=(15, 5))
        
        self.risk_value_label = ctk.CTkLabel(
            self.risk_card,
            text="--",
            font=ctk.CTkFont(size=36, weight="bold"),
            text_color="#2ECC71"
        )
        self.risk_value_label.pack(pady=(0, 5))
        
        self.risk_level_label = ctk.CTkLabel(
            self.risk_card,
            text="NO WELL SELECTED",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color="gray"
        )
        self.risk_level_label.pack(pady=(0, 15))
        
        # Selected Well Card
        self.well_card = ctk.CTkFrame(kpi_frame, corner_radius=10, fg_color="#2C3E50")
        self.well_card.pack(side="left", fill="both", expand=True, padx=(0, 10))
        
        ctk.CTkLabel(
            self.well_card,
            text="SELECTED WELL",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="#3498DB"
        ).pack(pady=(15, 5))
        
        self.well_name_label = ctk.CTkLabel(
            self.well_card,
            text="--",
            font=ctk.CTkFont(size=20, weight="bold")
        )
        self.well_name_label.pack(pady=(0, 5))
        
        self.well_status_label = ctk.CTkLabel(
            self.well_card,
            text="Select a well to monitor",
            font=ctk.CTkFont(size=12),
            text_color="gray"
        )
        self.well_status_label.pack(pady=(0, 15))
        
        # Field Status Card
        self.field_card = ctk.CTkFrame(kpi_frame, corner_radius=10, fg_color="#2C3E50")
        self.field_card.pack(side="left", fill="both", expand=True)
        
        ctk.CTkLabel(
            self.field_card,
            text="FIELD STATUS",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="#3498DB"
        ).pack(pady=(15, 5))
        
        self.field_wells_label = ctk.CTkLabel(
            self.field_card,
            text="-- wells",
            font=ctk.CTkFont(size=18, weight="bold")
        )
        self.field_wells_label.pack(pady=(0, 5))
        
        self.field_health_label = ctk.CTkLabel(
            self.field_card,
            text="Loading data...",
            font=ctk.CTkFont(size=12),
            text_color="gray"
        )
        self.field_health_label.pack(pady=(0, 15))

    def _build_well_insight_panel(self):
        """Modern selected-well insight panel with operational and ML context."""
        frame = ctk.CTkFrame(self.main_scroll, corner_radius=14, fg_color="#151B23")
        frame.pack(fill="x", pady=(0, 20))

        header = ctk.CTkFrame(frame, fg_color="transparent")
        header.pack(fill="x", padx=16, pady=(14, 8))
        ctk.CTkLabel(header, text="SELECTED WELL INTELLIGENCE",
                     font=ctk.CTkFont(size=14, weight="bold")).pack(side="left")
        self.insight_asof = ctk.CTkLabel(header, text="Awaiting scan", text_color="#64748B",
                                         font=ctk.CTkFont(size=10))
        self.insight_asof.pack(side="right")

        body = ctk.CTkFrame(frame, fg_color="transparent")
        body.pack(fill="x", padx=16, pady=(0, 15))
        body.grid_columnconfigure(0, weight=1)
        body.grid_columnconfigure(1, weight=1)
        body.grid_columnconfigure(2, weight=1)

        self.insight_operational = ctk.CTkLabel(body, text="Operational snapshot\n--", justify="left", anchor="w",
                                                text_color="#CBD5E1", font=ctk.CTkFont(size=11))
        self.insight_operational.grid(row=0, column=0, sticky="nsew", padx=(0, 10))

        self.insight_drivers = ctk.CTkLabel(body, text="Risk drivers\nRun diagnostics to calculate contributors.",
                                            justify="left", anchor="w", text_color="#CBD5E1",
                                            font=ctk.CTkFont(size=11), wraplength=320)
        self.insight_drivers.grid(row=0, column=1, sticky="nsew", padx=10)

        self.insight_action = ctk.CTkLabel(body, text="Monitoring state\nNo prediction loaded",
                                           justify="left", anchor="w", text_color="#CBD5E1",
                                           font=ctk.CTkFont(size=11), wraplength=320)
        self.insight_action.grid(row=0, column=2, sticky="nsew", padx=(10, 0))

    def _refresh_well_insight(self):
        if not self.current_well:
            return
        try:
            df = load_well_data(self.current_well)
            if df.empty:
                return
            latest = df.iloc[-1]
            self.insight_operational.configure(
                text=(f"Operational snapshot\n"
                      f"Oil rate     {latest['Oil_Rate']:,.1f} bbl/day\n"
                      f"Pressure     {latest['Pressure']:,.1f} psi\n"
                      f"Water cut    {latest['Water_Cut']:.1f}%\n"
                      f"Temperature  {latest['Temperature']:.1f} °C"))
            try:
                details = __import__('predict').get_prediction_details(self.current_well, top_n=4)
                driver_lines = [f"Risk drivers\n{details['score'] * 100:.1f}% • {details['level']}"]
                for d in details['drivers']:
                    driver_lines.append(f"• {d['name']}: {d['contribution']:+.3f}")
                self.insight_drivers.configure(text="\n".join(driver_lines))
                self.insight_asof.configure(text=f"As of {details['as_of']}")
                if details['level'] == 'CRITICAL':
                    action = "Monitoring state\nCRITICAL\nReview contributing signals and operational procedures."
                elif details['level'] == 'WARNING':
                    action = "Monitoring state\nWARNING\nContinue close monitoring and investigate emerging trends."
                else:
                    action = "Monitoring state\nNORMAL\nNo elevated model risk detected."
                self.insight_action.configure(text=action)
            except Exception as error:
                self.insight_drivers.configure(text=f"Risk drivers\nUnavailable: {error}")
        except Exception as error:
            self.insight_operational.configure(text=f"Operational snapshot\nUnavailable: {error}")

    def _build_chart_section(self):
        """Build the chart section with modern toolbar."""
        chart_frame = ctk.CTkFrame(self.main_scroll, corner_radius=10)
        chart_frame.pack(fill="both", expand=True, pady=(0, 20))
        
        # Chart header with toolbar
        header_frame = ctk.CTkFrame(chart_frame, fg_color="transparent")
        header_frame.pack(fill="x", padx=15, pady=(15, 10))
        
        ctk.CTkLabel(
            header_frame,
            text="WELL MONITORING",
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color="#3498DB"
        ).pack(side="left")
        
        # Chart type selector
        self.chart_segmented = ctk.CTkSegmentedButton(
            header_frame,
            values=charts.CHART_TYPES,
            command=self.show_chart,
            height=35
        )
        self.chart_segmented.pack(side="right")
        self.chart_segmented.set(charts.CHART_TYPES[0])
        
        # Chart panel
        self.chart_panel_frame = ctk.CTkFrame(chart_frame, fg_color="transparent")
        self.chart_panel_frame.pack(fill="both", expand=True, padx=15, pady=(0, 15))
        
        # Embed the matplotlib chart panel
        self.chart_panel = ChartPanel(self.chart_panel_frame)
        self.chart_panel.pack(fill="both", expand=True)

    def _build_eda_section(self):
        """Build the EDA section with modern toolbar."""
        eda_frame = ctk.CTkFrame(self.main_scroll, corner_radius=10)
        eda_frame.pack(fill="both", expand=True, pady=(0, 20))
        
        # EDA header with toolbar
        header_frame = ctk.CTkFrame(eda_frame, fg_color="transparent")
        header_frame.pack(fill="x", padx=15, pady=(15, 10))
        
        ctk.CTkLabel(
            header_frame,
            text="EXPLORATORY DATA ANALYSIS",
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color="#3498DB"
        ).pack(side="left")
        
        # EDA view selector
        self.eda_segmented = ctk.CTkSegmentedButton(
            header_frame,
            values=eda.EDA_VIEWS,
            command=self.show_eda_view,
            height=35
        )
        self.eda_segmented.pack(side="right")
        self.eda_segmented.set(eda.EDA_VIEWS[0])
        
        # EDA panel
        self.eda_panel_frame = ctk.CTkFrame(eda_frame, fg_color="transparent")
        self.eda_panel_frame.pack(fill="both", expand=True, padx=15, pady=(0, 15))
        
        # Embed the matplotlib EDA panel
        self.eda_panel = eda.EDAPanel(self.eda_panel_frame)
        self.eda_panel.pack(fill="both", expand=True)

    def _build_reports_section(self):
        """Build the reports workspace with responsive report tabs."""

        reports_frame = ctk.CTkFrame(
            self.main_scroll,
            corner_radius=10
        )
        reports_frame.pack(
            fill="both",
            expand=True
        )

        # ---------------------------------------------------------
        # Header
        # ---------------------------------------------------------
        header_frame = ctk.CTkFrame(
            reports_frame,
            fg_color="transparent"
        )
        header_frame.pack(
            fill="x",
            padx=15,
            pady=(15, 10)
        )

        ctk.CTkLabel(
            header_frame,
            text="ANALYTICAL REPORTS",
            font=ctk.CTkFont(
                size=16,
                weight="bold"
            ),
            text_color="#3498DB"
        ).pack(side="left")

        self.report_status_label = ctk.CTkLabel(
            header_frame,
            text="Select a report",
            text_color="#64748B",
            font=ctk.CTkFont(size=10)
        )
        self.report_status_label.pack(
            side="right"
        )

        # ---------------------------------------------------------
        # Tabs
        # ---------------------------------------------------------
        self.tabview = ctk.CTkTabview(
            reports_frame,
            height=200,
            command=self._on_report_tab_changed
        )

        self.tabview.pack(
            fill="both",
            expand=True,
            padx=15,
            pady=(0, 15)
        )

        self.tabview.add("Field Overview")
        self.tabview.add("Technical Report")
        self.tabview.add("Stakeholder Report")

        # Field Overview FIRST and selected by default.
        self.tabview.set("Field Overview")

        self.technical_text = self._create_report_text(
            self.tabview.tab("Technical Report")
        )

        self.stakeholder_text = self._create_report_text(
            self.tabview.tab("Stakeholder Report")
        )

        self.field_text = self._create_report_text(
            self.tabview.tab("Field Overview")
        )

        # Initial content.
        self._set_text(
            self.field_text,
            "Loading field intelligence…"
        )

        # Load the default tab after the GUI has rendered.
        self.after(
            150,
            self.refresh_field_summary
        )

    def _on_report_tab_changed(self, tab_name):
        """Load the selected report when its tab becomes active."""

        if tab_name == "Field Overview":
            self.refresh_field_summary()

        elif tab_name in (
            "Technical Report",
            "Stakeholder Report"
        ):
            if self.current_well:
                self._refresh_reports(
                    self.current_well
                )
            else:
                self.report_status_label.configure(
                    text="Select a well first"
                )

    def _create_report_text(self, parent):
        """Create a modern text widget for reports."""
        text_frame = ctk.CTkFrame(parent, fg_color="transparent")
        text_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Use standard tkinter text with custom styling
        text = tk.Text(
            text_frame,
            bg="#1E272E",
            fg="white",
            font=("Consolas", 10),
            wrap="word",
            relief="flat",
            padx=15,
            pady=15
        )
        text.pack(fill="both", expand=True)
        
        # Add scrollbar
        scrollbar = ttk.Scrollbar(text_frame, command=text.yview)
        scrollbar.pack(side="right", fill="y")
        text.config(yscrollcommand=scrollbar.set)
        
        return text

    def _build_status_bar(self):
        """Build modern status bar."""
        status_frame = ctk.CTkFrame(self.main_container, height=40)
        status_frame.pack(fill="x", side="bottom", pady=(20, 0))
        status_frame.pack_propagate(False)
        
        self.status_label = ctk.CTkLabel(
            status_frame,
            text="Ready",
            font=ctk.CTkFont(size=12),
            anchor="w"
        )
        self.status_label.pack(side="left", padx=20, pady=10)

    # -----------------------------------------------------------------
    # Utility Methods (adapted from original app.py)
    # -----------------------------------------------------------------

    def set_status(self, message, level='muted'):
        """Update status bar with message and color coding."""
        color_map = {
            'muted': 'gray',
            'normal': '#2ECC71',
            'warning': '#F39C12',
            'critical': '#E74C3C'
        }
        self.status_label.configure(text=message, text_color=color_map.get(level, 'gray'))

    def _set_text(self, widget, content):
        """Replace text widget content."""
        widget.config(state='normal')
        widget.delete('1.0', 'end')
        widget.insert('1.0', content)
        widget.config(state='disabled')

    def _load_wells(self):
        """Load wells from database and update UI."""
        try:
            wells = get_well_ids()
            self.db_status_label.configure(
                text=f"● DB: {len(wells)} wells",
                text_color="#2ECC71" if wells else "#F39C12"
            )
            self.field_wells_label.configure(text=f"{len(wells)} wells")
        except Exception as error:
            wells = []
            self.set_status(f'Database unavailable: {error}', 'critical')
            self.db_status_label.configure(text="● DB: Error", text_color="#E74C3C")
        
        self.well_listbox.delete(0, 'end')
        for well_id in wells:
            self.well_listbox.insert('end', well_id)
        
        if wells:
            self.well_listbox.selection_set(0)
            self.current_well = wells[0]
            self.well_name_label.configure(text=wells[0])
            self.well_status_label.configure(text="Ready for diagnostics")
            self.set_status(f'{len(wells)} wells loaded. Select one and run diagnostics.')
        else:
            self.set_status('No wells found. Load CSV data first.', 'warning')
            self.field_health_label.configure(text="No data available")

    def _refresh_csv_list(self):
        """Refresh CSV file list in dropdown."""
        csv_files = []
        if os.path.exists(RAW_DATA_DIR):
            csv_files.extend([f for f in os.listdir(RAW_DATA_DIR) if f.endswith('.csv')])
        if os.path.exists('.'):
            csv_files.extend([f for f in os.listdir('.') if f.endswith('.csv')])
        if os.path.exists('data'):
            csv_files.extend([f'data/{f}' for f in os.listdir('data') if f.endswith('.csv')])
        
        if csv_files:
            self.csv_dropdown.configure(values=csv_files)
            if csv_files:
                self.csv_dropdown.set('')
        else:
            self.csv_dropdown.configure(values=['No CSV files found'])
            self.csv_dropdown.set('No CSV files found')

    # -----------------------------------------------------------------
    # Data Loading Methods (adapted from original app.py)
    # -----------------------------------------------------------------

    def generate_csv_file(self):
        """Generate new CSV file."""
        log_gui_event('generate_csv', 'User clicked Generate CSV button')
        self.set_status('Generating CSV file…')
        self.update()
        
        try:
            csv_path = generate_data.generate_and_export_csv(use_raw_folder=True)
            log_gui_event('csv_generated', f'CSV file created at {csv_path}')
            self.set_status(f'CSV generated: {os.path.basename(csv_path)}')
            messagebox.showinfo('Success', f'CSV file generated:\n{csv_path}\n\nSelect it from the dropdown and click "Load Data" to load into database.')
            self._refresh_csv_list()
        except Exception as error:
            log_system_error('csv_generation_error', f'Failed to generate CSV: {error}', error)
            messagebox.showerror('Generation failed', f'Failed to generate CSV: {error}')
            self.set_status(f'CSV generation failed: {error}', 'critical')

    def load_selected_csv(self):
        """Load selected CSV into database."""
        csv_file = self.csv_var.get()
        if not csv_file or csv_file == 'No CSV files found':
            messagebox.showinfo('No CSV selected', 'Please select a CSV file from the dropdown.')
            return
        
        log_gui_event('load_csv', f'User selected CSV: {csv_file}')
        self.set_status(f'Loading {csv_file} into database…')
        self.update()
        
        try:
            if not os.path.exists(csv_file):
                csv_file = os.path.join(RAW_DATA_DIR, csv_file)
            if not os.path.exists(csv_file):
                csv_file = f'data/{csv_file}'
            
            if not os.path.exists(csv_file):
                messagebox.showerror('File not found', f'CSV file not found: {csv_file}')
                self.set_status('CSV file not found', 'critical')
                return
            
            inserted = load_csv_into_db(csv_file)
            log_gui_event('csv_loaded', f'Loaded {inserted} rows from {csv_file}')
            self.set_status(f'Loaded {inserted} rows from {csv_file}')
            messagebox.showinfo('Success', f'Loaded {inserted} rows from {csv_file} into database.')
            self._load_wells()
        except Exception as error:
            log_system_error('csv_load_error', f'Failed to load CSV: {error}', error)
            messagebox.showerror('Load failed', f'Failed to load CSV: {error}')
            self.set_status(f'CSV load failed: {error}', 'critical')

    def show_database_stats(self):
        """Display database statistics."""
        try:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            
            cursor.execute("SELECT COUNT(*) FROM production_data")
            total_rows = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(DISTINCT Well_ID) FROM production_data")
            unique_wells = cursor.fetchone()[0]
            
            cursor.execute("SELECT MIN(Date), MAX(Date) FROM production_data")
            date_range = cursor.fetchone()
            
            cursor.execute("SELECT COUNT(*) FROM production_data WHERE Pump_Status = 1")
            failure_count = cursor.fetchone()[0]
            
            conn.close()
            
            stats_text = f"""Database Statistics
{'=' * 40}

Total Records: {total_rows}
Unique Wells: {unique_wells}
Date Range: {date_range[0] or 'N/A'} to {date_range[1] or 'N/A'}
Failure Records: {failure_count}
Failure Rate: {failure_count/total_rows*100:.1f}% if total_rows > 0 else 0%
"""
            
            messagebox.showinfo('Database Statistics', stats_text)
            self.set_status('Database statistics displayed')
        except Exception as error:
            messagebox.showerror('Error', f'Failed to get database stats: {error}')
            self.set_status('Database stats failed', 'critical')

    def clear_database(self):
        """Clear all data from database."""
        if not messagebox.askyesno(
            'Confirm Clear Database',
            'This will delete ALL data from the database. This action cannot be undone.\n\nDo you want to continue?'
        ):
            return
        
        try:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            cursor.execute("DELETE FROM production_data")
            deleted = cursor.rowcount
            conn.commit()
            conn.close()
            
            messagebox.showinfo('Success', f'Cleared {deleted} records from database.')
            self.set_status(f'Database cleared: {deleted} records removed')
            self._load_wells()
        except Exception as error:
            messagebox.showerror('Error', f'Failed to clear database: {error}')
            self.set_status('Database clear failed', 'critical')

    def export_database_to_csv(self):
        """Export database to CSV."""
        try:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            
            cursor.execute("SELECT * FROM production_data ORDER BY Well_ID, Date")
            rows = cursor.fetchall()
            
            cursor.execute("PRAGMA table_info(production_data)")
            columns = [info[1] for info in cursor.fetchall()]
            
            conn.close()
            
            if not rows:
                messagebox.showinfo('No Data', 'Database is empty. Nothing to export.')
                return
            
            timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
            export_path = os.path.join(RAW_DATA_DIR, f'db_export_{timestamp}.csv')
            os.makedirs(RAW_DATA_DIR, exist_ok=True)
            
            with open(export_path, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(columns)
                writer.writerows(rows)
            
            messagebox.showinfo('Export Success', f'Exported {len(rows)} records to:\n{export_path}')
            self.set_status(f'Database exported to {os.path.basename(export_path)}')
            self._refresh_csv_list()
        except Exception as error:
            messagebox.showerror('Export Failed', f'Failed to export database: {error}')
            self.set_status('Database export failed', 'critical')

    def validate_selected_csv(self):
        """Validate selected CSV file."""
        csv_file = self.csv_var.get()
        if not csv_file or csv_file == 'No CSV files found':
            messagebox.showinfo('No CSV selected', 'Please select a CSV file from the dropdown.')
            return
        
        self.set_status(f'Validating {csv_file}…')
        self.update()
        
        try:
            actual_csv_file = csv_file
            if not os.path.exists(actual_csv_file):
                actual_csv_file = os.path.join(RAW_DATA_DIR, csv_file)
            if not os.path.exists(actual_csv_file):
                actual_csv_file = f'data/{csv_file}'
            
            if not os.path.exists(actual_csv_file):
                messagebox.showerror('File not found', f'CSV file not found: {csv_file}')
                self.set_status('CSV file not found', 'critical')
                return
            
            with open(actual_csv_file, 'r') as f:
                reader = csv.reader(f)
                header = next(reader)
                
                expected_columns = ['Well_ID', 'Date', 'Oil_Rate', 'Water_Cut', 'Pressure', 'Temperature', 'Pump_Status']
                
                if header != expected_columns:
                    messagebox.showwarning(
                        'CSV Structure Warning',
                        f'CSV header does not match expected format.\n\n'
                        f'Expected: {expected_columns}\n'
                        f'Found: {header}\n\n'
                        f'The file may still load, but could cause issues.'
                    )
                
                row_count = sum(1 for row in reader) + 1
                
                f.seek(0)
                next(reader)
                well_date_pairs = set()
                duplicates = 0
                for row in reader:
                    if len(row) >= 2:
                        pair = (row[0], row[1])
                        if pair in well_date_pairs:
                            duplicates += 1
                        well_date_pairs.add(pair)
            
            validation_result = f"""CSV Validation Results
{'=' * 40}

File: {os.path.basename(actual_csv_file)}
Total Rows: {row_count}
Unique Well/Date Pairs: {len(well_date_pairs)}
Potential Duplicates: {duplicates}
Header Format: {'✓ Valid' if header == expected_columns else '⚠ Warning'}

{'✓ CSV structure is valid' if header == expected_columns else '⚠ CSV structure may have issues'}
"""
            
            messagebox.showinfo('Validation Complete', validation_result)
            self.set_status(f'CSV validated: {row_count} rows, {duplicates} potential duplicates')
        except Exception as error:
            messagebox.showerror('Validation Failed', f'Failed to validate CSV: {error}')
            self.set_status(f'CSV validation failed: {error}', 'critical')

    # -----------------------------------------------------------------
    # System Log Methods (adapted from original app.py)
    # -----------------------------------------------------------------

    def show_system_logs(self):
        """Display system logs in modern dialog."""
        log_gui_event('view_logs', 'User requested to view system logs')
        
        try:
            recent_logs = get_recent_logs(100)
            
            log_window = ctk.CTkToplevel(self)
            log_window.title("System Logs")
            log_window.geometry("800x600")
            
            log_frame = ctk.CTkFrame(log_window)
            log_frame.pack(fill="both", expand=True, padx=20, pady=20)
            
            log_text = tk.Text(
                log_frame,
                bg="#1E272E",
                fg="white",
                font=("Consolas", 10),
                wrap="none",
                relief="flat",
                padx=15,
                pady=15
            )
            log_text.pack(fill="both", expand=True)
            
            for log_line in recent_logs:
                log_text.insert('end', log_line)
            
            log_text.config(state='disabled')
            
            close_btn = ctk.CTkButton(
                log_frame,
                text="Close",
                command=log_window.destroy,
                height=40,
                fg_color="#E74C3C",
                hover_color="#C0392B"
            )
            close_btn.pack(pady=10)
            
            self.set_status('System logs displayed')
        except Exception as error:
            log_system_error('log_view_error', f'Failed to display logs: {error}', error)
            messagebox.showerror('Error', f'Failed to display logs: {error}')
            self.set_status('Failed to display logs', 'critical')

    def clear_system_logs(self):
        """Clear system logs."""
        if not messagebox.askyesno(
            'Confirm Clear Logs',
            'This will delete all system logs. This action cannot be undone.\n\nDo you want to continue?'
        ):
            return
        
        log_gui_event('clear_logs', 'User requested to clear system logs')
        
        try:
            clear_logs()
            messagebox.showinfo('Success', 'System logs have been cleared.')
            self.set_status('System logs cleared')
        except Exception as error:
            log_system_error('log_clear_error', f'Failed to clear logs: {error}', error)
            messagebox.showerror('Error', f'Failed to clear logs: {error}')
            self.set_status('Failed to clear logs', 'critical')

    def test_smtp_connection(self):
        """Test SMTP connection."""
        log_gui_event('test_smtp', 'User requested SMTP connection test')
        self.set_status('Testing SMTP connection…')
        self.update()
        
        try:
            result = emailer.test_smtp_connection()
            messagebox.showinfo('SMTP Connection Test', result)
            self.set_status('SMTP connection test completed')
        except Exception as error:
            log_system_error('smtp_test_error', f'SMTP test failed: {error}', error)
            messagebox.showerror('Test Failed', f'SMTP connection test failed: {error}')
            self.set_status('SMTP test failed', 'critical')

    # -----------------------------------------------------------------
    # Well Selection and Diagnostics (adapted from original app.py)
    # -----------------------------------------------------------------

    def on_well_selected(self, _event=None):
        """Handle well selection and immediately update the selected-well UI."""
        selection = self.well_listbox.curselection()
        if not selection:
            return

        well_id = self.well_listbox.get(selection[0])

        # Update application state immediately.
        self.current_well = well_id
        self.current_score = None

        # ---------------------------------------------------------
        # IMMEDIATE UI UPDATE
        # ---------------------------------------------------------
        # Do not wait for the database/ML worker before changing
        # the selected well shown by the interface.
        self.well_name_label.configure(text=well_id)

        self.well_page_name.configure(text=well_id)
        self.well_status_label.configure(text="Loading well intelligence…")
        self.well_page_status.configure(text="Loading well intelligence…")

        self.risk_value_label.configure(
            text="--",
            text_color="#94A3B8"
        )
        self.risk_level_label.configure(
            text="LOADING",
            text_color="#94A3B8"
        )

        # Immediately clear/update the intelligence panel.
        self.insight_operational.configure(
            text="Operational snapshot\nLoading…"
        )
        self.insight_drivers.configure(
            text="Risk drivers\nCalculating…"
        )
        self.insight_action.configure(
            text="Monitoring state\nLoading prediction…"
        )
        self.insight_asof.configure(
            text="Loading..."
        )

        # Immediately reset well-page metrics.
        for metric in self.well_page_metrics.values():
            metric.configure(text="--")

        # Force Tkinter to render the new selection immediately.
        self.update_idletasks()

        # ---------------------------------------------------------
        # BACKGROUND DATA / ML WORK
        # ---------------------------------------------------------
        selected_well = well_id

        self._run_background(
            lambda: self._load_well_intelligence(selected_well),
            lambda result: self._well_intelligence_success(
                selected_well,
                result
            ),
            lambda error: self._well_intelligence_error(
                selected_well,
                error
            ),
        )

        # Refresh the chart for the newly selected well.
        # It is deliberately scheduled after the current UI event.
        self.after(
            10,
            lambda: self._refresh_selected_well_chart(selected_well)
        )
    
    def _refresh_selected_well_chart(self, well_id):
        """Refresh the chart only if the selected well has not changed."""
        if self.current_well != well_id:
            return

        try:
            self.chart_panel.plot(
                self.current_chart,
                well_id
            )
            self.set_status(
                f"{self.current_chart} chart • {well_id}"
            )
        except Exception as error:
            self.set_status(
                f"Chart failed: {error}",
                "critical"
            )
    
    def _load_well_intelligence(self, well_id):
        df = load_well_data(well_id)
        if df.empty:
            return {"empty": True}
        latest = df.iloc[-1]
        try:
            details = __import__('predict').get_prediction_details(well_id, top_n=4)
        except Exception as error:
            details = {"well_id": well_id, "score": None, "level": "UNAVAILABLE", "drivers": [], "as_of": str(latest["Date"])}
            details["error"] = str(error)
        return {"latest": latest.to_dict(), "details": details}

    def _well_page_intelligence_success(self, well_id, result):
        """Render the selected well's intelligence in the Wells workspace."""

        # Ignore stale background results.
        # This is important if the user clicks WELL-01 and immediately
        # clicks WELL-02.
        if self.current_well != well_id:
            return

        if result.get("empty"):
            self.well_page_name.configure(text=well_id)
            self.well_page_status.configure(text="No data available")
            return

        latest = result["latest"]
        details = result["details"]

        # ---------------------------------------------------------
        # Selected well
        # ---------------------------------------------------------
        self.well_page_name.configure(text=well_id)

        # ---------------------------------------------------------
        # Operational measurements
        # ---------------------------------------------------------
        self.well_page_metrics["Oil Rate"].configure(
            text=f"{float(latest['Oil_Rate']):,.1f} bbl/day"
        )

        self.well_page_metrics["Pressure"].configure(
            text=f"{float(latest['Pressure']):,.1f} psi"
        )

        self.well_page_metrics["Water Cut"].configure(
            text=f"{float(latest['Water_Cut']):.1f}%"
        )

        self.well_page_metrics["Temperature"].configure(
            text=f"{float(latest['Temperature']):.1f} °C"
        )

        # ---------------------------------------------------------
        # Prediction
        # ---------------------------------------------------------
        score = details.get("score")

        if score is None:
            error = details.get(
                "error",
                "Model prediction unavailable"
            )

            self.well_page_status.configure(
                text=f"Prediction unavailable • {error}"
            )

            self.insight_drivers.configure(
                text=f"Risk drivers\nUnavailable\n{error}"
            )

            self.insight_action.configure(
                text="Monitoring state\nMODEL UNAVAILABLE"
            )

            return

        level = details["level"]

        self.well_page_status.configure(
            text=(
                f"7-day model risk • "
                f"{level} • "
                f"{score * 100:.1f}%"
            )
        )

        # ---------------------------------------------------------
        # Risk card
        # ---------------------------------------------------------
        self.risk_value_label.configure(
            text=f"{score * 100:.0f}%"
        )

        risk_colors = {
            "NORMAL": "#22C55E",
            "WARNING": "#F59E0B",
            "CRITICAL": "#EF4444",
        }

        risk_color = risk_colors.get(
            level,
            "#94A3B8"
        )

        self.risk_value_label.configure(
            text_color=risk_color
        )

        self.risk_level_label.configure(
            text=level,
            text_color=risk_color
        )

        self.well_status_label.configure(
            text=f"{level} • {score * 100:.1f}% risk"
        )

        # ---------------------------------------------------------
        # Explainability
        # ---------------------------------------------------------
        driver_lines = [
            "Risk drivers",
            f"{score * 100:.1f}% • {level}"
        ]

        for driver in details.get("drivers", []):
            driver_lines.append(
                f"• {driver['name']}: "
                f"{driver['contribution']:+.3f}"
            )

        self.insight_drivers.configure(
            text="\n".join(driver_lines)
        )

        self.insight_asof.configure(
            text=f"As of {details.get('as_of', 'N/A')}"
        )

        monitoring_state = {
            "CRITICAL": (
                "Monitoring state\n"
                "CRITICAL\n"
                "Review contributing signals and "
                "follow operational procedures."
            ),
            "WARNING": (
                "Monitoring state\n"
                "WARNING\n"
                "Continue close monitoring and "
                "investigate emerging trends."
            ),
            "NORMAL": (
                "Monitoring state\n"
                "NORMAL\n"
                "No elevated model risk detected."
            ),
        }

        self.insight_action.configure(
            text=monitoring_state.get(
                level,
                "Monitoring state\nUNAVAILABLE"
            )
        )

        # ---------------------------------------------------------
        # Critical alert processing
        # ---------------------------------------------------------
        new_alerts = self._alert_manager.observe({
            "well_id": well_id,
            "score": score,
            "level": level
        })

        for alert in new_alerts:
            self._raise_alert(
                alert["well_id"],
                alert["score"],
                send_email_async=True
            )

        if self._alert_manager.pending():
            self._show_alert_bar()

        self.update_idletasks()

    def _well_intelligence_error(self, well_id, error):
        if self.current_well == well_id:
            self.well_status_label.configure(text=f"Unable to load well data: {error}")

    def _refresh_well_snapshot(self):
        """Update the selected-well mini status without requiring a full report."""
        if not self.current_well:
            return
        try:
            details = predict_failure_risk(self.current_well)
            level = get_risk_level(details)
            self.well_status_label.configure(text=f"7-day model risk • {level} • {details * 100:.1f}%")
        except Exception:
            self.well_status_label.configure(text="Ready for diagnostics")

    def show_chart(self, chart_type):
        """Display selected chart type."""
        self.current_chart = chart_type
        self.chart_segmented.set(chart_type)
        
        if not self.current_well:
            return
        
        try:
            self.chart_panel.plot(chart_type, self.current_well)
            self.set_status(f'{chart_type} chart — {self.current_well}')
        except Exception as error:
            self.set_status(f'Chart failed: {error}', 'critical')

    def show_eda_view(self, view_name):
        """Display selected EDA view."""
        self.current_eda_view = view_name
        self.eda_segmented.set(view_name)
        
        try:
            self.eda_panel.plot(view_name)
            self.set_status(f'EDA view: {view_name}')
        except Exception as error:
            self.set_status(f'EDA error: {error}', 'critical')
            log_system_error('eda_view_error', f'Failed to show EDA view {view_name}: {error}', error)

    def run_diagnostics(self):
        """Run diagnostics in a worker so ML/database work cannot freeze Tkinter."""
        if not self.current_well:
            messagebox.showinfo('No well selected', 'Select a well first.')
            return
        well_id = self.current_well
        self.set_status(f'Scoring {well_id}…')
        self._run_background(
            lambda: predict_failure_risk(well_id),
            lambda score: self._diagnostics_success(well_id, score),
            lambda error: self._diagnostics_error(error),
        )

    def _diagnostics_error(self, error):
        if isinstance(error, FileNotFoundError):
            messagebox.showwarning('Model not trained', f'{error}\n\nRun this once from the project root:\n    python train_model.py')
            self.set_status('No trained model.', 'warning')
        else:
            messagebox.showerror('Diagnostics failed', str(error))
            self.set_status(f'Diagnostics failed: {error}', 'critical')

    def _diagnostics_success(self, well_id, score):
        self.current_score = score
        level = get_risk_level(score)
        self.risk_value_label.configure(text=f'{score * 100:.0f}%')
        color_map = {'NORMAL': '#2ECC71', 'WARNING': '#F39C12', 'CRITICAL': '#E74C3C'}
        risk_color = color_map.get(level, '#2ECC71')
        self.risk_value_label.configure(text_color=risk_color)
        self.risk_level_label.configure(text=level, text_color=risk_color)
        self.well_status_label.configure(text=f'{level} - {score * 100:.1f}% risk')
        self.set_status(f'{well_id}: {level} ({score * 100:.1f}%)', level.lower() if level != 'CRITICAL' else 'critical')
        new_alerts = self._alert_manager.observe({'well_id': well_id, 'score': score, 'level': level})
        for alert in new_alerts:
            self._raise_alert(alert["well_id"], alert["score"], send_email_async=True)
        if self._alert_manager.pending():
            self._show_alert_bar()
        if self.current_page == 'Reports':
            self._refresh_reports(well_id)
        self.after_idle(lambda: self.show_chart(self.current_chart))

    def _refresh_reports(self, well_id):
        """Refresh all reports."""
        try:
            self._set_text(self.technical_text, reports.technical_report(well_id))
            self._set_text(self.stakeholder_text, reports.stakeholder_report(well_id))
        except Exception as error:
            self.set_status(f'Report generation failed: {error}', 'critical')

    def refresh_field_summary(self):
        """Generate the field report without blocking the GUI."""

        self.report_status_label.configure(
            text="Generating field overview…"
        )

        self.set_status(
            "Generating field overview…"
        )

        self._run_background(
            reports.field_summary,
            self._field_summary_success,
            self._field_summary_error
        )


    def _field_summary_success(self, report_text):
        """Display the completed field report."""

        self._set_text(
            self.field_text,
            report_text
        )

        self.report_status_label.configure(
            text="Field overview updated"
        )

        self.set_status(
            "Field overview updated",
            "normal"
        )


    def _field_summary_error(self, error):
        """Display field-report errors without crashing the GUI."""

        self._set_text(
            self.field_text,
            (
                "FIELD OVERVIEW ERROR\n\n"
                f"{error}"
            )
        )

        self.report_status_label.configure(
            text="Field overview unavailable"
        )

        self.set_status(
            f"Field overview failed: {error}",
            "critical"
        )

    def _raise_alert(self, well_id, score, send_email_async=True):
        """Register a critical alert and optionally send its email off-thread."""
        log_gui_event('critical_alert', f'Critical risk detected for {well_id}: {score:.2f}')
        if send_email_async:
            self._run_background(
                lambda: self._send_critical_email(well_id, score),
                lambda result: self.set_status(result, 'critical'),
                lambda error: self.set_status(f'Alert email failed: {error}', 'warning'),
            )

    def _send_critical_email(self, well_id, score):
        try:
            path = reports.save_report_to_file(
                reports.technical_report(well_id), f'{well_id}_alert.txt')
            result = emailer.send_alert(well_id, score, path)
            log_gui_event('alert_email_result', f'{well_id}: {result}')
            return result
        except Exception as error:
            log_system_error('alert_error', f'Failed to send alert for {well_id}: {error}', error)
            return f'Critical alert raised for {well_id}; email unavailable.'

    def _on_close(self):
        """Cancel scheduled jobs and stop worker threads before closing."""
        self._closing = True
        for job_name in ("_alert_blink_job", "_alert_scan_job"):
            job = getattr(self, job_name, None)
            if job:
                try:
                    self.after_cancel(job)
                except Exception:
                    pass
        try:
            self._executor.shutdown(wait=False, cancel_futures=True)
        except Exception:
            pass
        self.destroy()

    def logout(self):
        """End the current authenticated session and return to login."""
        username = self.current_user.get("username", "user")
        log_gui_event("logout", f"User logged out: {username}")
        self._on_close()
        login = AuthenticationApp()
        login.mainloop()

    def send_report(self, kind):
        """Send report via email."""
        if not self.current_well:
            messagebox.showinfo('No well selected', 'Select a well first.')
            return
        
        to_email = self.email_entry.get().strip()
        if '@' not in to_email:
            messagebox.showwarning('Invalid address', 'Enter a valid recipient email address.')
            return
        
        well_id = self.current_well
        builder = (reports.technical_report if kind == 'Technical'
                   else reports.stakeholder_report)
        
        self.set_status(f'Sending {kind.lower()} report for {well_id}…')
        self.update()
        
        try:
            path = reports.save_report_to_file(
                builder(well_id), f'{well_id}_{kind.lower()}.txt')
            result = emailer.send_report(to_email, well_id, kind, path)
        except Exception as error:
            messagebox.showerror('Send failed', str(error))
            self.set_status(f'Send failed: {error}', 'critical')
            return
        
        messagebox.showinfo(
            'Report', f'{result}\n\nSaved locally to {os.path.relpath(path)}')
        self.set_status(result)


class AuthenticationApp(ctk.CTk):
    """Modern first-screen authentication and first-run administrator setup."""

    def __init__(self):
        super().__init__()
        auth.init_auth_db()
        self.title("Squad Charlie — Secure Access")
        self.geometry("1100x700")
        self.minsize(900, 600)
        self._setup_mode = auth.user_count() == 0
        self._build_auth_ui()

    def _build_auth_ui(self):
        self.configure(fg_color="#080B12")
        outer = ctk.CTkFrame(self, fg_color="#080B12")
        outer.pack(fill="both", expand=True)

        # Left branding panel
        brand = ctk.CTkFrame(outer, fg_color="#0D1117", corner_radius=0, width=470)
        brand.pack(side="left", fill="both")
        brand.pack_propagate(False)
        ctk.CTkLabel(brand, text="SQUAD CHARLIE",
                     font=ctk.CTkFont(size=30, weight="bold"),
                     text_color="#38bdf8").pack(anchor="w", padx=55, pady=(120, 5))
        ctk.CTkLabel(brand, text="DIGITAL OILFIELD\nCONTROL CENTER",
                     justify="left",
                     font=ctk.CTkFont(size=28, weight="bold")).pack(anchor="w", padx=55)
        ctk.CTkLabel(brand, text="Predictive maintenance • field intelligence •\nsecure operational monitoring",
                     justify="left", text_color="#8B949E",
                     font=ctk.CTkFont(size=14)).pack(anchor="w", padx=55, pady=(18, 0))
        ctk.CTkLabel(brand, text="● SECURE SESSION  •  LOCAL AUTHENTICATION",
                     text_color="#3FB950", font=ctk.CTkFont(size=11, weight="bold")).pack(anchor="w", padx=55, pady=(100, 0))

        # Login card
        card = ctk.CTkFrame(outer, fg_color="#111827", corner_radius=18, width=460)
        card.pack(side="left", fill="both", expand=True, padx=55, pady=55)
        card.pack_propagate(False)

        heading = "Create Administrator Account" if self._setup_mode else "Welcome Back"
        subheading = ("First-run setup • create the account used to access the control center"
                      if self._setup_mode else "Sign in to access the Digital Oilfield Control Center")
        ctk.CTkLabel(card, text=heading, font=ctk.CTkFont(size=25, weight="bold")).pack(anchor="w", padx=45, pady=(55, 5))
        ctk.CTkLabel(card, text=subheading, text_color="#8B949E",
                     wraplength=350, justify="left", font=ctk.CTkFont(size=12)).pack(anchor="w", padx=45, pady=(0, 30))

        ctk.CTkLabel(card, text="USERNAME", text_color="#94A3B8",
                     font=ctk.CTkFont(size=11, weight="bold")).pack(anchor="w", padx=45)
        self.username_var = ctk.StringVar()
        self.username_entry = ctk.CTkEntry(card, textvariable=self.username_var, height=44,
                                           placeholder_text="Enter username")
        self.username_entry.pack(fill="x", padx=45, pady=(6, 18))

        ctk.CTkLabel(card, text="PASSWORD", text_color="#94A3B8",
                     font=ctk.CTkFont(size=11, weight="bold")).pack(anchor="w", padx=45)
        password_row = ctk.CTkFrame(card, fg_color="transparent")
        password_row.pack(fill="x", padx=45, pady=(6, 8))
        self.password_var = ctk.StringVar()
        self.password_entry = ctk.CTkEntry(password_row, textvariable=self.password_var, height=44,
                                           placeholder_text="Enter password", show="•")
        self.password_entry.pack(side="left", fill="x", expand=True)
        self.show_password_var = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(password_row, text="Show", variable=self.show_password_var,
                        command=self._toggle_password, width=55).pack(side="right", padx=(8, 0))

        self.role_var = ctk.StringVar(value="admin")
        if self._setup_mode:
            ctk.CTkLabel(card, text="ROLE", text_color="#94A3B8",
                         font=ctk.CTkFont(size=11, weight="bold")).pack(anchor="w", padx=45, pady=(8, 0))
            ctk.CTkComboBox(card, variable=self.role_var, values=["admin", "operator", "viewer"], height=40).pack(fill="x", padx=45, pady=(6, 10))
        else:
            self.role_var.set("operator")

        self.status_label = ctk.CTkLabel(card, text="", text_color="#F85149",
                                         wraplength=350, justify="left", font=ctk.CTkFont(size=11))
        self.status_label.pack(anchor="w", padx=45, pady=(4, 8))

        self.login_button = ctk.CTkButton(card, text="CREATE ACCOUNT" if self._setup_mode else "SIGN IN",
                                          height=46, font=ctk.CTkFont(size=13, weight="bold"),
                                          fg_color="#2563EB", hover_color="#1D4ED8",
                                          command=self._submit)
        self.login_button.pack(fill="x", padx=45, pady=(4, 14))
        ctk.CTkLabel(card, text="Passwords are stored as salted PBKDF2 hashes; plaintext passwords are never saved.",
                     text_color="#64748B", wraplength=350, justify="left",
                     font=ctk.CTkFont(size=10)).pack(anchor="w", padx=45)

        self.username_entry.focus_set()
        self.bind("<Return>", lambda _e: self._submit())

    def _toggle_password(self):
        self.password_entry.configure(show="" if self.show_password_var.get() else "•")

    def _submit(self):
        username = self.username_var.get().strip()
        password = self.password_var.get()
        if not username or not password:
            self.status_label.configure(text="Enter both username and password.")
            return

        try:
            if self._setup_mode:
                auth.create_user(username, password, self.role_var.get())
                user = auth.authenticate(username, password)
            else:
                user = auth.authenticate(username, password)
        except ValueError as exc:
            self.status_label.configure(text=str(exc))
            return
        except Exception as exc:
            log_system_error("authentication_error", f"Authentication error: {exc}", exc)
            self.status_label.configure(text="Authentication service error. Check the application log.")
            return

        if not user:
            self.status_label.configure(text="Invalid username or password.")
            self.password_var.set("")
            self.password_entry.focus_set()
            return

        log_gui_event("login_success", f"Authenticated user: {user['username']} ({user['role']})")
        self.destroy()
        dashboard = ModernDashboardApp(current_user=user)
        dashboard.mainloop()


if __name__ == "__main__":
    auth_app = AuthenticationApp()
    auth_app.mainloop()
