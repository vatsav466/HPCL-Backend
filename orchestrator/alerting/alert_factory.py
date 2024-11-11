class AlertFactory:
    @classmethod
    def create_bu_alert(cls, alert_data):
        """
        For translating bu level data into unique alert format
        """
        ...

    @classmethod
    def close_bu_alert(cls, alert_data):
        """
        For translating bu level data into unique alert format
        """
        ...

    @classmethod
    def create_alert(cls, alert_data):
        bu = alert_data['bu']
        sop_id = alert_data['sop_id']
        sap_id = alert_data['sap_id']

        # Create Alert

        # Create Interlock

    @classmethod
    def close_alert(cls, alert_data):
        bu = alert_data['bu']
        sop_id = alert_data['sop_id']
        sap_id = alert_data['sap_id']

        # Close Interlock
        # Close Alert
