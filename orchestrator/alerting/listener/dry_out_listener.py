import urdhva_base
import asyncio
import math
import json
import datetime
import polars as pl
import urdhva_base.redispool
import orchestrator.alerting.alert_helper as alert_helper
import utilities.connection_mapping as connection_mapping
from charts_actions import charts_connection_vault_routing
from orchestrator.alerting.alert_manager import create_alert
from dashboard_studio_model import Charts_Connection_Vault_RoutingParams
from orchestrator.actions.indent_dry_out import IndentDryOut as indent_dry_out


class DryoutCollector:
    @classmethod
    def assign_values_to_dataframe(cls, df, values):
        """
        Assigning camunda urls equally for each flow
        :param df:
        :param values:
        :return:
        """
        n = len(df)
        if n == 0:
            df = df.with_columns(pl.Series("camunda_listener", []))
            return df
        if n <= 10:
            assigned_values = values[:n]
        else:
            repeats = math.ceil(n / len(values))
            assigned_values = (values * repeats)[:n]
        df = df.with_columns(pl.Series("camunda_listener", assigned_values))
        return df

    @classmethod
    async def get_dry_out_data(cls):
        redis_queue = urdhva_base.redispool.RedisQueue('dry_out_camunda_queue')
        # Query to fetch dry out locations, intraday dry-out and potential dry out location
        Charts_Connection_Vault_RoutingParams.connection_id = connection_mapping.connection_mapping.get("cris", "2")
        Charts_Connection_Vault_RoutingParams.action = 'execute_query'
        function = await charts_connection_vault_routing(Charts_Connection_Vault_RoutingParams)
        schema = connection_mapping.schema_mapping.get("cris", "public")
        table = connection_mapping.table_mapping.get("dry_out", "")
        query = f'''select site_id, fcc_code, item_name,count(distinct tank_no) tank_cnt,
                    rosapcode, STRING_AGG(CAST(tank_no AS TEXT), ',') tank_no, product_no, 
                    case when sum(pumpable_Stock) <=0 then 0
                    when sum(pumpable_Stock) <(sum(sch.avgsales_7days)/7) then 1
                    when sum(pumpable_Stock) between (sum(sch.avgsales_7days)/7) and 
                    (sum(sch.avgsales_7days)/7)*3 then 2
                    when sum(pumpable_Stock) between (sum(sch.avgsales_7days)/7)*3 and 
                    (sum(sch.avgsales_7days)/7)*6 then 3
                    else 5 end status
                    from "{schema}".{table} sch
                    where 1=1 and sch.volume>0
                    group by site_id, fcc_code, item_name, rosapcode, product_no
                    order by site_id, fcc_code, item_name, rosapcode, product_no'''
        # records = await function(schema_name=schema, table_name=table, query=query)
        records = await function(query=query)
        records = pl.DataFrame(records)
        # records = records.filter(~pl.col("indent_status").is_in(['Raised', 'Completed']))
        records = records.unique(subset=['site_id', 'fcc_code', 'item_name', 'product_no'], keep='first')
        records = records.filter(pl.col('status') <= 2)
        records = cls.assign_values_to_dataframe(records,
                                                 list(connection_mapping.camunda_listener_mapping.values()))
        records = records.head(10).to_dicts()

        alert_data = {
            'bu': 'RO',
            'alert_type': 'RO',
            'sop_id': 'SOP293',
            'interlock_name': 'Dry Out Triggering Flow',
            'sap_id': '',  # location_id
            'product_code': '',
            'indent_no': '',
            'dealer_id': '',
            'severity': "",
            'workflow_datetime': '',
            'terminal_plant_id': '',
            'connection_name': 'ims'
        }

        _mapping = await indent_dry_out().prod_code_mapping()

        for _dry in records:
            _dry['indent_status'] = 'Raised'
            status = _dry['status']
            # alert_data['product_code'] = _dry['product_no']
            alert_data['product_code'] = _mapping.get(_dry['item_name'], _dry['product_no'])
            alert_data['sap_id'] = _dry['rosapcode']
            alert_data['device_id'] = str(_dry['tank_no'])
            alert_data['device_name'] = "Tank"
            alert_data[
                'severity'] = 'Critical' if status == 1 else 'High' if status == 2 else 'Medium' if status == 3 else 'Low'
            status, location_data = await alert_helper.get_location_details("RO", _dry['rosapcode'])
            if location_data.get("category") == 'R01':
                alert_data['severity'] = 'Critical'
            alert_data['indent_no'] = ''
            alert_data['dealer_id'] = _dry['rosapcode']
            alert_data['workflow_datetime'] = datetime.datetime.now(datetime.UTC).strftime('%Y-%m-%dT%H:%M:%S.%f')[
                                              :-3] + "Z"
            alert_data['terminal_plant_id'] = ''
            alert_data['camunda_host'] = _dry['camunda_listener']['host']
            alert_data['camunda_port'] = _dry['camunda_listener']['port']
            await redis_queue.put(json.dumps(alert_data))


if __name__ == "__main__":
    print(f"Executing dry-out alert creation at {datetime.datetime.now(datetime.timezone.utc)}")
    asyncio.run(DryoutCollector.get_dry_out_data())
