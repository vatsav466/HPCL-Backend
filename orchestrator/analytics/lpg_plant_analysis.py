import urdhva_base
import hpcl_ceg_model


async def lpg_plant_analysis(filters, cross_filters, drill_state="", time_grain="", resp_format=""):
    lpg_data = {"stock": {"dom": 0, "non_dom": 0},
                "tankage": {"total": 0, "not_in_ops": 0, "op_tankage": 0, "stock_percentage": 0},
                "avg_sales": {"dom": 0, "non_dom": 0}, "days_cover": {"dom": 0, "non_dom": 0},
                "in_transit": {"dom": 0, "non_dom": 0}, "days_cover_in_transit": {"dom": 0, "non_dom": 0}}
    return lpg_data
    # Material Codes for Domestic and Non Domestic Sales
    material_code_domestic = ['0949036', '0949109']
    material_code_non_domestic = ['0948064', '0948450', '0949000', '0948042', '0948149']
    zones = [cond['value'] for cond in filters if cond['key'].strip('"') == 'zone_name']
    plants = [cond['value'] for cond in filters if cond['key'].strip('"') == 'sap_id']
    filters = [cond for cond in filters if cond['key'].strip('"') not in ['zone_name', 'sap_id']]
    if not plants and zones:
        in_clause_raw = ", ".join(f"'{value}'" for value in zones)
        query = f"""select sap_id from location_master where zone_name in ({in_clause_raw})"""
        resp = await hpcl_ceg_model.LocationMaster.get_aggr_data(query, limit=1000)
        plants = [rec['sap_id'] for rec in resp['data']]
    for cond in filters:
        cond['key'] = cond['key'].strip('"')
        if isinstance(cond["value"], str):
            value = [mnt_name.strip() for mnt_name in cond["value"].split(",")]
            if len(value) > 1:
                cond["cond"] = 'one-off'
                cond["value"] = value

    plant_cond = ""
    if plants:
        in_clause_raw = ", ".join(f"'{value}'" for value in plants)
        plant_cond = f" AND ZM.plant in ({in_clause_raw})"
    query_hpcl_sales = """
SELECT ZM.MATERIAL_NUMBER,ZM.plant as Locationcode, sum(quantity)/(1000 * 7) AS Average_Sales 
from  ZMMCI_MATDOC_V1_STG ZM
LEFT JOIN ZSDCV_CUST_SA_STG ZS ON ZM.GOODS_RECIPIENT = ZS.CUSTOMER
WHERE ZM.MVT_TYPE_INVENTORY_MANAGEMENT in ('309','601') AND ZS.DIST_CHANNEL in ('11', '12') AND 
ZM.MATERIAL_NUMBER in ('0949036', '0949109', '0948064', '0948450', '0949000', '0948042', '0948149')
AND DATE_FORMAT( ZM.POSTING_DATE_IN_THE_DOCUMENT,'%Y-%m-%d') between date_sub(CURRENT_DATE,interval 7 day) 
and date_sub(CURRENT_DATE,interval 1 day) {plant_cond}
group by  ZM.plant,ZM.MATERIAL_NUMBER
"""