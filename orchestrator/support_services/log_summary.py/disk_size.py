import urdhva_base
import pandas as pd
import asyncio
import pytz
import subprocess
import paramiko
from datetime import datetime
import orchestrator.notification_manager.notification_factory


# List of servers to check, adjust IP range as needed
servers = [f"10.90.38.{i}" for i in range(211, 223)]
ssh_username = urdhva_base.settings.novex_user
ssh_password = urdhva_base.settings.novex_password  # confirm if this password is correct otherwise update


def fetch_disk_usage(host):
    try:
        if host == "10.90.38.211":
            # Local execution for this host
            result = subprocess.run(['df', '-h'], capture_output=True, text=True, check=True)
            output = result.stdout
        else:
            # Remote execution via SSH
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            ssh.connect(host, username=ssh_username, password=ssh_password, timeout=10)
            stdin, stdout, stderr = ssh.exec_command("df -h")
            output = stdout.read().decode()
            ssh.close()

        lines = output.strip().split('\n')
        columns = ['Filesystem', 'Size', 'Used', 'Avail', 'Use%', 'Mounted on']
        data = []

        # Parse lines while handling multiple words in Filesystem column
        for line in lines[1:]:
            parts = line.split()
            if len(parts) >= 6:
                fs = ' '.join(parts[0:len(parts)-5])
                size, used, avail, use_percent, mount = parts[-5:]
                data.append([fs, size, used, avail, use_percent, mount])

        df = pd.DataFrame(data, columns=columns)
        return host, df

    except Exception as e:
        # Return error info in a DataFrame if exception occurs
        return host, pd.DataFrame({"Error": [str(e)]})


def parse_usage(usage_str):
    """Convert Use% string value like '77%' to integer 77 safely."""
    try:
        return int(str(usage_str).strip().replace('%', ''))
    except Exception:
        return 0


def filter_high_usage(df, threshold=60):
    """
    Return rows with 'Use%' greater than threshold.
    If no 'Use%' column or empty df, returns empty DataFrame.
    """
    if "Use%" not in df.columns:
        return pd.DataFrame()  # no Use% column means no data to filter
    usage_series = df['Use%'].apply(parse_usage)
    filtered_df = df[usage_series > threshold].reset_index(drop=True)
    return filtered_df


async def send_disk_report(all_reports):
    ist = pytz.timezone('Asia/Kolkata')
    now_ist = datetime.now(ist).strftime('%d-%m-%Y %I:%M %p IST')

    html_tables = ""
    for server, df in all_reports.items():
        filtered_df = filter_high_usage(df, threshold=60)

        # Skip servers with no partitions above threshold
        if filtered_df.empty:
            continue

        try:
            # No special styling applied now, just plain table
            html_table = filtered_df.to_html(index=False, border=0, justify='center', classes='disk-table', escape=False)
        except Exception:
            # Fallback to something very basic
            html_table = filtered_df.to_html(index=False)

        html_tables += f"<h3>Server: {server}</h3>{html_table}<br><br>"

    if not html_tables:
        html_tables = "<p>No disk partitions with usage above 60% found on monitored servers.</p>"

    html_body = f"""
    <html>
    <head>
        <style>
            .disk-table {{
                font-family: Arial, sans-serif;
                border-collapse: collapse;
                width: 100%;
            }}
            .disk-table th, .disk-table td {{
                border: 1px solid #dddddd;
                text-align: left;
                padding: 8px;
            }}
            .disk-table th {{
                background-color: #d32f2f;  /* red header for high alert */
                color: white;
            }}
        </style>
    </head>
    <body>
        <p>Hello,</p>
        <p>Below is the <b>disk usage report (only partitions &gt; 60%)</b> from all monitored servers.</p>
        <p>Generated at: <b>{now_ist}</b></p>
        <br>
        {html_tables}
        <br><br>
        Regards,<br>
        Disk Usage Monitor
    </body>
    </html>
    """

    for attempt in range(1, 4):
        try:
            ins = await orchestrator.notification_manager.notification_factory.get_notification_module("email")
            await ins.publish_message(
                subject=f"Disk Usage Report - {now_ist}",
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
                force_send=True
            )
            print("Email sent successfully.")
            break
        except Exception as e:
            print(f"Attempt {attempt} - Failed to send email: {e}")
            if attempt == 3:
                print("All retries failed. Giving up.")


async def main():
    all_reports = {}
    for server in servers:
        print(f"Checking {server}...")
        host, df = fetch_disk_usage(server)
        all_reports[host] = df
    await send_disk_report(all_reports)


if __name__ == "__main__":
    asyncio.run(main())

