import urdhva_base
from hpcl_ceg_enum import *
from hpcl_ceg_model import *
import fastapi
import datetime
import utilities.connection_mapping as connection_mapping
from charts_actions import charts_connection_vault_routing
from orchestrator.alerting.alert_manager import create_alert
from dashboard_studio_model import Charts_Connection_Vault_RoutingParams
from orchestrator.actions.indent_dry_out import IndentDryOut as indent_dry_out

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
    Charts_Connection_Vault_RoutingParams.connection_id = connection_mapping.connection_mapping.get("hpcl_ceg", "1")
    Charts_Connection_Vault_RoutingParams.action = 'get_data'
    function = await charts_connection_vault_routing(Charts_Connection_Vault_RoutingParams)
    schema = connection_mapping.schema_mapping.get("cris", "public")
    table = connection_mapping.table_mapping.get("dry_out", "")
    query = f'''SELECT * FROM "{schema}"."{table}" WHERE "volume" > 0 AND "indent_status" NOT IN ('Raised', 'Completed') AND "status" IN ('0', '1', '2');'''
    # query = f'''select site_id, fcc_code, item_name,count(distinct tank_no) tank_cnt,
    #         rosapcode, STRING_AGG(CAST(tank_no AS TEXT), ',') tank_no, product_no,
    #         case when sum(pumpable_Stock) <=0 then 1
    #         when sum(pumpable_Stock) <(sum(sch.avgsales_7days)/7) then 2
    #         when sum(pumpable_Stock) between (sum(sch.avgsales_7days)/7) and (sum(sch.avgsales_7days)/7)*3 then 3
    #         when sum(pumpable_Stock) between (sum(sch.avgsales_7days)/7)*3 and (sum(sch.avgsales_7days)/7)*6 then 4
    #         else 6 end status
    #         from "{schema}".{table} sch
    #         where 1=1 and sch.volume>0
    #         group by site_id, fcc_code, item_name, rosapcode, product_no
    #         order by site_id, fcc_code, item_name, rosapcode, product_no'''
    records = await function(schema_name=schema, table_name=table, query=query)
    records = records.unique(subset=['site_id', 'fcc_code', 'item_name', 'product_no'], keep='first')
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
        'severity': "",
        'workflow_datetime': '',
        'terminal_loc_code': ''
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
        alert_data['severity'] = 'Critical' if status == 0 else 'High' if status == 1 else 'Medium' if status == 2 else 'Low'
        alert_data['indent_no'] = ''
        alert_data['dealer_id'] = _dry['rosapcode']
        alert_data['workflow_datetime'] = datetime.datetime.now(datetime.UTC).strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + "Z"
        alert_data['terminal_loc_code'] = ''
        await create_alert(alert_data)

        Charts_Connection_Vault_RoutingParams.connection_id = "1"
        Charts_Connection_Vault_RoutingParams.action = 'execute_query'
        function = await charts_connection_vault_routing(Charts_Connection_Vault_RoutingParams)
        query = f"""UPDATE "HPCL_HOS".sch_inventory_forecast_dashboard SET "indent_status" = 'Raised' """ \
                f"""WHERE "site_id" = '{_dry['site_id']}' """ \
                f"""AND "fcc_code" = '{_dry['fcc_code']}' """ \
                f"""AND "product_no" = '{_dry['product_no']}' """
        await function(
            query=query
        )
        # await function(
        #     schema_name="HPCL_HOS",
        #     table_name=connection_mapping.table_mapping.get("dry_out", ""),
        #     records=_dry,
        #     conflict_columns=["site_id", "fcc_code", "product_no", "tank_no"]
        # )

    return {"status": True, "message": "Alerts created successfully", "data": []}


# Action get_dried_out_plants
@router.post('/get_dried_out_plants', tags=['IndentDryOut'])
async def indentdryout_get_dried_out_plants(data: Indentdryout_Get_Dried_Out_PlantsParams):
    top_x_axis = [
        "Indent Not Raised", "Indent Raised", "Valid Indent", "Truck Allocated", "Sent to SAP",
        "Sales Order Placed", "R2 Swiped", "Invoice Created", "R3 Swiped", "VTS",
        "Indent Delivered"
    ]
    bottom_x_axis = [
        "Dealer", "SO\nRM", "SO\nCO", "SO", "SO\nRM", "SO\nRM",
        "Plant Incharge\nRM", "Plant Incharge\nRM", "Plant Incharge\nRM",
        "Plant Incharge\nRM", "SO\nRM"
    ]
    query = "select location_name as name, sap_id, progress_rate as present_stage," \
            "case when severity = 'Critical' then '0' " \
            "when severity = 'High' then '1' " \
            "when severity = 'Medium' then '2' " \
            "when severity = 'Low' then '3' " \
            "else severity " \
            "end as dry_out_days " \
            "from alerts where interlock_name = 'Indent Dry Out'"

    Charts_Connection_Vault_RoutingParams.connection_id = "1"
    Charts_Connection_Vault_RoutingParams.action = 'execute_query'
    function = await charts_connection_vault_routing(Charts_Connection_Vault_RoutingParams)
    resp = await function(
        query=query
    )
    return {"status": True, "message": "Success", "data": resp, "top_x_axis": top_x_axis, "bottom_x_axis": bottom_x_axis}
    # return [
    #     {"name": "location1", "sap_id": "12345", "dry_out_days": 3, "present_stage": 3},
    #     {"name": "location2", "sap_id": "112233", "dry_out_days": 2, "present_stage": 3},
    #     {"name": "location3", "sap_id": "223344", "dry_out_days": 3, "present_stage": 4},
    #     {"name": "location4", "sap_id": "334455", "dry_out_days": -3, "present_stage": 6},
    #     {"name": "location5", "sap_id": "445566", "dry_out_days": -1, "present_stage": 5},
    #     {"name": "location6", "sap_id": "556677", "dry_out_days": -2, "present_stage": 2},
    #     {"name": "location6", "sap_id": "556677", "dry_out_days": -2, "present_stage": 1},
    #     {"name": "location6", "sap_id": "556677", "dry_out_days": -6, "present_stage": 0}
    # ]


# Action get_dry_out_stats
@router.post('/get_dry_out_stats', tags=['IndentDryOut'])
async def indentdryout_get_dry_out_stats(data: Indentdryout_Get_Dry_Out_StatsParams):
    ...
