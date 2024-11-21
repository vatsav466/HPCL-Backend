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


class AlertAction:
    @classmethod
    async def update_alert_data(cls, alert_data):
        """
        Function to update alert data, Either reject or approve or justify or override
        :param alert_data:
        :return:
        """
        function_map = {"Justification": "justify_alert", "Rejected": "reject_alert",
                        "Approved": "approve_alert", "Override": "override_alert"}

        # get the function name
        function_name = function_map.get(alert_data['alert_action'], None)
        if function_name:
            # call the function
            return await getattr(cls, function_name)(alert_data)
        return None

    @classmethod
    async def base_functionality(cls, alert_data):
        """
        Function to update alert data, Either reject or approve or justify or override
        :param alert_data:
        :return:
        """
        # Todo:- here we have to write all the generic functionality like updating the alert data,
        #  history, fetching users, roles, ...

    @classmethod
    async def reject_alert(cls, alert_data):
        """
        Function to reject an alert
        :param alert_data:
        :return:
        """

    @classmethod
    async def approve_alert(cls, alert_data):
        """
        Function to approve an alert
        :param alert_data:
        :return:
        """

    @classmethod
    async def justify_alert(cls, alert_data):
        """
        Function to justify an alert
        :param alert_data:
        :return:
        """

    @classmethod
    async def override_alert(cls, alert_data):
        """
        Function to override an alert
        :param alert_data:
        :return:
        """


