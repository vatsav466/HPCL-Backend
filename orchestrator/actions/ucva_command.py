import urdhva_base

logger = urdhva_base.logger.Logger.getInstance("actions-processing-log")


class UCVACommand:
    async def get_required_variables(self):
        return ["alert_id"]

    async def ucvacommand(self, params):
        return True, None
