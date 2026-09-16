"""
app.py
Member 3 (GUI Developer) | Friday deliverable — the application entry point.

Tkinter control-room dashboard that wires every other module together:

    data_loader  -> well list and sensor history from SQLite
    predict      -> failure probability for the selected well
    charts       -> embedded Matplotlib time series
    reports      -> technical and stakeholder text reports
    emailer      -> automatic CRITICAL alerts and manual report sending

Layout:
    +--------------------------------------------------------------+
    | header: title + field status                                  |
    +-------------------+------------------------------------------+
    | sidebar           | risk card | chart toolbar + chart         |
    | well list         |-----------+--------------------------------|
    | run diagnostics   | notebook: technical / stakeholder / field |
    | email controls    |                                          |
    +-------------------+------------------------------------------+
    | status bar                                                    |
    +--------------------------------------------------------------+

Run with `python app.py` from the project root, after the data pipeline
(db_setup -> generate_data -> load_csv -> train_model) has been run once.
"""

import os
import sqlite3
import datetime
import csv
import tkinter as tk
from tkinter import messagebox, ttk

import charts
import emailer
import reports
from charts import ChartPanel
from config import COLORS, FONT_FAMILY, RISK_THRESHOLD, TECH_EMAIL, CSV_PATH, RAW_DATA_DIR, DB_PATH
from data_loader import get_well_ids
from predict import get_risk_level, predict_failure_risk
from load_csv import load_csv_into_db
import generate_data
from logger import log_gui_event, log_system_error, get_recent_logs, clear_logs

# Fonts are grouped here so the whole window can be rescaled from one place.
FONT_TITLE = (FONT_FAMILY, 17, 'bold')
FONT_HEADING = (FONT_FAMILY, 11, 'bold')
FONT_BODY = (FONT_FAMILY, 10)
FONT_SMALL = (FONT_FAMILY, 9)
FONT_RISK = (FONT_FAMILY, 40, 'bold')
FONT_MONO = ('DejaVu Sans Mono', 9)

# Sidebar-specific larger fonts for better readability
FONT_SIDEBAR_HEADING = (FONT_FAMILY, 13, 'bold')
FONT_SIDEBAR_BODY = (FONT_FAMILY, 12)
FONT_SIDEBAR_BUTTON = (FONT_FAMILY, 11)

# Risk level -> colour, so the card, the well list and the status bar all
# agree on what red means.
LEVEL_COLORS = {
    'NORMAL': COLORS['normal'],
    'WARNING': COLORS['warning'],
    'CRITICAL': COLORS['critical'],
}


class DashboardApp(tk.Tk):
    """The main window. One instance per process."""

    def __init__(self):
        super().__init__()
        self.title('Squad Charlie — Digital Oilfield Monitoring System')
        
        # Calculate window size based on screen dimensions
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        
        # Use 90% of screen size for better responsiveness, with reasonable minimums
        window_width = max(1000, int(screen_width * 0.9))
        window_height = max(700, int(screen_height * 0.9))
        
        self.geometry(f'{window_width}x{window_height}')
        self.minsize(900, 600)
        self.configure(bg=COLORS['bg'])

        # Selected well and the last computed score, shared by the chart,
        # report and email handlers so they never disagree about what is
        # currently on screen.
        self.current_well = None
        self.current_score = None
        self.current_chart = charts.CHART_TYPES[0]
        # Wells already alerted this session — without this, every click on
        # Run Diagnostics would re-send the same CRITICAL email.
        self.alerted_wells = set()

        log_gui_event('app_start', 'Application started')

        self._configure_styles()
        self._build_header()
        self._build_body()
        self._build_status_bar()

        self._load_wells()

    # ------------------------------------------------------------- styling

    def _configure_styles(self):
        """Theme the ttk widgets.

        ttk ignores plain bg/fg options, so notebooks, combos and
        scrollbars have to be restyled through a ttk.Style with the
        'clam' theme, which is the one that actually honours colours.
        """
        style = ttk.Style(self)
        style.theme_use('clam')

        style.configure('TNotebook', background=COLORS['bg'], borderwidth=0)
        style.configure(
            'TNotebook.Tab', background=COLORS['panel'], foreground=COLORS['muted'],
            padding=(18, 8), font=FONT_SMALL, borderwidth=0,
        )
        style.map(
            'TNotebook.Tab',
            background=[('selected', COLORS['bg'])],
            foreground=[('selected', COLORS['accent'])],
        )
        style.configure(
            'Vertical.TScrollbar', background=COLORS['panel'],
            troughcolor=COLORS['bg'], bordercolor=COLORS['border'],
            arrowcolor=COLORS['muted'],
        )
        style.configure(
            'Horizontal.TScrollbar', background=COLORS['panel'],
            troughcolor=COLORS['bg'], bordercolor=COLORS['border'],
            arrowcolor=COLORS['muted'],
        )

    def _card(self, parent, **kwargs):
        """A panel-coloured frame with a hairline border — the visual unit."""
        return tk.Frame(
            parent, bg=COLORS['panel'], highlightbackground=COLORS['border'],
            highlightthickness=1, **kwargs
        )

    def _button(self, parent, text, command, primary=False):
        """Flat coloured button; ttk buttons cannot be flat-styled reliably."""
        background = COLORS['accent'] if primary else COLORS['panel']
        foreground = COLORS['bg'] if primary else COLORS['text']
        return tk.Button(
            parent, text=text, command=command,
            bg=background, fg=foreground,
            activebackground=COLORS['accent_dark'] if primary else COLORS['border'],
            activeforeground=COLORS['bg'] if primary else COLORS['text'],
            font=FONT_SIDEBAR_BUTTON, relief='flat', cursor='hand2',
            bd=0, padx=12, pady=8,
        )

    # -------------------------------------------------------------- layout

    def _build_header(self):
        header = tk.Frame(self, bg=COLORS['panel'])
        header.pack(fill='x', side='top', pady=(0, 12))

        tk.Label(
            header, text='DIGITAL OILFIELD MONITORING',
            bg=COLORS['panel'], fg=COLORS['text'], font=FONT_TITLE,
        ).pack(side='left', padx=20)

        tk.Label(
            header, text='Predictive Maintenance  •  Squad Charlie',
            bg=COLORS['panel'], fg=COLORS['muted'], font=FONT_SMALL,
        ).pack(side='left')

        # Database status indicator
        self.db_state = tk.Label(
            header,
            text='DB: Ready',
            bg=COLORS['panel'],
            fg=COLORS['normal'],
            font=FONT_SMALL,
        )
        self.db_state.pack(side='right', padx=10)

        self.email_state = tk.Label(
            header,
            text='SMTP: live' if emailer.is_configured() else 'SMTP: dry run',
            bg=COLORS['panel'],
            fg=COLORS['normal'] if emailer.is_configured() else COLORS['warning'],
            font=FONT_SMALL,
        )
        self.email_state.pack(side='right', padx=20)

    def _build_body(self):
        body = tk.Frame(self, bg=COLORS['bg'])
        body.pack(fill='both', expand=True, padx=14, pady=12)

        self._build_sidebar(body)

        # Create scrollable main content area for smaller screens
        main_container = tk.Frame(body, bg=COLORS['bg'])
        main_container.pack(side='left', fill='both', expand=True)

        main_canvas = tk.Canvas(main_container, bg=COLORS['bg'], highlightthickness=0)
        main_scrollbar = ttk.Scrollbar(main_container, orient="vertical", command=main_canvas.yview)
        main_content = tk.Frame(main_canvas, bg=COLORS['bg'])

        main_content.bind(
            "<Configure>",
            lambda e: main_canvas.configure(scrollregion=main_canvas.bbox("all"))
        )

        main_canvas.create_window((0, 0), window=main_content, anchor="nw")
        main_canvas.configure(yscrollcommand=main_scrollbar.set)

        main_canvas.pack(side="left", fill="both", expand=True)
        main_scrollbar.pack(side="right", fill="y")

        # Make canvas expand to fill available space
        main_canvas.bind("<Configure>", lambda e: main_canvas.itemconfig("all", width=e.width))

        self._build_risk_card(main_content)
        self._build_chart_area(main_content)
        self._build_report_tabs(main_content)

    def _build_sidebar(self, parent):
        sidebar = self._card(parent, width=320)
        sidebar.pack(side='left', fill='y', padx=(0, 12))
        sidebar.pack_propagate(False)  # Keep minimum width
        
        # Create scrollable sidebar content with simpler approach
        sidebar_container = tk.Frame(sidebar, bg=COLORS['panel'])
        sidebar_container.pack(fill='both', expand=True)
        
        sidebar_canvas = tk.Canvas(sidebar_container, bg=COLORS['panel'], highlightthickness=0)
        sidebar_scrollbar = ttk.Scrollbar(sidebar_container, orient="vertical", command=sidebar_canvas.yview)
        scrollable_frame = tk.Frame(sidebar_canvas, bg=COLORS['panel'])

        scrollable_frame.bind(
            "<Configure>",
            lambda e: sidebar_canvas.configure(scrollregion=sidebar_canvas.bbox("all"))
        )

        sidebar_canvas.create_window((0, 0), window=scrollable_frame, anchor="nw", width=320)
        sidebar_canvas.configure(yscrollcommand=sidebar_scrollbar.set)

        # Always show scrollbar on the right
        sidebar_scrollbar.pack(side="right", fill="y")
        sidebar_canvas.pack(side="left", fill="both", expand=True)
        
        # Enable mouse wheel scrolling
        def _on_mousewheel(event):
            sidebar_canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        
        def _bind_to_mousewheel(event):
            sidebar_canvas.bind_all("<MouseWheel>", _on_mousewheel)
        
        def _unbind_from_mousewheel(event):
            sidebar_canvas.unbind_all("<MouseWheel>")
        
        sidebar_canvas.bind('<Enter>', _bind_to_mousewheel)
        sidebar_canvas.bind('<Leave>', _unbind_from_mousewheel)
        
        # Store references
        self.sidebar_canvas = sidebar_canvas
        self.sidebar_content = scrollable_frame

        # CSV Data Loading Section
        tk.Label(
            self.sidebar_content, text='DATA LOADING', bg=COLORS['panel'], fg=COLORS['muted'],
            font=FONT_SIDEBAR_HEADING,
        ).pack(anchor='w', padx=16, pady=(16, 10))

        # Generate CSV button
        self._button(
            self.sidebar_content, 'Generate CSV', self.generate_csv_file,
        ).pack(fill='x', padx=12, pady=(0, 8))

        # CSV file dropdown
        self.csv_var = tk.StringVar()
        self.csv_dropdown = ttk.Combobox(
            self.sidebar_content, textvariable=self.csv_var, state='readonly',
            font=FONT_SIDEBAR_BODY
        )
        self.csv_dropdown.pack(fill='x', padx=12, pady=(0, 8))
        self._refresh_csv_list()

        self._button(
            self.sidebar_content, 'Load Data', self.load_selected_csv, primary=True,
        ).pack(fill='x', padx=12, pady=(0, 8))

        self._button(
            self.sidebar_content, 'Refresh CSV list', self._refresh_csv_list,
        ).pack(fill='x', padx=12, pady=(0, 18))

        tk.Frame(self.sidebar_content, bg=COLORS['border'], height=1).pack(
            fill='x', padx=12, pady=18)

        # Database Management Section
        tk.Label(
            self.sidebar_content, text='DATABASE', bg=COLORS['panel'], fg=COLORS['muted'],
            font=FONT_SIDEBAR_HEADING,
        ).pack(anchor='w', padx=16, pady=(18, 10))

        self._button(
            self.sidebar_content, 'View DB Stats', self.show_database_stats,
        ).pack(fill='x', padx=12, pady=(0, 8))

        self._button(
            self.sidebar_content, 'Clear All Data', self.clear_database,
        ).pack(fill='x', padx=12, pady=(0, 8))

        self._button(
            self.sidebar_content, 'Export DB to CSV', self.export_database_to_csv,
        ).pack(fill='x', padx=12, pady=(0, 8))

        self._button(
            self.sidebar_content, 'Validate CSV', self.validate_selected_csv,
        ).pack(fill='x', padx=12, pady=(0, 18))

        tk.Frame(self.sidebar_content, bg=COLORS['border'], height=1).pack(
            fill='x', padx=12, pady=0)

        tk.Label(
            self.sidebar_content, text='WELLS', bg=COLORS['panel'], fg=COLORS['muted'],
            font=FONT_SIDEBAR_HEADING,
        ).pack(anchor='w', padx=16, pady=(18, 10))

        # Listbox rather than a dropdown: an operator needs to see the whole
        # field at once, and selecting a well is the most frequent action.
        self.well_list = tk.Listbox(
            self.sidebar_content, bg=COLORS['bg'], fg=COLORS['text'],
            selectbackground=COLORS['accent'], selectforeground=COLORS['bg'],
            font=FONT_SIDEBAR_BODY, relief='flat', highlightthickness=0,
            activestyle='none', height=8,
        )
        self.well_list.pack(fill='x', padx=12)
        self.well_list.bind('<<ListboxSelect>>', self.on_well_selected)

        self._button(
            self.sidebar_content, 'RUN DIAGNOSTICS', self.run_diagnostics, primary=True,
        ).pack(fill='x', padx=12, pady=(18, 8))

        self._button(
            self.sidebar_content, 'Refresh field summary', self.refresh_field_summary,
        ).pack(fill='x', padx=12, pady=(0, 14))

        tk.Label(
            self.sidebar_content, text='EMAIL REPORT', bg=COLORS['panel'],
            fg=COLORS['muted'], font=FONT_SIDEBAR_HEADING,
        ).pack(anchor='w', padx=16, pady=(10, 10))

        self.email_entry = tk.Entry(
            self.sidebar_content, bg=COLORS['bg'], fg=COLORS['text'], font=FONT_SIDEBAR_BODY,
            relief='flat', insertbackground=COLORS['accent'],
            highlightbackground=COLORS['border'], highlightthickness=1,
        )
        self.email_entry.insert(0, TECH_EMAIL)
        self.email_entry.pack(fill='x', padx=12, pady=(0, 10), ipady=6)

        self._button(
            self.sidebar_content, 'Send technical report',
            lambda: self.send_report('Technical'),
        ).pack(fill='x', padx=12, pady=(0, 8))

        self._button(
            self.sidebar_content, 'Send stakeholder report',
            lambda: self.send_report('Stakeholder'),
        ).pack(fill='x', padx=12, pady=(0, 8))

        self._button(
            self.sidebar_content, 'Test SMTP Connection',
            self.test_smtp_connection,
        ).pack(fill='x', padx=12, pady=(0, 8))

        tk.Label(
            self.sidebar_content,
            text=f'Auto-alert to\n{TECH_EMAIL}\nat risk ≥ {RISK_THRESHOLD:.0%}',
            bg=COLORS['panel'], fg=COLORS['muted'], font=FONT_SIDEBAR_BODY,
            justify='left',
        ).pack(anchor='w', padx=16, pady=(10, 18))

        tk.Frame(self.sidebar_content, bg=COLORS['border'], height=1).pack(
            fill='x', padx=12, pady=0)

        tk.Frame(self.sidebar_content, bg=COLORS['border'], height=1).pack(
            fill='x', padx=12, pady=0)

        # System Logs Section
        tk.Label(
            self.sidebar_content, text='SYSTEM LOGS', bg=COLORS['panel'],
            fg=COLORS['muted'], font=FONT_SIDEBAR_HEADING,
        ).pack(anchor='w', padx=16, pady=(18, 10))

        self._button(
            self.sidebar_content, 'View Recent Logs', self.show_system_logs,
        ).pack(fill='x', padx=12, pady=(0, 8))

        self._button(
            self.sidebar_content, 'Clear Logs', self.clear_system_logs,
        ).pack(fill='x', padx=12, pady=(0, 18))

    def _build_risk_card(self, parent):
        card = self._card(parent)
        card.pack(fill='x', pady=(0, 12))

        left = tk.Frame(card, bg=COLORS['panel'])
        left.pack(side='left', padx=24, pady=18)

        tk.Label(
            left, text='PREDICTED FAILURE RISK', bg=COLORS['panel'],
            fg=COLORS['muted'], font=FONT_SMALL,
        ).pack(anchor='w')

        self.risk_value = tk.Label(
            left, text='—', bg=COLORS['panel'], fg=COLORS['muted'],
            font=FONT_RISK,
        )
        self.risk_value.pack(anchor='w')

        right = tk.Frame(card, bg=COLORS['panel'])
        right.pack(side='left', padx=24, pady=24, fill='both', expand=True)

        self.risk_badge = tk.Label(
            right, text='NO WELL SELECTED', bg=COLORS['bg'],
            fg=COLORS['muted'], font=FONT_HEADING, padx=14, pady=6,
        )
        self.risk_badge.pack(anchor='w')

        self.risk_note = tk.Label(
            right, text='Select a well and press Run Diagnostics.',
            bg=COLORS['panel'], fg=COLORS['muted'], font=FONT_SMALL,
            justify='left', wraplength=520,
        )
        self.risk_note.pack(anchor='w', pady=(10, 0))

    def _build_chart_area(self, parent):
        wrapper = self._card(parent)
        wrapper.pack(fill='both', expand=True, pady=(0, 12))

        toolbar = tk.Frame(wrapper, bg=COLORS['panel'])
        toolbar.pack(fill='x', padx=12, pady=10)

        # One button per entry in charts.CHART_TYPES, so the toolbar stays in
        # step with the chart module.
        self.chart_buttons = {}
        for chart_type in charts.CHART_TYPES:
            button = self._button(
                toolbar, chart_type,
                lambda name=chart_type: self.show_chart(name),
            )
            button.pack(side='left', padx=(0, 6))
            self.chart_buttons[chart_type] = button

        self.chart_panel = ChartPanel(wrapper)
        self.chart_panel.pack(fill='both', expand=True, padx=12, pady=(0, 12))
        self._highlight_chart_button()

    def _build_report_tabs(self, parent):
        notebook = ttk.Notebook(parent)
        notebook.pack(fill='both', expand=True)

        self.technical_text = self._report_tab(notebook, 'Technical Report')
        self.stakeholder_text = self._report_tab(notebook, 'Stakeholder Report')
        self.field_text = self._report_tab(notebook, 'Field Overview')

    def _report_tab(self, notebook, label):
        """A scrollable read-only monospaced Text widget inside a tab."""
        frame = tk.Frame(notebook, bg=COLORS['bg'])
        notebook.add(frame, text=label)

        scrollbar = ttk.Scrollbar(frame, orient='vertical')
        scrollbar.pack(side='right', fill='y')

        text = tk.Text(
            frame, bg=COLORS['bg'], fg=COLORS['text'], font=FONT_MONO,
            relief='flat', wrap='none', padx=14, pady=10,
            yscrollcommand=scrollbar.set, insertbackground=COLORS['accent'],
        )
        text.pack(fill='both', expand=True)
        scrollbar.config(command=text.yview)
        return text

    def _build_status_bar(self):
        bar = tk.Frame(self, bg=COLORS['panel'], height=28)
        bar.pack(fill='x', side='bottom')
        bar.pack_propagate(False)

        self.status = tk.Label(
            bar, text='Ready.', bg=COLORS['panel'], fg=COLORS['muted'],
            font=FONT_SMALL, anchor='w',
        )
        self.status.pack(side='left', padx=16)

    # ------------------------------------------------------------- helpers

    def set_status(self, message, level='muted'):
        self.status.config(text=message, fg=COLORS.get(level, COLORS['muted']))

    def _set_text(self, widget, content):
        """Replace a read-only Text widget's content.

        Text widgets ignore writes while disabled, so the widget is enabled
        for the update and disabled again to keep it read-only.
        """
        widget.config(state='normal')
        widget.delete('1.0', 'end')
        widget.insert('1.0', content)
        widget.config(state='disabled')

    def _highlight_chart_button(self):
        """Show which chart is active by tinting its toolbar button."""
        for name, button in self.chart_buttons.items():
            active = name == self.current_chart
            button.config(
                bg=COLORS['accent'] if active else COLORS['panel'],
                fg=COLORS['bg'] if active else COLORS['text'],
            )

    def _load_wells(self):
        """Fill the sidebar from the database, degrading gracefully if empty."""
        try:
            wells = get_well_ids()
            # Update database status
            self.db_state.config(
                text=f'DB: {len(wells)} wells',
                fg=COLORS['normal'] if wells else COLORS['warning']
            )
        except Exception as error:
            wells = []
            self.set_status(f'Database unavailable: {error}', 'critical')
            self.db_state.config(text='DB: Error', fg=COLORS['critical'])

        self.well_list.delete(0, 'end')  # Clear existing list
        for well_id in wells:
            self.well_list.insert('end', well_id)

        if wells:
            self.well_list.selection_set(0)
            self.current_well = wells[0]
            self.show_chart(self.current_chart)
            self.set_status(f'{len(wells)} wells loaded. Select one and run diagnostics.')
        else:
            self.set_status(
                'No wells found. Load CSV data using the dropdown above or run: '
                'python db_setup.py && python generate_data.py && python load_csv.py && python train_model.py', 'warning')

    def _refresh_csv_list(self):
        """Scan for CSV files in raw folder and populate the dropdown."""
        csv_files = []
        # Check raw directory for CSV files (primary location)
        if os.path.exists(RAW_DATA_DIR):
            csv_files.extend([f for f in os.listdir(RAW_DATA_DIR) if f.endswith('.csv')])
        # Check current directory for CSV files (legacy support)
        if os.path.exists('.'):
            csv_files.extend([f for f in os.listdir('.') if f.endswith('.csv')])
        # Check data directory for CSV files (legacy support)
        if os.path.exists('data'):
            csv_files.extend([f'data/{f}' for f in os.listdir('data') if f.endswith('.csv')])

        if csv_files:
            self.csv_dropdown['values'] = csv_files
            if csv_files:
                self.csv_dropdown.set('')
        else:
            self.csv_dropdown['values'] = ['No CSV files found']
            self.csv_dropdown.set('No CSV files found')

    def generate_csv_file(self):
        """Generate a new CSV file with random month_year name in raw folder."""
        log_gui_event('generate_csv', 'User clicked Generate CSV button')
        self.set_status('Generating CSV file…')
        self.update_idletasks()

        try:
            csv_path = generate_data.generate_and_export_csv(use_raw_folder=True)
            log_gui_event('csv_generated', f'CSV file created at {csv_path}')
            self.set_status(f'CSV generated: {os.path.basename(csv_path)}')
            messagebox.showinfo('Success', f'CSV file generated:\n{csv_path}\n\nSelect it from the dropdown and click "Load Data" to load into database.')

            # Refresh the CSV list to show the new file
            self._refresh_csv_list()

        except Exception as error:
            log_system_error('csv_generation_error', f'Failed to generate CSV: {error}', error)
            messagebox.showerror('Generation failed', f'Failed to generate CSV: {error}')
            self.set_status(f'CSV generation failed: {error}', 'critical')

    def load_selected_csv(self):
        """Load the selected CSV file into the database."""
        csv_file = self.csv_var.get()
        if not csv_file or csv_file == 'No CSV files found':
            messagebox.showinfo('No CSV selected', 'Please select a CSV file from the dropdown.')
            return

        log_gui_event('load_csv', f'User selected CSV: {csv_file}')
        self.set_status(f'Loading {csv_file} into database…')
        self.update_idletasks()

        try:
            # Handle both relative paths and simple filenames
            if not os.path.exists(csv_file):
                # Try in raw directory first
                csv_file = os.path.join(RAW_DATA_DIR, csv_file)
            if not os.path.exists(csv_file):
                # Try in data directory (legacy)
                csv_file = f'data/{csv_file}'

            if not os.path.exists(csv_file):
                messagebox.showerror('File not found', f'CSV file not found: {csv_file}')
                self.set_status('CSV file not found', 'critical')
                return

            inserted = load_csv_into_db(csv_file)
            log_gui_event('csv_loaded', f'Loaded {inserted} rows from {csv_file}')
            self.set_status(f'Loaded {inserted} rows from {csv_file}')
            messagebox.showinfo('Success', f'Loaded {inserted} rows from {csv_file} into database.')

            # Refresh the well list to show newly loaded wells
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

            # Get total rows
            cursor.execute("SELECT COUNT(*) FROM production_data")
            total_rows = cursor.fetchone()[0]

            # Get unique wells
            cursor.execute("SELECT COUNT(DISTINCT Well_ID) FROM production_data")
            unique_wells = cursor.fetchone()[0]

            # Get date range
            cursor.execute("SELECT MIN(Date), MAX(Date) FROM production_data")
            date_range = cursor.fetchone()

            # Get failure count
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
        """Clear all data from the database with confirmation."""
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

            # Refresh the well list
            self._load_wells()

        except Exception as error:
            messagebox.showerror('Error', f'Failed to clear database: {error}')
            self.set_status('Database clear failed', 'critical')

    def export_database_to_csv(self):
        """Export current database contents to a CSV file."""
        try:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()

            # Get all data
            cursor.execute("SELECT * FROM production_data ORDER BY Well_ID, Date")
            rows = cursor.fetchall()

            # Get column names
            cursor.execute("PRAGMA table_info(production_data)")
            columns = [info[1] for info in cursor.fetchall()]

            conn.close()

            if not rows:
                messagebox.showinfo('No Data', 'Database is empty. Nothing to export.')
                return

            # Generate filename with timestamp
            timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
            export_path = os.path.join(RAW_DATA_DIR, f'db_export_{timestamp}.csv')

            # Ensure raw directory exists
            os.makedirs(RAW_DATA_DIR, exist_ok=True)

            # Write to CSV
            with open(export_path, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(columns)
                writer.writerows(rows)

            messagebox.showinfo('Export Success', f'Exported {len(rows)} records to:\n{export_path}')
            self.set_status(f'Database exported to {os.path.basename(export_path)}')

            # Refresh CSV list to show the exported file
            self._refresh_csv_list()

        except Exception as error:
            messagebox.showerror('Export Failed', f'Failed to export database: {error}')
            self.set_status('Database export failed', 'critical')

    def validate_selected_csv(self):
        """Validate the selected CSV file structure and content."""
        csv_file = self.csv_var.get()
        if not csv_file or csv_file == 'No CSV files found':
            messagebox.showinfo('No CSV selected', 'Please select a CSV file from the dropdown.')
            return

        self.set_status(f'Validating {csv_file}…')
        self.update_idletasks()

        try:
            # Handle both relative paths and simple filenames
            actual_csv_file = csv_file
            if not os.path.exists(actual_csv_file):
                actual_csv_file = os.path.join(RAW_DATA_DIR, csv_file)
            if not os.path.exists(actual_csv_file):
                actual_csv_file = f'data/{csv_file}'

            if not os.path.exists(actual_csv_file):
                messagebox.showerror('File not found', f'CSV file not found: {csv_file}')
                self.set_status('CSV file not found', 'critical')
                return

            # Validate CSV structure
            with open(actual_csv_file, 'r') as f:
                reader = csv.reader(f)
                header = next(reader)  # Get header row

                expected_columns = ['Well_ID', 'Date', 'Oil_Rate', 'Water_Cut', 'Pressure', 'Temperature', 'Pump_Status']

                if header != expected_columns:
                    messagebox.showwarning(
                        'CSV Structure Warning',
                        f'CSV header does not match expected format.\n\n'
                        f'Expected: {expected_columns}\n'
                        f'Found: {header}\n\n'
                        f'The file may still load, but could cause issues.'
                    )

                # Count rows
                row_count = sum(1 for row in reader) + 1  # +1 for header

                # Check for duplicate wells/dates (sample check)
                f.seek(0)
                next(reader)  # Skip header
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

    def show_system_logs(self):
        """Display recent system logs in a dialog."""
        log_gui_event('view_logs', 'User requested to view system logs')

        try:
            recent_logs = get_recent_logs(100)

            # Create a log viewer window
            log_window = tk.Toplevel(self)
            log_window.title('System Logs')
            log_window.geometry('800x600')
            log_window.configure(bg=COLORS['bg'])

            # Add scrollbar
            scrollbar = ttk.Scrollbar(log_window)
            scrollbar.pack(side='right', fill='y')

            # Add text widget for logs
            log_text = tk.Text(
                log_window, bg=COLORS['bg'], fg=COLORS['text'],
                font=FONT_MONO, wrap='none', padx=10, pady=10,
                yscrollcommand=scrollbar.set
            )
            log_text.pack(fill='both', expand=True)
            scrollbar.config(command=log_text.yview)

            # Insert logs
            for log_line in recent_logs:
                log_text.insert('end', log_line)

            # Make text read-only
            log_text.config(state='disabled')

            # Add close button
            close_button = self._button(
                log_window, 'Close', log_window.destroy,
            )
            close_button.pack(pady=10)

            self.set_status('System logs displayed')

        except Exception as error:
            log_system_error('log_view_error', f'Failed to display logs: {error}', error)
            messagebox.showerror('Error', f'Failed to display logs: {error}')
            self.set_status('Failed to display logs', 'critical')

    def clear_system_logs(self):
        """Clear the system log file with confirmation."""
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
        """Test the SMTP connection and display results."""
        log_gui_event('test_smtp', 'User requested SMTP connection test')
        self.set_status('Testing SMTP connection…')
        self.update_idletasks()

        try:
            result = emailer.test_smtp_connection()
            messagebox.showinfo('SMTP Connection Test', result)
            self.set_status('SMTP connection test completed')
        except Exception as error:
            log_system_error('smtp_test_error', f'SMTP test failed: {error}', error)
            messagebox.showerror('Test Failed', f'SMTP connection test failed: {error}')
            self.set_status('SMTP test failed', 'critical')

    # ------------------------------------------------------------ handlers

    def on_well_selected(self, _event=None):
        """Selecting a well redraws the chart but does not re-score it.

        Scoring is left to Run Diagnostics so that browsing the field never
        triggers an automatic alert email.
        """
        selection = self.well_list.curselection()
        if not selection:
            return
        self.current_well = self.well_list.get(selection[0])
        self.current_score = None
        self.risk_value.config(text='—', fg=COLORS['muted'])
        self.risk_badge.config(text='NOT DIAGNOSED', fg=COLORS['muted'])
        self.risk_note.config(text=f'{self.current_well} selected. '
                                   f'Press Run Diagnostics to score it.')
        self.show_chart(self.current_chart)

    def show_chart(self, chart_type):
        """Redraw the chart area; errors become a status line, not a crash."""
        self.current_chart = chart_type
        self._highlight_chart_button()

        if not self.current_well:
            return
        try:
            self.chart_panel.plot(chart_type, self.current_well)
            self.set_status(f'{chart_type} chart — {self.current_well}')
        except Exception as error:
            self.set_status(f'Chart failed: {error}', 'critical')

    def run_diagnostics(self):
        """Score the selected well, refresh both reports, alert if CRITICAL."""
        if not self.current_well:
            messagebox.showinfo('No well selected', 'Select a well first.')
            return

        well_id = self.current_well
        self.set_status(f'Scoring {well_id}…')
        self.update_idletasks()  # paint the status line before the slow work

        try:
            score = predict_failure_risk(well_id)
        except FileNotFoundError as error:
            # Raised when models/pump_failure_model.pkl is missing — the most
            # common first-run problem, so give the exact command to fix it.
            messagebox.showwarning(
                'Model not trained',
                f'{error}\n\nRun this once from the project root:\n'
                f'    python train_model.py')
            self.set_status('No trained model.', 'warning')
            return
        except Exception as error:
            messagebox.showerror('Diagnostics failed', str(error))
            self.set_status(f'Diagnostics failed: {error}', 'critical')
            return

        self.current_score = score
        level = get_risk_level(score)
        colour = LEVEL_COLORS[level]

        self.risk_value.config(text=f'{score * 100:.0f}%', fg=colour)
        self.risk_badge.config(text=level, fg=colour)
        self.risk_note.config(
            text=f'{well_id} scored {score * 100:.1f}% failure probability '
                 f'from its latest reading.', fg=COLORS['text'])

        self._refresh_reports(well_id)
        self.show_chart(self.current_chart)
        self.set_status(f'{well_id}: {level} ({score * 100:.1f}%)',
                        level.lower() if level != 'CRITICAL' else 'critical')

        if score >= RISK_THRESHOLD:
            self._raise_alert(well_id, score)

    def _refresh_reports(self, well_id):
        try:
            self._set_text(self.technical_text, reports.technical_report(well_id))
            self._set_text(self.stakeholder_text, reports.stakeholder_report(well_id))
        except Exception as error:
            self.set_status(f'Report generation failed: {error}', 'critical')

    def refresh_field_summary(self):
        """Score every well and fill the Field Overview tab."""
        self.set_status('Scoring all wells…')
        self.update_idletasks()
        try:
            self._set_text(self.field_text, reports.field_summary())
            self.set_status('Field overview updated.')
        except Exception as error:
            messagebox.showerror('Field summary failed', str(error))
            self.set_status(f'Field summary failed: {error}', 'critical')

    def _raise_alert(self, well_id, score):
        """FR4: email the technical team once per well per session."""
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

        messagebox.showwarning(
            'CRITICAL risk detected',
            f'{well_id} is at {score * 100:.1f}% failure risk.\n\n{result}')
        self.set_status(result, 'critical')

    def send_report(self, kind):
        """Save the chosen report to reports/ and email it to the entered address."""
        if not self.current_well:
            messagebox.showinfo('No well selected', 'Select a well first.')
            return

        to_email = self.email_entry.get().strip()
        if '@' not in to_email:
            messagebox.showwarning('Invalid address',
                                   'Enter a valid recipient email address.')
            return

        well_id = self.current_well
        builder = (reports.technical_report if kind == 'Technical'
                   else reports.stakeholder_report)

        self.set_status(f'Sending {kind.lower()} report for {well_id}…')
        self.update_idletasks()

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
    DashboardApp().mainloop()
