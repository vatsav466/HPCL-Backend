import orchestrator.alerting.alert_factory as alert_factory


class VAAlertManager(alert_factory.AlertFactory):
    @classmethod
    def create_bu_alert(cls, alert_data):
        pass

    @classmethod
    def close_bu_alert(cls, alert_data):
        ...
