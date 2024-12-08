import urdhva_base
from hpcl_ceg_enum import *
from hpcl_ceg_model import *
import fastapi
import utilities.connection_mapping as connection_mapping
from charts_actions import charts_connection_vault_routing
from orchestrator.alerting.alert_manager import create_alert
from dashboard_studio_model import Charts_Connection_Vault_RoutingParams

router = fastapi.APIRouter(prefix='/indentdryout')


# Action sync_data_from_cris_to_ceg
@router.post('/sync_data_from_cris_to_ceg', tags=['IndentDryOut'])
async def indentdryout_sync_data_from_cris_to_ceg(data: Indentdryout_Sync_Data_From_Cris_To_CegParams):
    Charts_Connection_Vault_RoutingParams.connection_id = data.source_connection
    Charts_Connection_Vault_RoutingParams.action = 'get_data'
    function = await charts_connection_vault_routing(Charts_Connection_Vault_RoutingParams)
    records = await function(schema_name=data.source_schema, table_name=data.source_table)

    Charts_Connection_Vault_RoutingParams.connection_id = data.destination_connection
    Charts_Connection_Vault_RoutingParams.action = 'upsert_data'
    function = await charts_connection_vault_routing(Charts_Connection_Vault_RoutingParams)
    return await function(
        schema_name=data.destination_schema,
        table_name=data.destination_table,
        records=records,
        conflict_columns=data.conflict_columns
    )


# Action create_dry_out_alert
@router.post('/create_dry_out_alert', tags=['IndentDryOut'])
async def indentdryout_create_dry_out_alert(data: Indentdryout_Create_Dry_Out_AlertParams):
    Charts_Connection_Vault_RoutingParams.connection_id = connection_mapping.connection_mapping.get("cris", "1")
    Charts_Connection_Vault_RoutingParams.action = 'get_data'
    function = await charts_connection_vault_routing(Charts_Connection_Vault_RoutingParams)
    schema = connection_mapping.schema_mapping.get("cris", "public")
    table = connection_mapping.table_mapping.get("dry_out", "")
    query = f'''SELECT * FROM "{schema}"."{table}" WHERE "volume" > 0 AND "indent_status" != 'Raised' AND "status" IN ('0', '1', '2');'''
    records = await function(schema_name=schema, table_name=table, query=query)
    records = records.head(10).to_dicts()

    alert_data = {
        'bu': 'RO',
        'alert_type': 'RO',
        'sop_id': 'SOP291',
        'interlock_name': 'Indent Dry Out',
        'sap_id': '',  # location_id
        'product_code': '',
        'indent_no': '',
        'dealer_id': '',
        'severity': ""
    }

    for _dry in records:
        _dry['indent_status'] = 'Raised'
        status = _dry['status']
        alert_data['product_code'] = _dry['product_no']
        alert_data['sap_id'] = _dry['site_id']
        alert_data['severity'] = 'Critical' if status == 0 else 'High' if status == 1 else 'Medium' if status == 2 else 'Low'
        alert_data['indent_no'] = ''
        alert_data['dealer_id'] = _dry['rosapcode']
        await create_alert(alert_data)

        Charts_Connection_Vault_RoutingParams.connection_id = "1"
        Charts_Connection_Vault_RoutingParams.action = 'upsert_data'
        function = await charts_connection_vault_routing(Charts_Connection_Vault_RoutingParams)
        return await function(
            schema_name="HPCL_HOS",
            table_name=connection_mapping.table_mapping.get("dry_out", ""),
            records=_dry,
            conflict_columns=["site_id", "fcc_code", "product_no", "tank_no"]
        )

    return {"status": True, "message": "Alerts created successfully", "data": []}
