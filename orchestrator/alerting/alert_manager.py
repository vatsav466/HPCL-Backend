import orchestrator.alerting.ro_alert as ro_alert
import orchestrator.alerting.va_alert as va_alert
import orchestrator.alerting.vts_alert as vts_alert
import orchestrator.alerting.emlock_alert as emlock_alert


async def create_alert(alert_data):
    """
    Create alert based on input alert BU or Type for which type of alert
    :param alert_data: raw alert data from API or Message Queue
    :return:
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
        return await vts_alert.VTSAlertManager().create_bu_alert(alert_data)
    elif alert_data['alert_type'] == 'LPG':
        return await vts_alert.VTSAlertManager().create_bu_alert(alert_data)
    return None


async def close_alert(alert_data):
    """
    Close alert based on input alert BU or Type for which type of alert
    :param alert_data: raw alert data from API or Message Queue
    :return:
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
