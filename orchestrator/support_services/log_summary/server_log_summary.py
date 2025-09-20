import urdhva_base
import re
import os
import asyncio
import traceback
import paramiko
import csv
import psycopg2
from psycopg2 import Error
from datetime import datetime, time, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo
import orchestrator.notification_manager.notification_factory
import orchestrator.dbconnector.credential_loader as credential_loader


creds = credential_loader.get_credentials("HPCL_DEV")

LOG_DIR = "/var/log/ceg_logs"
SLOTS = [
    (time(8, 0), "8AM"),
    (time(12, 0), "12PM"),
    (time(17, 0), "5PM")
]

DATETIME_PATTERN = re.compile(r'^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})')
ERROR_PATTERN = re.compile(r'(ERROR|logger\.error)', re.IGNORECASE)

# Database configuration for dev 162 (PostgreSQL) - NEW ADDITION
DB_CONFIG = {
    'host': creds['host'],
    'database': creds['database'],
    'user': creds['user'],
    'password': creds['password'],
    'port': creds['port']
}

log_blocks = []
csv_data = []  # List to store CSV data

# NEW FUNCTION - Get current slot label
def get_current_slot_label():
    """Get the current slot label based on current time"""
    now_ist = datetime.now(ZoneInfo("Asia/Kolkata"))
    current_time = now_ist.time()

    # Determine which slot we're currently in
    if current_time >= time(17, 0) or current_time < time(8, 0):
        return "5PM"
    elif current_time >= time(12, 0):
        return "5PM"
    elif current_time >= time(8, 0):
        return "12PM"
    else:
        return "8AM"

# NEW FUNCTION - Clean up old data (older than 7 days)
async def cleanup_old_data():
    """Remove data older than 7 days from database"""
    connection = None
    cursor = None
    try:
        print("Cleaning up data older than 7 days...")
        connection = psycopg2.connect(**DB_CONFIG)
        cursor = connection.cursor()

        # Delete records older than 7 days
        cleanup_query = """
        DELETE FROM log_summary
        WHERE created_at < (CURRENT_TIMESTAMP - INTERVAL '7 days')
        """
        cursor.execute(cleanup_query)
        deleted_count = cursor.rowcount
        connection.commit()

        if deleted_count > 0:
            print(f"Deleted {deleted_count} old records from database")
        else:
            print("No old records found to delete")

    except Exception as e:
        print(f"Error cleaning up old data: {e}")
        if connection:
            connection.rollback()
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()

# MODIFIED FUNCTION - Insert CSV data to database
async def insert_csv_to_database():
    """Insert CSV data to PostgreSQL database"""
    if not csv_data:
        print("No data to insert into database")
        return

    connection = None
    cursor = None
    try:
        print("Connecting to PostgreSQL database...")
        connection = psycopg2.connect(**DB_CONFIG)
        cursor = connection.cursor()

        # Create table if it doesn't exist
        create_table_query = """
        CREATE TABLE IF NOT EXISTS log_summary (
            id SERIAL PRIMARY KEY,
            server VARCHAR(10) NOT NULL,
            log_file VARCHAR(255) NOT NULL,
            status VARCHAR(10) NOT NULL,
            errors TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """
        cursor.execute(create_table_query)

        # Insert new data
        insert_query = """
        INSERT INTO log_summary (server, log_file, status, errors)
        VALUES (%s, %s, %s, %s)
        """

        # Prepare data for insertion
        insert_data = []
        for record in csv_data:
            insert_data.append((
                record['Server'],
                record['Log File'],
                record['Status'],
                record['errors']
            ))

        # Execute batch insert
        cursor.executemany(insert_query, insert_data)
        connection.commit()

        current_slot = get_current_slot_label()
        print(f"Successfully inserted {len(insert_data)} records into log_summary table for {current_slot} slot")

    except Exception as e:
        print(f"Error inserting data to database: {e}")
        if connection:
            connection.rollback()
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()

async def log_summary():
    print("Reading logs from local server...")

    now_ist = datetime.now(ZoneInfo("Asia/Kolkata"))
    today = now_ist.date()

    # Determine slot start time
    current_slot_start = None
    current_slot_label = ""
    for i in range(len(SLOTS)):
        if now_ist.time() < SLOTS[i][0]:
            slot_time, label = SLOTS[i]
            current_slot_start = datetime.combine(today, SLOTS[i-1][0], tzinfo=ZoneInfo("Asia/Kolkata")) if i > 0 else datetime.combine(today - timedelta(days=1), SLOTS[-1][0], tzinfo=ZoneInfo("Asia/Kolkata"))
            current_slot_label = label
            break
    else:
        slot_time, label = SLOTS[-1]
        current_slot_start = datetime.combine(today, slot_time, tzinfo=ZoneInfo("Asia/Kolkata"))
        current_slot_label = label

    # Special handling for 8AM slot: go back to yesterday 5PM
    if current_slot_label == "8AM":
        current_slot_start = datetime.combine(today - timedelta(days=1), time(17, 0), tzinfo=ZoneInfo("Asia/Kolkata"))

    slot_start_utc = current_slot_start.astimezone(timezone.utc)

    for log_file in Path(LOG_DIR).glob("*.log"):
        errors = []
        try:
            with open(log_file, "r", encoding="utf-8", errors="ignore") as file:
                for line in file:
                    match = DATETIME_PATTERN.match(line)
                    if match:
                        try:
                            log_time = datetime.strptime(match.group(1), "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
                            if log_time >= slot_start_utc and ERROR_PATTERN.search(line):
                                errors.append(line.strip())
                        except Exception:
                            continue

            status = "FAIL" if errors else "PASS"
            block = f"Server     : 211\n"
            block += f"Log File   : {log_file.name}\nStatus     : {status}"
            block += "\n" + "\n".join(errors) if errors else "\n(No errors found)"
            log_blocks.append(block)

            # Add to CSV data with deduplicated errors
            if errors:
                # Deduplicate similar errors for CSV
                unique_errors = []
                seen_patterns = set()

                for error in errors:
                    # Extract error pattern by removing timestamp and specific details
                    # Keep the core error message structure
                    error_pattern = re.sub(r'\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3}', 'TIMESTAMP', error)
                    error_pattern = re.sub(r'\d+', 'NUMBER', error_pattern)

                    if error_pattern not in seen_patterns:
                        seen_patterns.add(error_pattern)
                        unique_errors.append(error)

                error_text = "\n".join(unique_errors)
            else:
                error_text = "(No errors found)"

            csv_data.append({
                'Server': '211',
                'Log File': log_file.name,
                'Status': status,
                'errors': error_text
            })

        except Exception as e:
            print(f"Failed reading {log_file.name}: {e}")
            error_msg = f"Could not read log file: {e}"
            log_blocks.append(f"Log File   : {log_file.name}\nStatus     : FAIL\nError      : {error_msg}")
            csv_data.append({
                'Server': '211',
                'Log File': log_file.name,
                'Status': 'FAIL',
                'errors': error_msg
            })

async def monitor_remote_logs(server):
    print("Monitoring all logs on remote server...")
    REMOTE_HOST = f"10.90.38.{server}"
    REMOTE_USER = urdhva_base.settings.novex_user
    REMOTE_PASSWORD = urdhva_base.settings.novex_password
    REMOTE_LOG_DIR = "/var/log/ceg_logs"

    now_ist = datetime.now(ZoneInfo("Asia/Kolkata"))
    today = now_ist.date()

    # Determine slot start time
    current_slot_start = None
    current_slot_label = ""
    for i in range(len(SLOTS)):
        if now_ist.time() < SLOTS[i][0]:
            slot_time, label = SLOTS[i]
            current_slot_start = datetime.combine(today, SLOTS[i-1][0], tzinfo=ZoneInfo("Asia/Kolkata")) if i > 0 else datetime.combine(today - timedelta(days=1), SLOTS[-1][0], tzinfo=ZoneInfo("Asia/Kolkata"))
            current_slot_label = label
            break
    else:
        slot_time, label = SLOTS[-1]
        current_slot_start = datetime.combine(today, slot_time, tzinfo=ZoneInfo("Asia/Kolkata"))
        current_slot_label = label

    # Special handling for 8AM slot: go back to yesterday 5PM
    if current_slot_label == "8AM":
        current_slot_start = datetime.combine(today - timedelta(days=1), time(17, 0), tzinfo=ZoneInfo("Asia/Kolkata"))

    slot_start_utc = current_slot_start.astimezone(timezone.utc)

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(REMOTE_HOST, username=REMOTE_USER, password=REMOTE_PASSWORD)
    sftp = client.open_sftp()
    try:
        for file_attr in sftp.listdir_attr(REMOTE_LOG_DIR):
            file_name = file_attr.filename
            if not file_name.endswith(".log"):
                continue

            remote_path = f"{REMOTE_LOG_DIR}/{file_name}"

            try:
                file_obj = sftp.file(remote_path, "r")
                content = file_obj.read()

                if isinstance(content, bytes):
                    lines = content.decode(errors="ignore").splitlines()
                else:
                    lines = content.splitlines()

                errors = []
                for line in lines:
                    match = DATETIME_PATTERN.match(line)
                    if match:
                        try:
                            log_time = datetime.strptime(match.group(1), "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
                            if log_time >= slot_start_utc and ERROR_PATTERN.search(line):
                                errors.append(line.strip())
                        except Exception:
                            continue

                status = "FAIL" if errors else "PASS"
                block = f"Server     : {server}\n"
                block += f"Log File   : {file_name}\nStatus     : {status}"
                block += "\n" + "\n".join(errors) if errors else "\n(No errors found)"
                log_blocks.append(block)

                # Add to CSV data with deduplicated errors
                if errors:
                    # Deduplicate similar errors for CSV
                    unique_errors = []
                    seen_patterns = set()

                    for error in errors:
                        # Extract error pattern by removing timestamp and specific details
                        # Keep the core error message structure
                        error_pattern = re.sub(r'\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3}', 'TIMESTAMP', error)
                        error_pattern = re.sub(r'\d+', 'NUMBER', error_pattern)

                        if error_pattern not in seen_patterns:
                            seen_patterns.add(error_pattern)
                            unique_errors.append(error)

                    error_text = "\n".join(unique_errors)
                else:
                    error_text = "(No errors found)"

                csv_data.append({
                    'Server': server,
                    'Log File': file_name,
                    'Status': status,
                    'errors': error_text
                })

            except Exception as e:
                print(f"Error reading {file_name}: {e}")
                error_msg = f"Could not read log file: {e}"
                log_blocks.append(f"Log File   : {file_name}\nStatus     : FAIL\nError      : {error_msg}")
                csv_data.append({
                    'Server': server,
                    'Log File': file_name,
                    'Status': 'FAIL',
                    'errors': error_msg
                })

    finally:
        sftp.close()
        client.close()

async def send_mail():
    now_ist = datetime.now(ZoneInfo("Asia/Kolkata"))
    txt_path = "/tmp/log_summary.txt"
    csv_path = "/tmp/log_summary.csv"

    # Write TXT file
    with open(txt_path, "w") as f:
        f.write("\n\n".join(log_blocks))

    # Write CSV file
    with open(csv_path, "w", newline='', encoding='utf-8') as csvfile:
        fieldnames = ['Server', 'Log File', 'Status', 'errors']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(csv_data)

    # Email
    formatted_time = now_ist.strftime('%d-%m-%Y %I:%M %p IST')
    html_body = f"""
    <html>
        <body>
        <p>Hello,</p>
        <p>Attached is the <b>log error summary</b> in both TXT and CSV formats</p>
        <br>
        Regards,<br>
        Log Monitoring System
        </body>
    </html>
    """

    for attempt in range(1, 4):
        try:
            print(f"Attempt {attempt} to send email with TXT and CSV attachments...")
            import orchestrator.notification_manager.notification_factory
            ins = await orchestrator.notification_manager.notification_factory.get_notification_module("email")
            print("Email module imported from path:", orchestrator.notification_manager.notification_factory.__file__)
            await ins.publish_message(
                subject=f"Production Servers Log Summary - {formatted_time}",
                recipients=[
                    "sreedhar.maddipati@algofusiontech.com",
                    "bala@algofusiontech.com",
                    "venu@algofusiontech.com",
                    "moufikali@algofusiontech.com",
                    "shrihari.b@algofusiontech.com",
                    "keerthesrep@algofusiontech.com",
                    "vamsi.c@urdhvapay.com",
                    "yesu.p@algofusiontech.com",
                    "manohar.v@algofusiontech.com",
                    "mohith.p@algofusiontech.com",
                    "pawann.k@algofusiontech.com"
                ],
                html_content=True,
                body=html_body,
                attachments=[txt_path, csv_path],  # Both TXT and CSV attachments
                force_send=True
            )
            print("Email sent successfully with both TXT and CSV attachments.")
            break
        except Exception as e:
            print(f"Attempt {attempt} - Failed to send email: {e}")
            if attempt == 3:
                print("All retries failed. Giving up.")

async def main():
    try:
        # Clean up data older than 7 days
        await cleanup_old_data()

        servers = {
            '211': 'local',
            '212': 'remote',
            '217': 'remote',
            '218': 'remote',
            '219': 'remote',
            '222': 'remote'
        }
        for server, server_type in servers.items():
            print(f"Processing server {server} of type {server_type}")
            if server_type == 'local':
                await log_summary()
            else:
                await monitor_remote_logs(server)

        # Insert CSV data to database
        await insert_csv_to_database()

        await send_mail()
    except Exception as e:
        print(f"Error in main: {e}")
        print(traceback.format_exc())


if __name__ == "__main__":
    asyncio.run(main())
