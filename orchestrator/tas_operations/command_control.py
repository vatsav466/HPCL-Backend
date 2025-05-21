import urdhva_base
import aio_pika
import json
import traceback
import hpcl_ceg_enum
import hpcl_ceg_model
import utilities.helpers as helpers
import orchestrator.alerting.alert_factory as alert_create

logger = urdhva_base.logger.Logger.getInstance("tas_command_control_log")

command_mapping = {
    "gantry_shutdown": {"tag": "SmartLoad-Dual.BC-501A.PERMISSIVE_FROM_DNC", "value": 1},
    "gantry_start": {"tag": "SmartLoad-Dual.BC-501A.PERMISSIVE_FROM_DNC", "value": 0},
    "esd_shutdown": {"tag": "PLC.SFTPLC.ESD_FROM_DNC", "value": 1},
    "esd_start": {"tag": "PLC.SFTPLC.ESD_FROM_DNC", "value": 0}

}


async def publish_command(sap_id, command, bu, location_name, user_name, employee_id, value):
    # return False, "Operation not allowed, Please contact support"
    if command in ("gantry_shutdown", "esd_shutdown"):
        is_gantry = command == "gantry_shutdown"
        alert_message = "Gantry Permissive Off DNC_SOFT" if is_gantry else "ESD Permissive Off DNC_SOFT"
        action_msg = f"Gantry Shutdown command from DNC by {user_name} with employee id {employee_id}" if is_gantry else f"ESD Shutdown command from DNC by {user_name} with employee id {employee_id}"

        alert_data = {
            "bu": bu,
            "sap_id": sap_id,
            "location_name": location_name,
            "sop_id": "SOP028A",
            "interlock_name": alert_message,
            "alert_status": "Open",
            "alert_state": "InProgress",
            "severity": "CRITICAL",
            "alert_section": "TAS",
            "device_name": "",
            "return_data": True
        }

        camunda_url = await helpers.get_camunda_url(bu=bu, sap_id=sap_id, alert_section="TAS")
        status, created_alert = await alert_create.AlertFactory().create_alert(alert_data=alert_data, camunda_url=camunda_url)

        if not status or not created_alert:
            logger.error("Failed to create alert")
            return None

        alert_id = created_alert.get("id") if isinstance(created_alert, dict) else None
        if not alert_id:
            logger.error("Alert ID missing in created alert")
            return None

        new_alert = await hpcl_ceg_model.Alerts.get(alert_id)
        if not isinstance(new_alert, dict):
            new_alert = new_alert.__dict__

        if 'alert_history' not in new_alert:
            new_alert['alert_history'] = []

        action_entry = {
            'action_type': hpcl_ceg_enum.AlertActionType.Message.value,
            'action_msg': action_msg,
        }
        new_alert['alert_history'].append(action_entry)

        await hpcl_ceg_model.Alerts(id=alert_id, alert_history=new_alert['alert_history']).modify()
        logger.info(f"Successfully created new {alert_message} alert with ID: {alert_id}")
    
    if command in ("gantry_start", "esd_start"):
        cleared_alert_message = "Gantry Permissive off DNC_Soft_Cleared" if command == "gantry_start" else "ESD Permissive off DNC_Soft_Cleared"
        original_alert_message = "Gantry Permissive Off DNC_SOFT" if command == "gantry_start" else "ESD Permissive Off DNC_SOFT"

        # 1. Create "Cleared" alert
        cleared_alert_data = {
            "bu": bu,
            "sap_id": sap_id,
            "location_name": location_name,
            "sop_id": "SOP028A",
            "interlock_name": cleared_alert_message,
            "alert_status": "Closed",  # Since it's a cleared alert
            "alert_state": "Cleared",
            "severity": "INFO",
            "alert_section": "TAS",
            "device_name": "",
            "return_data": True
        }

        camunda_url = await helpers.get_camunda_url(bu=bu, sap_id=sap_id, alert_section="TAS")
        status, cleared_alert = await alert_create.AlertFactory().create_alert(alert_data=cleared_alert_data, camunda_url=camunda_url)

        if not status or not cleared_alert:
            logger.error("Failed to create cleared alert")
            return None

        # 2. Close the original DNC_SOFT alert
        existing_alerts = await hpcl_ceg_model.Alerts.get_all(urdhva_base.queryparams.QueryParams(q=f"sap_id='{sap_id}' AND interlock_name='{original_alert_message}' AND alert_status='Open'"), resp_type="plain")
        if existing_alerts:
            for alert in existing_alerts:
                if not isinstance(alert, dict):
                    alert = alert.__dict__

                alert_id = alert.get("id")
                if alert_id:
                    alert['alert_status'] = "Close"
                    alert['alert_state'] = "Resolved"

                    if 'alert_history' not in alert:
                        alert['alert_history'] = []

                    action_entry = {
                        'action_type': hpcl_ceg_enum.AlertActionType.Message.value,
                        'action_msg': (
                            f"Gantry Signal Clear off by {user_name} with employee id {employee_id}"
                            if command == "gantry_start"
                            else f"ESD Signal Clear off by {user_name} with employee id {employee_id}"
                        )
                    }
                    alert['alert_history'].append(action_entry)

                    await hpcl_ceg_model.Alerts(id=alert_id, alert_status="Closed", alert_state="Cleared", alert_history=alert['alert_history']).modify()
                    logger.info(f"Closed {original_alert_message} alert with ID: {alert_id}")
        else:
            logger.warning(f"No open alert found for {original_alert_message} to close.")

    if not command_mapping.get(command):
        return False, "Invalid inputs"
    connection = await aio_pika.connect_robust(
        host=urdhva_base.settings.rabbitmq_host,
        port=urdhva_base.settings.rabbitmq_port,
        virtualhost=urdhva_base.settings.rabbitmq_vhost,
        login=urdhva_base.settings.rabbitmq_username,
        password=urdhva_base.settings.rabbitmq_password
    )
    message = {
        "command": "write",
        "sensor_tag": command_mapping[command]['tag'],
        "value": f"{command_mapping[command]['value']}"
    }
    async with connection:
        channel = await connection.channel()

        # Generate the queue name using sap_id
        queue_name = f'command_write_{sap_id}'
        print(f"Queue name generated: {queue_name}")

        # Declare the queue
        await channel.declare_queue(queue_name, durable=True)

        # Create and send the message only once
        await channel.default_exchange.publish(
            aio_pika.Message(
                body=json.dumps(message).encode(),
                delivery_mode=aio_pika.DeliveryMode.PERSISTENT
            ),
            routing_key=queue_name
        )
    return True, {"message": f"Command sent to location {sap_id}"}
