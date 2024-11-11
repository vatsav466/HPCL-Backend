import orchestrator.alerting.ro_alert as ro_alert
import orchestrator.alerting.va_alert as va_alert
import orchestrator.alerting.vts_alert as vts_alert
import orchestrator.alerting.tas_alert as tas_alert
import orchestrator.alerting.lpg_alert as lpg_alert
import orchestrator.alerting.emlock_alert as emlock_alert


async def create_alert(alert_data):
    """
    Create an alert based on input alert data. This function delegates the actual creation of the alert to the specific alert manager (e.g. ROAlertManager, VAAlertManager, etc.) based on the 'alert_type' field in the input alert data.

    Parameters:
        alert_data (dict): A dictionary containing the data to create the alert.

    Returns:
        dict: A dictionary containing the status, message and the created alert document.
    """
    if alert_data['alert_type'] == 'RO':
        return await ro_alert.ROAlertManager().create_bu_alert(alert_data)
    elif alert_data['alert_type'] == 'VA':
        return await va_alert.VAAlertManager().create_bu_alert(alert_data)
    elif alert_data['alert_type'] == 'VTS':
        return await vts_alert.VTSAlertManager().create_bu_alert(alert_data)
    elif alert_data['alert_type'] == 'EMLock':
        return await emlock_alert.EMLockAlertManager().create_bu_alert(alert_data)
    elif alert_data['alert_type'] == 'TAS':
        return await tas_alert.TASAlertManager().create_bu_alert(alert_data)
    elif alert_data['alert_type'] == 'LPG':
        return await lpg_alert.LPGAlertManager().create_bu_alert(alert_data)
    return None


async def close_alert(alert_data):
    """
    Close an alert based on input alert data. This function delegates the actual closure of the alert to the specific alert manager (e.g. ROAlertManager, VAAlertManager, etc.) based on the 'alert_type' field in the input alert data.

    Parameters:
        alert_data (dict): A dictionary containing the data to close the alert.

    Returns:
        dict: A dictionary containing the status, message and the closed alert document.
    """
    if alert_data['alert_type'] == 'RO':
        return await ro_alert.ROAlertManager().close_bu_alert(alert_data)
    elif alert_data['alert_type'] == 'TAS':
        return await vts_alert.VTSAlertManager().close_bu_alert(alert_data)
    elif alert_data['alert_type'] == 'LPG':
        return await vts_alert.VTSAlertManager().close_bu_alert(alert_data)
    elif alert_data['alert_type'] == 'VA':
        return await va_alert.VAAlertManager().close_bu_alert(alert_data)
    elif alert_data['alert_type'] == 'VTS':
        return await vts_alert.VTSAlertManager().close_bu_alert(alert_data)
    elif alert_data['alert_type'] == 'EMLock':
        return await emlock_alert.EMLockAlertManager().close_bu_alert(alert_data)
    return None
