"""
emailer.py
Member 4 (Integration) | Thursday deliverable.

Sends maintenance alerts and reports over Gmail SMTP.

Email configuration (including credentials) is centralized in config.py,
which loads from environment variables (.env file). With no password set
the module falls back to DRY RUN — the message is printed instead of sent,
so the GUI can be demonstrated on a machine without mail credentials.

Gmail needs a 16-character App Password (Google account -> Security ->
2-Step Verification -> App passwords); a normal account password is
rejected by SMTP.
"""

import os
import smtplib
from email.message import EmailMessage
from email.utils import getaddresses

from config import SENDER_EMAIL, SMTP_HOST, SMTP_PORT, SMTP_USE_SSL, TECH_EMAIL, EMAIL_PASS
from logger import log_email_event, log_system_error


def get_password():
    """Return the SMTP app password, or None when the app is unconfigured."""
    return EMAIL_PASS


def is_configured() -> bool:
    """True when a real send is possible; the GUI uses this to warn the user."""
    return bool(get_password())

def test_smtp_connection() -> str:
    """Test SMTP connection and return detailed status."""
    password = get_password()
    if not password:
        return "EMAIL_PASS not configured"

    try:
        log_email_event('connection_test', f'Testing connection to {SMTP_HOST}:{SMTP_PORT}')

        if SMTP_USE_SSL:
            # Test SMTP_SSL connection
            with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, timeout=10) as server:
                server.set_debuglevel(1)
                log_email_event('connection_test', 'SMTP_SSL connection successful')
                return f"SMTP_SSL connection to {SMTP_HOST}:{SMTP_PORT} successful"
        else:
            # Test SMTP with STARTTLS
            with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=10) as server:
                server.set_debuglevel(1)
                server.starttls()
                log_email_event('connection_test', 'SMTP STARTTLS connection successful')
                return f"SMTP STARTTLS connection to {SMTP_HOST}:{SMTP_PORT} successful"

    except TimeoutError as error:
        error_msg = f"Connection timeout to {SMTP_HOST}:{SMTP_PORT}. Network/firewall may be blocking this port."
        log_email_event('connection_test_failed', error_msg, 'error')
        return error_msg
    except Exception as error:
        error_msg = f"Connection test failed: {error}"
        log_email_event('connection_test_failed', error_msg, 'error')
        return error_msg


def parse_recipients(to_email):
    """Normalize one or many recipients from comma/semicolon/newline input."""
    if isinstance(to_email, (list, tuple, set)):
        raw = ",".join(str(item) for item in to_email)
    else:
        raw = str(to_email or "")

    # Support values such as:
    # a@example.com,b@example.com
    # a@example.com; b@example.com
    # a@example.com\nb@example.com
    raw = raw.replace(";", ",").replace("\n", ",")
    addresses = [addr.strip() for _, addr in getaddresses([raw]) if addr.strip()]

    # Remove duplicates while preserving order.
    unique = list(dict.fromkeys(addresses))
    if not unique:
        raise ValueError("No valid recipient email address was provided.")

    invalid = [addr for addr in unique if "@" not in addr or addr.startswith("@") or addr.endswith("@")]
    if invalid:
        raise ValueError(f"Invalid recipient email address(es): {', '.join(invalid)}")

    return unique


def build_message(to_email, subject, body, attachment_path=None):
    """Assemble a MIME message, supporting one or multiple recipients."""
    recipients = parse_recipients(to_email)
    message = EmailMessage()
    message['From'] = SENDER_EMAIL
    message['To'] = ", ".join(recipients)
    message['Subject'] = subject
    message.set_content(body)

    if attachment_path:
        with open(attachment_path, 'rb') as f:
            data = f.read()
        # maintype/subtype must be given explicitly — EmailMessage does not
        # guess the type, and a wrong type makes clients hide the file.
        message.add_attachment(
            data, maintype='text', subtype='plain',
            filename=os.path.basename(attachment_path),
        )

    return message


def send_email(to_email, subject, body, attachment_path=None) -> str:
    """Send one message and return a human-readable status for the GUI.

    Any SMTP failure is turned into a returned string rather than an
    exception, because this is called from button handlers where an
    uncaught error would kill the event loop.
    """
    recipients = parse_recipients(to_email)
    log_email_event('send_attempt', f"To: {', '.join(recipients)}, Subject: {subject}")

    message = build_message(recipients, subject, body, attachment_path)
    password = get_password()

    if not password:
        # DRY RUN: no credentials configured. Echo the message so the demo
        # still shows exactly what would have been delivered.
        print('[DRY RUN] EMAIL_PASS not set — message not sent.')
        print(f'  To      : {to_email}')
        print(f'  Subject : {subject}')
        print(f'  Attach  : {attachment_path or "none"}')
        log_email_event('dry_run', f'Would email {to_email} (no EMAIL_PASS configured)', 'warning')
        return f'DRY RUN — no EMAIL_PASS configured. Would email {to_email}.'

    try:
        # Increased timeout and added connection debugging
        log_email_event('smtp_connect', f'Connecting to {SMTP_HOST}:{SMTP_PORT}')

        if SMTP_USE_SSL:
            # Use SMTP_SSL for port 465 (SSL connection)
            with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, timeout=30) as server:
                server.set_debuglevel(1)  # Enable SMTP debugging
                log_email_event('smtp_login', f'Authenticating as {SENDER_EMAIL}')
                server.login(SENDER_EMAIL, password)
                log_email_event('smtp_send', 'Sending message')
                server.send_message(message, from_addr=SENDER_EMAIL, to_addrs=recipients)
        else:
            # Use SMTP with STARTTLS for port 587 (TLS connection)
            with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=30) as server:
                server.set_debuglevel(1)  # Enable SMTP debugging
                log_email_event('smtp_starttls', 'Starting TLS encryption')
                server.starttls()  # upgrade to TLS before sending credentials
                log_email_event('smtp_login', f'Authenticating as {SENDER_EMAIL}')
                server.login(SENDER_EMAIL, password)
                log_email_event('smtp_send', 'Sending message')
                server.send_message(message, from_addr=SENDER_EMAIL, to_addrs=recipients)

        log_email_event('send_success', f'Email sent to {to_email}')
        return f'Email sent to {to_email}.'
    except smtplib.SMTPAuthenticationError as error:
        error_msg = 'Login rejected by Gmail. EMAIL_PASS must be a 16-character App Password, not the account password.'
        log_email_event('auth_failed', f'Authentication failed for {to_email}: {error}', 'error')
        log_system_error('smtp_auth_error', error_msg, error)
        return error_msg
    except smtplib.SMTPServerDisconnected as error:
        error_msg = f'SMTP connection failed: {error}. This may be due to network/firewall issues. Try checking your internet connection or using a different network.'
        log_email_event('connection_failed', f'Connection failed for {to_email}: {error}', 'error')
        log_system_error('smtp_connection_error', error_msg, error)
        return error_msg
    except TimeoutError as error:
        error_msg = f'SMTP connection timed out. This may be due to firewall/network issues blocking port {SMTP_PORT}. Try port 465 with SSL or check your network settings.'
        log_email_event('timeout', f'Connection timed out for {to_email}: {error}', 'error')
        log_system_error('smtp_timeout_error', error_msg, error)
        return error_msg
    except Exception as error:
        error_msg = f'Email failed: {error}'
        log_email_event('send_failed', f'Failed to send to {to_email}: {error}', 'error')
        log_system_error('smtp_error', error_msg, error)
        return error_msg


def send_alert(well_id, risk_score, report_path=None) -> str:
    """FR4: notify the technical team that a well crossed RISK_THRESHOLD."""
    subject = f'CRITICAL: Predicted pump failure on {well_id}'
    body = (
        f'Automated alert from the Digital Oilfield Monitoring System.\n\n'
        f'Well              : {well_id}\n'
        f'Predicted failure : {risk_score * 100:.1f}%\n\n'
        f'The model classifies this well as CRITICAL. Schedule an inspection '
        f'before the next production day.\n\n'
        f'-- Squad Charlie monitoring system'
    )
    return send_email(TECH_EMAIL, subject, body, report_path)


def send_report(to_email, well_id, report_kind, report_path) -> str:
    """Email a generated technical or stakeholder report as an attachment."""
    subject = f'{report_kind} report — {well_id}'
    body = (
        f'Attached is the {report_kind.lower()} report for {well_id}, '
        f'generated by the Digital Oilfield Monitoring System.'
    )
    return send_email(to_email, subject, body, report_path)


if __name__ == "__main__":
    # Prints the dry-run preview unless EMAIL_PASS is exported.
    print('Configured:', is_configured())
    print(send_alert('WELL-01', 0.91))
