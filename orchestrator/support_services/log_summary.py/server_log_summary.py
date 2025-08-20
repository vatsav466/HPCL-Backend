import urdhva_base
import re
import os
import asyncio
import traceback
import paramiko
from datetime import datetime, time, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo
import orchestrator.notification_manager.notification_factory


LOG_DIR = "/var/log/ceg_logs"
SLOTS = [
    (time(8, 0), "8AM"),
    (time(12, 0), "12PM"),
    (time(17, 0), "5PM")
]

DATETIME_PATTERN = re.compile(r'^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})')
ERROR_PATTERN = re.compile(r'(ERROR|logger\.error)', re.IGNORECASE)

log_blocks = []

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
        except Exception as e:
            print(f"Failed reading {log_file.name}: {e}")
            log_blocks.append(f"Log File   : {log_file.name}\nStatus     : FAIL\nError      : Could not read log file: {e}")

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

            except Exception as e:
                print(f"Error reading {file_name}: {e}")
                log_blocks.append(f"Log File   : {file_name}\nStatus     : FAIL\nError      : Could not read log file: {e}")

    finally:
        sftp.close()
        client.close()

async def send_mail():
    now_ist = datetime.now(ZoneInfo("Asia/Kolkata"))
    txt_path = "/tmp/log_summary.txt"
    with open(txt_path, "w") as f:
        f.write("\n\n".join(log_blocks))

    # Email
    formatted_time = now_ist.strftime('%d-%m-%Y %I:%M %p IST')
    html_body = f"""
    <html>
        <body>
        <p>Hello,</p>
        <p>Attached is the <b>log error summary</b></p>
        <br>
        Regards,<br>
        Log Monitoring System
        </body>
    </html>
    """

    for attempt in range(1, 4):
        try:
            print(f"Attempt {attempt} to send email with TXT attachment...")
            import orchestrator.notification_manager.notification_factory
            ins = await orchestrator.notification_manager.notification_factory.get_notification_module("email")
            print("Email module imported from path:", orchestrator.notification_manager.notification_factory.__file__)
            await ins.publish_message(
                subject=f"Production Servers Log Summary - {formatted_time}",
                recipients=[
                    "yesu.p@algofusiontech.com",
                    "sreedhar.maddipati@algofusiontech.com",
                    "venu@algofusiontech.com",
                    "shrihari.b@algofusiontech.com",
                    "santoshkumar.s@algofusiontech.com",
                    "keerthesrep@algofusiontech.com",
                    "moufikali@algofusiontech.com",
                    "bala@algofusiontech.com",
                    "manoj.m@algofusiontech.com",
                    "manohar.v@algofusiontech.com",
                    "vamsi.c@urdhvapay.com"
                ],
                html_content=True,
                body=html_body,
                attachments=[txt_path],
                force_send=True
            )
            print("Email sent successfully.")
            break
        except Exception as e:
            print(f"Attempt {attempt} - Failed to send email: {e}")
            if attempt == 3:
                print("All retries failed. Giving up.")

async def main():
    try:
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
        await send_mail()
    except Exception as e:
        print(f"Error in main: {e}")
        print(traceback.format_exc())


if __name__ == "__main__":
    asyncio.run(main())
