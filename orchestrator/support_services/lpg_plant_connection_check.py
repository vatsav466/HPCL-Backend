import urdhva_base
import pandas as pd
import socket
import csv
import asyncio
import traceback
import os
from datetime import datetime
from zoneinfo import ZoneInfo
import orchestrator.notification_manager.notification_factory

PLANT_DATA_FILE = "/data/LPG_PLANTS_CREDENTIALS.csv"
CONNECTION_TIMEOUT = 10  # seconds

not_connected_plants = []


def load_plant_data():
    """Load plant data from CSV file"""
    try:
        if os.path.exists(PLANT_DATA_FILE):
            df = pd.read_csv(PLANT_DATA_FILE)
            print(f"Loaded {len(df)} plants from {PLANT_DATA_FILE}")
            return df
        else:
            print(f"Plant data file not found: {PLANT_DATA_FILE}")
            return None
    except Exception as e:
        print(f"Error loading plant data: {e}")
        return None


def test_telnet_connection(host_ip, port, timeout=CONNECTION_TIMEOUT):
    """Test telnet connection to host:port"""
    try:
        # Create socket and attempt connection
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)

        result = sock.connect_ex((host_ip, int(port)))
        sock.close()

        # connect_ex returns 0 if connection successful
        if result == 0:
            return True, "Connected"
        else:
            return False, f"Connection failed (Error: {result})"

    except socket.timeout:
        return False, "Connection timeout"
    except socket.gaierror as e:
        return False, f"DNS resolution failed: {e}"
    except Exception as e:
        return False, f"Connection error: {e}"


def check_plant_connectivity(plant_df):
    """Check connectivity for all plants and collect failed ones"""
    global not_connected_plants
    not_connected_plants = []

    print(f"Testing connectivity for {len(plant_df)} plants...")

    for index, plant in plant_df.iterrows():
        host_ip = str(plant['host_ip']).strip()
        port = str(plant['port']).strip()
        short_name = str(plant['short_name']).strip()

        print(f"Testing {short_name} ({host_ip}:{port})...")

        # Test connection
        is_connected, status_message = test_telnet_connection(host_ip, port)

        if not is_connected:
            # Add to not connected list
            not_connected_plants.append({
                's_no': len(not_connected_plants) + 1,
                'erp_id': str(plant['erp_id']).strip(),
                'plant_name': str(plant['plant_name']).strip(),
                'short_name': short_name,
                'zone': str(plant['zone']).strip(),
                'host_ip': host_ip,
                'port': port,
                'status': 'NOT CONNECTED',
                'error_message': status_message
            })
            print(f"{short_name}: {status_message}")
        else:
            print(f"{short_name}: Connected successfully")

    print(f"\nConnectivity check completed:")
    print(f"Total plants tested: {len(plant_df)}")
    print(f"Not connected plants: {len(not_connected_plants)}")
    print(f"Successfully connected plants: {len(plant_df) - len(not_connected_plants)}")

    return not_connected_plants


def create_not_connected_plants_csv():
    """Create CSV file with not connected plant details"""
    global not_connected_plants

    if not not_connected_plants:
        print("No disconnected plants found to create CSV")
        return None

    csv_path = "/data/not_connected_plants.csv"

    try:
        with open(csv_path, "w", newline='', encoding='utf-8') as csvfile:
            fieldnames = ['s_no', 'erp_id', 'plant_name', 'short_name', 'zone', 'host_ip', 'port', 'status']
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()

            # Write rows without error_message for CSV
            for plant in not_connected_plants:
                csv_row = {k: v for k, v in plant.items() if k != 'error_message'}
                writer.writerow(csv_row)

        print(f"Created not connected plants CSV with {len(not_connected_plants)} entries: {csv_path}")
        return csv_path

    except Exception as e:
        print(f"Error creating not connected plants CSV: {e}")
        return None


async def send_connectivity_mail(csv_path):
    """Send email with not connected plants details"""
    if not csv_path or not not_connected_plants:
        print("No disconnected plants to send")
        return

    now_ist = datetime.now(ZoneInfo("Asia/Kolkata"))
    formatted_time = now_ist.strftime('%d-%m-%Y %I:%M %p IST')

    total_not_connected = len(not_connected_plants)

    # Create zone summary for not connected plants
    zone_summary = {}
    for plant in not_connected_plants:
        zone = plant['zone']
        if zone in zone_summary:
            zone_summary[zone] += 1
        else:
            zone_summary[zone] = 1

    # Create zone summary text
    zone_summary_text = ", ".join([f"{zone}: {count}" for zone, count in zone_summary.items()])

    # Create HTML table for not connected plants
    table_rows = ""
    for plant in not_connected_plants:
        table_rows += f"""
        <tr>
            <td style="padding: 8px; border: 1px solid #ddd; text-align: center;">{plant['s_no']}</td>
            <td style="padding: 8px; border: 1px solid #ddd;">{plant['erp_id']}</td>
            <td style="padding: 8px; border: 1px solid #ddd;">{plant['plant_name']}</td>
            <td style="padding: 8px; border: 1px solid #ddd;">{plant['short_name']}</td>
            <td style="padding: 8px; border: 1px solid #ddd;">{plant['zone']}</td>
            <td style="padding: 8px; border: 1px solid #ddd;">{plant['host_ip']}</td>
            <td style="padding: 8px; border: 1px solid #ddd;">{plant['port']}</td>
            <td style="padding: 8px; border: 1px solid #ddd; color: red; font-weight: bold;">{plant['status']}</td>
        </tr>
        """

    html_body = f"""
    <html>
        <body style="font-family: Arial, sans-serif;">
        <h3 style="color: #333;">LPG Plants Connectivity Report</h3>
        <p><strong>Report Time:</strong> {formatted_time}</p>
        <p><strong>Total Not Connected Plants:</strong> <span style="color: red; font-weight: bold;">{total_not_connected}</span></p>
        <p><strong>Zone-wise Breakdown:</strong> {zone_summary_text}</p>

        <h4 style="color: #333;">Not Connected Plants Details:</h4>
        <table style="border-collapse: collapse; width: 100%; margin: 20px 0;">
            <thead>
                <tr style="background-color: #87CEEB;">
                    <th style="padding: 12px; border: 1px solid #ddd; text-align: left;">S.No</th>
                    <th style="padding: 12px; border: 1px solid #ddd; text-align: left;">ERP ID</th>
                    <th style="padding: 12px; border: 1px solid #ddd; text-align: left;">Plant Name</th>
                    <th style="padding: 12px; border: 1px solid #ddd; text-align: left;">Short Name</th>
                    <th style="padding: 12px; border: 1px solid #ddd; text-align: left;">Zone</th>
                    <th style="padding: 12px; border: 1px solid #ddd; text-align: left;">Host IP</th>
                    <th style="padding: 12px; border: 1px solid #ddd; text-align: left;">Port</th>
                    <th style="padding: 12px; border: 1px solid #ddd; text-align: left;">Status</th>
                </tr>
            </thead>
            <tbody>
                {table_rows}
            </tbody>
        </table>

        <h4 style="color: #333;">Error Details:</h4>
        <ul style="margin: 20px 0;">
    """

    # Add error details
    for plant in not_connected_plants:
        html_body += f"<li><strong>{plant['short_name']}</strong> ({plant['host_ip']}:{plant['port']}): {plant['error_message']}</li>"

    html_body += f"""
        </ul>

        <p><strong>Note:</strong> These plants failed telnet connectivity test and may require immediate attention.</p>
        <p>Detailed information is also available in the attached CSV file.</p>

        <br>
        <p>Regards,<br>
        LPG Plants Monitoring System</p>
        </body>
    </html>
    """

    for attempt in range(1, 4):
        try:
            print(f"Attempt {attempt} to send email with not connected plants...")
            ins = await orchestrator.notification_manager.notification_factory.get_notification_module("email")
            await ins.publish_message(
                subject=f"LPG - Not Connected Plants Report - {formatted_time}",
                recipients=[
                    "avinashgaurav@hpcl.in",
                    "rishikeshdevidas.patil@hpcl.in",   
                    "randhir.kumar2@hpcl.in"
                ],
                cc_recipients=["yesu.p@algofusiontech.com", "mrudula.m@algofusiontech.com", "venu@algofusiontech.com", "sachinkwarghane@hpcl.in", "arpitakanak.bara@hpcl.in"],
                html_content=True,
                body=html_body,
                attachments=[csv_path],
                force_send=True
            )
            print("Email sent successfully with not connected plants details.")
            break
        except Exception as e:
            print(f"Attempt {attempt} - Failed to send email: {e}")
            if attempt == 3:
                print("All email attempts failed.")


async def main():
    try:
        print("Starting LPG Plants Connectivity Checker...")

        # Clear the global not_connected_plants at the beginning of each run
        global not_connected_plants
        not_connected_plants = []

        # Load plant data
        plant_df = load_plant_data()
        if plant_df is None:
            print("Cannot proceed without plant data")
            return

        # Check connectivity for all plants
        not_connected_list = check_plant_connectivity(plant_df)

        # Create CSV with not connected plants details
        csv_path = create_not_connected_plants_csv()

        # Send email if there are not connected plants
        if csv_path and not_connected_plants:
            await send_connectivity_mail(csv_path)
            print(f"Email sent with {len(not_connected_plants)} not connected plants")
        else:
            print("All plants are connected - no email sent")

    except Exception as e:
        print(f"Error in main: {e}")
        print(traceback.format_exc())


if __name__ == "__main__":
    asyncio.run(main())

