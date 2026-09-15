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
import tkinter as tk
from tkinter import messagebox, ttk

import charts
import emailer
import reports
from charts import ChartPanel
from config import COLORS, FONT_FAMILY, RISK_THRESHOLD, TECH_EMAIL
from data_loader import get_well_ids
from predict import get_risk_level, predict_failure_risk

# Fonts are grouped here so the whole window can be rescaled from one place.
FONT_TITLE = (FONT_FAMILY, 17, 'bold')
FONT_HEADING = (FONT_FAMILY, 11, 'bold')
FONT_BODY = (FONT_FAMILY, 10)
FONT_SMALL = (FONT_FAMILY, 9)
FONT_RISK = (FONT_FAMILY, 40, 'bold')
FONT_MONO = ('DejaVu Sans Mono', 9)

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
        self.geometry('1280x820')
        self.minsize(1080, 720)
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
            troughcolor=COLORS['bg'], bordercolor=COLORS['bg'],
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
            font=FONT_SMALL, relief='flat', cursor='hand2',
            bd=0, padx=12, pady=7,
        )

    # -------------------------------------------------------------- layout

    def _build_header(self):
        header = tk.Frame(self, bg=COLORS['panel'], height=64)
        header.pack(fill='x', side='top')
        header.pack_propagate(False)  # keep the fixed height

        tk.Label(
            header, text='DIGITAL OILFIELD MONITORING',
            bg=COLORS['panel'], fg=COLORS['text'], font=FONT_TITLE,
        ).pack(side='left', padx=20)

        tk.Label(
            header, text='Predictive Maintenance  •  Squad Charlie',
            bg=COLORS['panel'], fg=COLORS['muted'], font=FONT_SMALL,
        ).pack(side='left')

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

        main = tk.Frame(body, bg=COLORS['bg'])
        main.pack(side='left', fill='both', expand=True, padx=(12, 0))

        self._build_risk_card(main)
        self._build_chart_area(main)
        self._build_report_tabs(main)

    def _build_sidebar(self, parent):
        sidebar = self._card(parent, width=250)
        sidebar.pack(side='left', fill='y')
        sidebar.pack_propagate(False)

        tk.Label(
            sidebar, text='WELLS', bg=COLORS['panel'], fg=COLORS['muted'],
            font=FONT_HEADING,
        ).pack(anchor='w', padx=16, pady=(16, 8))

        # Listbox rather than a dropdown: an operator needs to see the whole
        # field at once, and selecting a well is the most frequent action.
        self.well_list = tk.Listbox(
            sidebar, bg=COLORS['bg'], fg=COLORS['text'],
            selectbackground=COLORS['accent'], selectforeground=COLORS['bg'],
            font=FONT_BODY, relief='flat', highlightthickness=0,
            activestyle='none', height=8,
        )
        self.well_list.pack(fill='x', padx=12)
        self.well_list.bind('<<ListboxSelect>>', self.on_well_selected)

        self._button(
            sidebar, 'RUN DIAGNOSTICS', self.run_diagnostics, primary=True,
        ).pack(fill='x', padx=12, pady=(16, 6))

        self._button(
            sidebar, 'Refresh field summary', self.refresh_field_summary,
        ).pack(fill='x', padx=12)

        tk.Frame(sidebar, bg=COLORS['border'], height=1).pack(
            fill='x', padx=12, pady=16)

        tk.Label(
            sidebar, text='EMAIL REPORT', bg=COLORS['panel'],
            fg=COLORS['muted'], font=FONT_HEADING,
        ).pack(anchor='w', padx=16)

        self.email_entry = tk.Entry(
            sidebar, bg=COLORS['bg'], fg=COLORS['text'], font=FONT_SMALL,
            relief='flat', insertbackground=COLORS['accent'],
            highlightbackground=COLORS['border'], highlightthickness=1,
        )
        self.email_entry.insert(0, TECH_EMAIL)
        self.email_entry.pack(fill='x', padx=12, pady=(8, 8), ipady=5)

        self._button(
            sidebar, 'Send technical report',
            lambda: self.send_report('Technical'),
        ).pack(fill='x', padx=12, pady=(0, 6))

        self._button(
            sidebar, 'Send stakeholder report',
            lambda: self.send_report('Stakeholder'),
        ).pack(fill='x', padx=12)

        tk.Label(
            sidebar,
            text=f'Auto-alert to\n{TECH_EMAIL}\nat risk ≥ {RISK_THRESHOLD:.0%}',
            bg=COLORS['panel'], fg=COLORS['muted'], font=FONT_SMALL,
            justify='left',
        ).pack(anchor='w', padx=16, pady=16)

    def _build_risk_card(self, parent):
        card = self._card(parent, height=140)
        card.pack(fill='x')
        card.pack_propagate(False)

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
        wrapper.pack(fill='both', expand=True, pady=12)

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
        notebook = ttk.Notebook(parent, height=230)
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
        except Exception as error:
            wells = []
            self.set_status(f'Database unavailable: {error}', 'critical')

        for well_id in wells:
            self.well_list.insert('end', well_id)

        if wells:
            self.well_list.selection_set(0)
            self.current_well = wells[0]
            self.show_chart(self.current_chart)
            self.set_status(f'{len(wells)} wells loaded. Select one and run diagnostics.')
        else:
            self.set_status(
                'No wells found. Run: python db_setup.py && python generate_data.py '
                '&& python load_csv.py && python train_model.py', 'warning')

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
        if well_id in self.alerted_wells:
            return
        self.alerted_wells.add(well_id)

        try:
            path = reports.save_report_to_file(
                reports.technical_report(well_id), f'{well_id}_alert.txt')
            result = emailer.send_alert(well_id, score, path)
        except Exception as error:
            result = f'Alert could not be sent: {error}'

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
