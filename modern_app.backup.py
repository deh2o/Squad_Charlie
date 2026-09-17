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
import customtkinter as ctk
from tkinter import messagebox, ttk
import tkinter as tk

import charts
import emailer
import reports
import eda
from charts import ChartPanel
from config import COLORS, FONT_FAMILY, RISK_THRESHOLD, TECH_EMAIL, CSV_PATH, RAW_DATA_DIR, DB_PATH
from data_loader import get_well_ids
from predict import get_risk_level, predict_failure_risk
from load_csv import load_csv_into_db
import generate_data
from logger import log_gui_event, log_system_error, get_recent_logs, clear_logs

# Configure CustomTkinter appearance
ctk.set_appearance_mode("dark")  # Modes: "System" (standard), "Dark", "Light"
ctk.set_default_color_theme("dark-blue")  # Themes: "blue" (standard), "green", "dark-blue"


class ModernDashboardApp(ctk.CTk):
    """Modern dashboard application using CustomTkinter."""

    def __init__(self):
        super().__init__()
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
        
        log_gui_event('modern_app_start', 'Modern application started')
        
        self._build_layout()
        self._load_wells()

    def _build_layout(self):
        """Build the modern dashboard layout."""
        # Main container with modern spacing
        self.main_container = ctk.CTkFrame(self)
        self.main_container.pack(fill="both", expand=True, padx=20, pady=20)
        
        # Header section
        self._build_header()
        
        # Content area with sidebar and main dashboard
        self.content_frame = ctk.CTkFrame(self.main_container)
        self.content_frame.pack(fill="both", expand=True, pady=(20, 0))
        
        # Build sidebar and main content
        self._build_sidebar()
        self._build_main_dashboard()
        
        # Status bar
        self._build_status_bar()

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

    def _build_sidebar(self):
        """Build modern sidebar with enhanced widgets."""
        self.sidebar = ctk.CTkFrame(self.content_frame, width=350, corner_radius=10)
        self.sidebar.pack(side="left", fill="y", padx=(0, 20))
        self.sidebar.pack_propagate(False)
        
        # Scrollable sidebar content
        self.sidebar_scroll = ctk.CTkScrollableFrame(
            self.sidebar, 
            label_text="Control Panel",
            label_font=ctk.CTkFont(size=16, weight="bold")
        )
        self.sidebar_scroll.pack(fill="both", expand=True, padx=15, pady=15)
        
        # Data Loading Section
        self._add_section_header("DATA LOADING")
        
        self.generate_csv_btn = ctk.CTkButton(
            self.sidebar_scroll,
            text="Generate CSV",
            command=self.generate_csv_file,
            height=40,
            fg_color="#3498DB",
            hover_color="#2980B9"
        )
        self.generate_csv_btn.pack(fill="x", pady=(0, 10))
        
        self.csv_var = ctk.StringVar()
        self.csv_dropdown = ctk.CTkComboBox(
            self.sidebar_scroll,
            variable=self.csv_var,
            height=40,
            command=self._refresh_csv_list
        )
        self.csv_dropdown.pack(fill="x", pady=(0, 10))
        self._refresh_csv_list()
        
        self.load_data_btn = ctk.CTkButton(
            self.sidebar_scroll,
            text="Load Data",
            command=self.load_selected_csv,
            height=40,
            fg_color="#27AE60",
            hover_color="#229954"
        )
        self.load_data_btn.pack(fill="x", pady=(0, 10))
        
        self.refresh_csv_btn = ctk.CTkButton(
            self.sidebar_scroll,
            text="Refresh CSV List",
            command=self._refresh_csv_list,
            height=35,
            fg_color="transparent",
            border_color="#34495E",
            border_width=2
        )
        self.refresh_csv_btn.pack(fill="x", pady=(0, 20))
        
        # Database Management Section
        self._add_section_header("DATABASE")
        
        self.db_stats_btn = ctk.CTkButton(
            self.sidebar_scroll,
            text="View DB Stats",
            command=self.show_database_stats,
            height=35,
            fg_color="transparent",
            border_color="#34495E",
            border_width=2
        )
        self.db_stats_btn.pack(fill="x", pady=(0, 8))
        
        self.clear_db_btn = ctk.CTkButton(
            self.sidebar_scroll,
            text="Clear All Data",
            command=self.clear_database,
            height=35,
            fg_color="transparent",
            border_color="#E74C3C",
            border_width=2,
            text_color="#E74C3C"
        )
        self.clear_db_btn.pack(fill="x", pady=(0, 8))
        
        self.export_db_btn = ctk.CTkButton(
            self.sidebar_scroll,
            text="Export DB to CSV",
            command=self.export_database_to_csv,
            height=35,
            fg_color="transparent",
            border_color="#34495E",
            border_width=2
        )
        self.export_db_btn.pack(fill="x", pady=(0, 8))
        
        self.validate_csv_btn = ctk.CTkButton(
            self.sidebar_scroll,
            text="Validate CSV",
            command=self.validate_selected_csv,
            height=35,
            fg_color="transparent",
            border_color="#34495E",
            border_width=2
        )
        self.validate_csv_btn.pack(fill="x", pady=(0, 20))
        
        # Wells Section
        self._add_section_header("WELLS")
        
        self.well_listbox = tk.Listbox(
            self.sidebar_scroll,
            height=8,
            font=("Segoe UI", 11),
            bg="#2C3E50",
            fg="white",
            selectbackground="#3498DB",
            selectforeground="white",
            relief="flat",
            highlightthickness=0
        )
        self.well_listbox.pack(fill="x", pady=(0, 10))
        self.well_listbox.bind('<<ListboxSelect>>', self.on_well_selected)
        
        self.run_diagnostics_btn = ctk.CTkButton(
            self.sidebar_scroll,
            text="RUN DIAGNOSTICS",
            command=self.run_diagnostics,
            height=45,
            fg_color="#E74C3C",
            hover_color="#C0392B",
            font=ctk.CTkFont(size=14, weight="bold")
        )
        self.run_diagnostics_btn.pack(fill="x", pady=(0, 10))
        
        self.refresh_field_btn = ctk.CTkButton(
            self.sidebar_scroll,
            text="Refresh Field Summary",
            command=self.refresh_field_summary,
            height=35,
            fg_color="transparent",
            border_color="#34495E",
            border_width=2
        )
        self.refresh_field_btn.pack(fill="x", pady=(0, 20))
        
        # Email Section
        self._add_section_header("EMAIL REPORT")
        
        self.email_entry = ctk.CTkEntry(
            self.sidebar_scroll,
            placeholder_text="Recipient email",
            height=40
        )
        self.email_entry.insert(0, TECH_EMAIL)
        self.email_entry.pack(fill="x", pady=(0, 10))
        
        self.send_tech_btn = ctk.CTkButton(
            self.sidebar_scroll,
            text="Send Technical Report",
            command=lambda: self.send_report('Technical'),
            height=35,
            fg_color="transparent",
            border_color="#34495E",
            border_width=2
        )
        self.send_tech_btn.pack(fill="x", pady=(0, 8))
        
        self.send_stakeholder_btn = ctk.CTkButton(
            self.sidebar_scroll,
            text="Send Stakeholder Report",
            command=lambda: self.send_report('Stakeholder'),
            height=35,
            fg_color="transparent",
            border_color="#34495E",
            border_width=2
        )
        self.send_stakeholder_btn.pack(fill="x", pady=(0, 8))
        
        self.test_smtp_btn = ctk.CTkButton(
            self.sidebar_scroll,
            text="Test SMTP Connection",
            command=self.test_smtp_connection,
            height=35,
            fg_color="transparent",
            border_color="#34495E",
            border_width=2
        )
        self.test_smtp_btn.pack(fill="x", pady=(0, 10))
        
        # Auto-alert info
        ctk.CTkLabel(
            self.sidebar_scroll,
            text=f"Auto-alert to {TECH_EMAIL}\nat risk ≥ {RISK_THRESHOLD:.0%}",
            font=ctk.CTkFont(size=11),
            text_color="gray",
            wraplength=300
        ).pack(anchor="w", pady=(0, 20))
        
        # System Logs Section
        self._add_section_header("SYSTEM LOGS")
        
        self.view_logs_btn = ctk.CTkButton(
            self.sidebar_scroll,
            text="View Recent Logs",
            command=self.show_system_logs,
            height=35,
            fg_color="transparent",
            border_color="#34495E",
            border_width=2
        )
        self.view_logs_btn.pack(fill="x", pady=(0, 8))
        
        self.clear_logs_btn = ctk.CTkButton(
            self.sidebar_scroll,
            text="Clear Logs",
            command=self.clear_system_logs,
            height=35,
            fg_color="transparent",
            border_color="#E74C3C",
            border_width=2,
            text_color="#E74C3C"
        )
        self.clear_logs_btn.pack(fill="x", pady=(0, 20))

    def _add_section_header(self, text):
        """Add a section header to the sidebar."""
        separator = ctk.CTkFrame(self.sidebar_scroll, height=2, fg_color="#34495E")
        separator.pack(fill="x", pady=(15, 10))
        
        ctk.CTkLabel(
            self.sidebar_scroll,
            text=text,
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color="#3498DB"
        ).pack(anchor="w")

    def _build_main_dashboard(self):
        """Build the main dashboard area with KPI cards and charts."""
        self.dashboard_content = ctk.CTkFrame(self.content_frame, corner_radius=10)
        self.dashboard_content.pack(side="left", fill="both", expand=True)
        
        # Scrollable main content
        self.main_scroll = ctk.CTkScrollableFrame(self.dashboard_content)
        self.main_scroll.pack(fill="both", expand=True, padx=15, pady=15)
        
        # KPI Cards Row
        self._build_kpi_cards()
        
        # Chart Section
        self._build_chart_section()
        
        # EDA Section
        self._build_eda_section()
        
        # Reports Section
        self._build_reports_section()

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
        """Build the reports section with modern tabbed interface."""
        reports_frame = ctk.CTkFrame(self.main_scroll, corner_radius=10)
        reports_frame.pack(fill="both", expand=True)
        
        # Reports header
        header_frame = ctk.CTkFrame(reports_frame, fg_color="transparent")
        header_frame.pack(fill="x", padx=15, pady=(15, 10))
        
        ctk.CTkLabel(
            header_frame,
            text="ANALYTICAL REPORTS",
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color="#3498DB"
        ).pack(side="left")
        
        # Tabbed interface for reports
        self.tabview = ctk.CTkTabview(reports_frame, height=200)
        self.tabview.pack(fill="both", expand=True, padx=15, pady=(0, 15))
        
        self.tabview.add("Technical Report")
        self.tabview.add("Stakeholder Report")
        self.tabview.add("Field Overview")
        
        # Create text areas for each tab
        self.technical_text = self._create_report_text(self.tabview.tab("Technical Report"))
        self.stakeholder_text = self._create_report_text(self.tabview.tab("Stakeholder Report"))
        self.field_text = self._create_report_text(self.tabview.tab("Field Overview"))

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
            self.show_chart(self.current_chart)
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
        """Handle well selection."""
        selection = self.well_listbox.curselection()
        if not selection:
            return
        
        self.current_well = self.well_listbox.get(selection[0])
        self.current_score = None
        
        self.well_name_label.configure(text=self.current_well)
        self.well_status_label.configure(text="Ready for diagnostics")
        self.risk_value_label.configure(text="--", text_color="#2ECC71")
        self.risk_level_label.configure(text="NOT DIAGNOSED", text_color="gray")
        
        self.show_chart(self.current_chart)

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
        """Run diagnostics on selected well."""
        if not self.current_well:
            messagebox.showinfo('No well selected', 'Select a well first.')
            return
        
        well_id = self.current_well
        self.set_status(f'Scoring {well_id}…')
        self.update()
        
        try:
            score = predict_failure_risk(well_id)
        except FileNotFoundError as error:
            messagebox.showwarning(
                'Model not trained',
                f'{error}\n\nRun this once from the project root:\n    python train_model.py')
            self.set_status('No trained model.', 'warning')
            return
        except Exception as error:
            messagebox.showerror('Diagnostics failed', str(error))
            self.set_status(f'Diagnostics failed: {error}', 'critical')
            return
        
        self.current_score = score
        level = get_risk_level(score)
        
        # Update KPI cards
        self.risk_value_label.configure(text=f'{score * 100:.0f}%')
        
        color_map = {
            'NORMAL': '#2ECC71',
            'WARNING': '#F39C12',
            'CRITICAL': '#E74C3C'
        }
        risk_color = color_map.get(level, '#2ECC71')
        self.risk_value_label.configure(text_color=risk_color)
        self.risk_level_label.configure(text=level, text_color=risk_color)
        
        self.well_status_label.configure(text=f'{level} - {score * 100:.1f}% risk')
        
        self._refresh_reports(well_id)
        self.show_chart(self.current_chart)
        self.set_status(f'{well_id}: {level} ({score * 100:.1f}%)', level.lower() if level != 'CRITICAL' else 'critical')
        
        if score >= RISK_THRESHOLD:
            self._raise_alert(well_id, score)

    def _refresh_reports(self, well_id):
        """Refresh all reports."""
        try:
            self._set_text(self.technical_text, reports.technical_report(well_id))
            self._set_text(self.stakeholder_text, reports.stakeholder_report(well_id))
        except Exception as error:
            self.set_status(f'Report generation failed: {error}', 'critical')

    def refresh_field_summary(self):
        """Refresh field summary report."""
        self.set_status('Scoring all wells…')
        self.update()
        try:
            self._set_text(self.field_text, reports.field_summary())
            self.set_status('Field overview updated.')
        except Exception as error:
            messagebox.showerror('Field summary failed', str(error))
            self.set_status(f'Field summary failed: {error}', 'critical')

    def _raise_alert(self, well_id, score):
        """Raise critical alert."""
        log_gui_event('auto_alert', f'Raising alert for {well_id} with score {score:.2f}')
        
        if well_id in self.alerted_wells:
            log_gui_event('alert_skipped', f'{well_id} already alerted this session')
            return
        
        self.alerted_wells.add(well_id)
        
        try:
            path = reports.save_report_to_file(
                reports.technical_report(well_id), f'{well_id}_alert.txt')
            result = emailer.send_alert(well_id, score, path)
            log_gui_event('alert_sent', f'Alert sent for {well_id}: {result}')
        except Exception as error:
            result = f'Alert could not be sent: {error}'
            log_system_error('alert_error', f'Failed to send alert for {well_id}: {error}', error)
        
        self._show_critical_alert(well_id, score, result)
        self.set_status(result, 'critical')

    def _show_critical_alert(self, well_id, score, result):
        """Show modern critical alert dialog."""
        if self.critical_alert_window:
            self.critical_alert_window.destroy()
        
        alert_window = ctk.CTkToplevel(self)
        alert_window.title("⚠️ CRITICAL ALERT")
        alert_window.geometry("500x450")
        
        # Main alert frame
        alert_frame = ctk.CTkFrame(alert_window, fg_color="#E74C3C")
        alert_frame.pack(fill="both", expand=True, padx=20, pady=20)
        
        # Warning header
        ctk.CTkLabel(
            alert_frame,
            text="⚠️ CRITICAL DANGER ALERT ⚠️",
            font=ctk.CTkFont(size=20, weight="bold"),
            text_color="white"
        ).pack(pady=(20, 15))
        
        # Well information
        ctk.CTkLabel(
            alert_frame,
            text=f"Well: {well_id}",
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color="white"
        ).pack(pady=5)
        
        ctk.CTkLabel(
            alert_frame,
            text=f"Failure Risk: {score * 100:.1f}%",
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color="white"
        ).pack(pady=5)
        
        # Result message
        result_label = ctk.CTkLabel(
            alert_frame,
            text=result,
            font=ctk.CTkFont(size=12),
            text_color="white",
            wraplength=400
        )
        result_label.pack(pady=15)
        
        # Acknowledge button
        acknowledge_btn = ctk.CTkButton(
            alert_frame,
            text="ACKNOWLEDGE",
            command=lambda: self._close_critical_alert(alert_window),
            height=45,
            fg_color="white",
            text_color="#E74C3C",
            hover_color="#BDC3C7",
            font=ctk.CTkFont(size=14, weight="bold")
        )
        acknowledge_btn.pack(pady=20)
        
        self.critical_alert_window = alert_window

    def _close_critical_alert(self, alert_window):
        """Close critical alert window."""
        alert_window.destroy()
        self.critical_alert_window = None

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


if __name__ == "__main__":
    app = ModernDashboardApp()
    app.mainloop()
