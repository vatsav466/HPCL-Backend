import urdhva_base
import pandas as pd
import hpcl_ceg_model
import mysql.connector
import orchestrator.dbconnector.credential_loader as credential_loader

# Material Codes for Domestic and Non-Domestic Sales
material_code_domestic = ['0949036', '0949109']
material_code_non_domestic = ['0948064', '0948450', '0949000', '0948042', '0948149']


async def fetch_from_tibco(query):
    # For fetching data from Tibco, Using MYSQL interface
    creds = credential_loader.get_credentials('TIBCO')
    connection = mysql.connector.connect(
        host=creds['host'],
        user=creds['user'],
        passwd=creds['password'],
        port=creds['port']
    )
    cursor = connection.cursor()
    cursor.execute(query)
    data = cursor.fetchall()
    # Convert to list of dictionaries
    columns = [col[0] for col in cursor.description]  # Extract column names
    result = [dict(zip(columns, row)) for row in data]
    cursor.close()
    connection.close()
    return result


async def lpg_plant_analysis(filters, cross_filters, drill_state="", time_grain="", resp_format=""):
    """
    LPG Plant level analysis
    :param filters:
    :param cross_filters:
    :param drill_state:
    :param time_grain:
    :param resp_format:
    :return:
    """
    lpg_data = {"stock": {"dom": 0, "non_dom": 0}, "current_inventory": 0,
                "hpcl_sales": {"dom": 0, "non_dom": 0}, "omc_sales": {"dom": 0, "non_dom": 0},
                "stock_transfers": {"dom": 0, "non_dom": 0},
                "tankage": {"total": 0, "not_in_ops": 0, "op_tankage": 0, "stock_percentage": 0},
                "avg_sales": {"dom": 0, "non_dom": 0}, "days_cover": {"dom": 0, "non_dom": 0},
                "in_transit": {"dom": 0, "non_dom": 0}, "days_cover_in_transit": {"dom": 0, "non_dom": 0}}

    zones = [cond['value'] for cond in filters if cond['key'].strip('"') == 'zone_name']
    plants = [cond['value'] for cond in filters if cond['key'].strip('"') == 'sap_id']
    filters = [cond for cond in filters if cond['key'].strip('"') not in ['zone_name', 'sap_id']]
    if not plants and zones:
        in_clause_raw = ", ".join(f"'{value}'" for value in zones)
        query = f"""select sap_id from location_master where bu='LPG' and zone in ({in_clause_raw})"""
        resp = await hpcl_ceg_model.LocationMaster.get_aggr_data(query, limit=1000)
        plants = [rec['sap_id'] for rec in resp['data']]

    # Fetching required data from tibco
    hpcl_sales = await fetch_hpcl_sales(plants)
    omc_sales = await fetch_omc_sales(plants)
    opening_stock = await fetch_opening_stock(plants)
    stock_transfer = await fetch_stock_transfer(plants)
    receipt_stock = await fetch_receipt_stock_transfer(plants)

    lpg_data['stock']['dom'] = opening_stock
    # Updating sales data
    for key, value in hpcl_sales.items():
        lpg_data['avg_sales'][key] += value
    for key, value in omc_sales.items():
        lpg_data['avg_sales'][key] += value
    for key, value in stock_transfer.items():
        lpg_data['avg_sales'][key] += value
    lpg_data['hpcl_sales'].update(hpcl_sales)
    lpg_data['omc_sales'].update(omc_sales)
    lpg_data['stock_transfers'].update(stock_transfer)

    lpg_data['current_inventory'] = round((float(opening_stock) + float(sum(list(receipt_stock.values()))) -
                                           float(sum(list(lpg_data['avg_sales'].values())))))
    lpg_data['days_cover']['dom'] = round(float(lpg_data['current_inventory']) /
                                          float(sum(list(lpg_data['avg_sales'].values()))))
    for key in lpg_data:
        if isinstance(lpg_data[key], dict):
            for key_ in lpg_data[key]:
                lpg_data[key][key_] = round(lpg_data[key][key_])
    return lpg_data


async def fetch_hpcl_sales(plants):
    """
    For fetching hpcl sales data
    :param plants:
    :return:
    """
    plant_cond = ''
    if plants:
        in_clause_raw = ", ".join(f"'{value}'" for value in plants)
        plant_cond = f" AND ZM.plant in ({in_clause_raw})"
    # HPCL Sales Query
    query_hpcl_sales = f"""
SELECT ZM.MATERIAL_NUMBER,ZM.plant as Locationcode, sum(quantity)/(1000 * 7) AS Average_Sales 
from  CONN_ENT.ZMMCI_MATDOC_V1_STG ZM
LEFT JOIN CONN_ENT.ZSDCV_CUST_SA_STG ZS ON ZM.GOODS_RECIPIENT = ZS.CUSTOMER
WHERE ZM.MVT_TYPE_INVENTORY_MANAGEMENT in ('309','601') AND ZS.DIST_CHANNEL in ('11', '12') AND 
ZM.MATERIAL_NUMBER in ('0949036', '0949109', '0948064', '0948450', '0949000', '0948042', '0948149')
AND DATE_FORMAT( ZM.POSTING_DATE_IN_THE_DOCUMENT,'%Y-%m-%d') between date_sub(CURRENT_DATE,interval 7 day) 
and date_sub(CURRENT_DATE,interval 1 day) {plant_cond}
group by  ZM.plant,ZM.MATERIAL_NUMBER
"""
    hpcl_sales = {"dom": 0, "non_dom": 0}
    resp = await fetch_from_tibco(query_hpcl_sales)
    df = pd.DataFrame(resp)
    for rec in df.groupby('MATERIAL_NUMBER', as_index=False).sum().to_dict(orient='records'):
        if rec['MATERIAL_NUMBER'] in material_code_domestic:
            hpcl_sales['dom'] += float(rec['Average_Sales'])
        else:
            hpcl_sales['non_dom'] += float(rec['Average_Sales'])
    return hpcl_sales


async def fetch_omc_sales(plants):
    """
    For fetching omc sales data
    :param plants:
    :return:
    """
    plant_cond = ''
    if plants:
        in_clause_raw = ", ".join(f"'{value}'" for value in plants)
        plant_cond = f" AND ZM.plant in ({in_clause_raw})"
    query_omc_sales = f"""
SELECT ZM.MATERIAL_NUMBER,ZM.plant as Locationcode, sum(quantity)/(1000 * 7) AS Average_Sales 
from  CONN_ENT.ZMMCI_MATDOC_V1_STG ZM
LEFT JOIN CONN_ENT.ZSDCV_CUST_SA_STG ZS ON ZM.GOODS_RECIPIENT = ZS.CUSTOMER
WHERE ZM.MVT_TYPE_INVENTORY_MANAGEMENT in ('309','601','643') AND ZS.DIST_CHANNEL in ('13') AND 
ZM.MATERIAL_NUMBER in ('0949036', '0949109', '0948064', '0948450', '0949000', '0948042', '0948149')
AND DATE_FORMAT( ZM.POSTING_DATE_IN_THE_DOCUMENT,'%Y-%m-%d') between date_sub(CURRENT_DATE,interval 7 day) 
and date_sub(CURRENT_DATE,interval 1 day) {plant_cond}
group by  ZM.plant,ZM.MATERIAL_NUMBER
"""
    omc_sales = {"dom": 0, "non_dom": 0}
    resp = await fetch_from_tibco(query_omc_sales)
    df = pd.DataFrame(resp)
    for rec in df.groupby('MATERIAL_NUMBER', as_index=False).sum().to_dict(orient='records'):
        if rec['MATERIAL_NUMBER'] in material_code_domestic:
            omc_sales['dom'] += float(rec['Average_Sales'])
        else:
            omc_sales['non_dom'] += float(rec['Average_Sales'])
    return omc_sales


async def fetch_stock_transfer(plants):
    """
    For fetching Stock Transfer data
    :param plants:
    :return:
    """
    return {"dom": 0, "non_dom": 0}


async def fetch_receipt_stock_transfer(plants):
    """
    For fetching Receipt Stock data
    :param plants:
    :return:
    """
    return {"dom": 0, "non_dom": 0}


async def fetch_opening_stock(plants):
    """
    For fetching opening stock  data
    :param plants:
    :return:
    """
    plant_cond = ''
    if plants:
        in_clause_raw = ", ".join(f"'{value}'" for value in plants)
        plant_cond = f" AND MAR.werks in ({in_clause_raw})"
    # Opening Stock
    query_open_stock = f"""
select werks ,matnr,
  sum(labst) as Opening_Stock
  from CONN_ENT.ZISCV_NSDM_V_MARD_STG MAR 
  inner join CONN_ENT.ZISCV_TANK_CAP_STG TCAP 
  on MAR.werks = TCAP.plant and MAR.lgort = TCAP.storage_location 
  where  MAR.matnr in ('0949036', '0949109', '0948064', '0948450', '0949000', '0948042', '0948149') {plant_cond}
  group by werks ,matnr
"""
    omc_sales = {"dom": 0, "non_dom": 0}
    resp = await fetch_from_tibco(query_open_stock)
    return sum([float(rec['Opening_Stock']) for rec in resp])
