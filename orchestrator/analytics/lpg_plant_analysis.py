import urdhva_base
import os
import pandas as pd
import hpcl_ceg_model
import mysql.connector
import urdhva_base.utilities
import utilities.helpers as helpers
import orchestrator.dbconnector.credential_loader as credential_loader

# Material Codes for Domestic and Non-Domestic Sales
material_code_domestic = ['0949036', '0949109']
material_code_non_domestic = ['0948064', '0948450', '0948042', '0948149']
material_code_bulk = ['0949000']


def load_lpg_tank_capacity():
    """Loading tank operating capacity and daily average sales data from master sheet provided by HPCL"""
    file_path = f"{os.path.dirname(helpers.__file__)}/../orchestrator/masterdata/lpg_tank_capacity.xlsx"
    capacity_data = pd.read_excel(file_path)
    capacity_data['LPGPlantCode'] = capacity_data['LPGPlantCode'].astype(str)
    # capacity_data = capacity_data[capacity_data['IsSelected'] == 'Y']
    return capacity_data


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
    lpg_data = {"stock": 0, "current_inventory": 0,
                "hpcl_sales": {"dom": 0, "non_dom": 0, "bulk": 0}, "omc_sales": {"dom": 0, "non_dom": 0, "bulk": 0},
                "stock_transfers": {"dom": 0, "non_dom": 0, "bulk": 0},
                "opening_stock": {"dom": 0, "non_dom": 0},
                "tankage": {"total": 0, "not_in_ops": 0, "op_tankage": 0, "stock_percentage": 0},
                "avg_sales": {"dom": 0, "non_dom": 0, "bulk": 0}, "days_cover": 0, "in_transit": 0}

    zones = [cond['value'] if cond['value'] else cond.get('val') for cond in filters
             if cond['key'].strip('"') == 'zone_name' and (cond['value'] or cond.get('val'))]
    if not zones:
        zones = ['SCZ', 'SZ']
    plants = [cond['value'] if cond['value'] else cond.get('val') for cond
              in filters if cond['key'].strip('"') == 'plant_name' and (cond['value'] or cond.get('val'))]
    filters = [cond for cond in filters if cond['key'].strip('"') not in ['zone_name', 'sap_id', 'plant_name']]
    if not plants and zones:
        in_clause_raw = ", ".join(f"'{value}'" for value in zones)
        query = f"""select sap_id from location_master where bu='LPG' and zone in ({in_clause_raw})"""
        resp = await hpcl_ceg_model.LocationMaster.get_aggr_data(query, limit=1000)
        plants = [rec['sap_id'] for rec in resp['data']]

    # Fetching required data from tibco
    hpcl_sales = await fetch_hpcl_sales(plants)
    omc_sales = await fetch_omc_sales(plants)
    opening_stock_dom, opening_stock_non_dom, operating_tankage = await fetch_opening_stock(plants)
    opening_stock = opening_stock_dom + opening_stock_non_dom
    stock_transfer = await fetch_stock_transfer(plants)
    receipt_stock = await fetch_receipt_stock_transfer(plants)

    lpg_data['stock'] = round(opening_stock)
    lpg_data['receipt_stock'] = round(float(sum(list(receipt_stock.values()))))
    # Updating sales data
    for key, value in hpcl_sales.items():
        lpg_data['avg_sales'][key] += value
    for key, value in omc_sales.items():
        lpg_data['avg_sales'][key] += value
    for key, value in stock_transfer.items():
        lpg_data['avg_sales'][key] += value
    dom_avg_sales, non_dom_avg_sales = await get_hpcl_average_sale(plants)
    lpg_data['opening_stock'].update({"dom": dom_avg_sales, "non_dom": non_dom_avg_sales})
    lpg_data['avg_sales']['dom'] = dom_avg_sales
    lpg_data['avg_sales']['non_dom'] = non_dom_avg_sales
    lpg_data['hpcl_sales'].update(hpcl_sales)
    lpg_data['omc_sales'].update(omc_sales)
    lpg_data['stock_transfers'].update(stock_transfer)
    lpg_data['in_transit'] = round(await fetch_intransit_stock_transfer(plants))

    avg_sales = float(sum(list(lpg_data['avg_sales'].values())))
    lpg_data['current_inventory'] = round((float(opening_stock) + float(sum(list(receipt_stock.values()))) - avg_sales))
    lpg_data['days_cover'] = round(float(lpg_data['current_inventory']) / avg_sales) if avg_sales else 0
    dom_days_cover = round(float((opening_stock_dom - dom_avg_sales) / dom_avg_sales)) if dom_avg_sales else 0
    non_dom_days_cover = round(float((opening_stock_non_dom - non_dom_avg_sales) / non_dom_avg_sales)) \
        if non_dom_avg_sales else 0
    lpg_data['days_cover_stock'] = {"dom": dom_days_cover, "non_dom": non_dom_days_cover}
    lpg_data['tankage']['total'] = 0
    lpg_data['tankage']['op_tankage'] = operating_tankage
    lpg_data['tankage']['stock_percentage'] = (opening_stock / operating_tankage) * 100

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
    hpcl_sales = {"dom": 0, "non_dom": 0, "bulk": 0}
    resp = await fetch_from_tibco(query_hpcl_sales)
    df = pd.DataFrame(resp)
    if not df.empty:
        for rec in df.groupby('MATERIAL_NUMBER', as_index=False).sum().to_dict(orient='records'):
            if rec['MATERIAL_NUMBER'] in material_code_domestic:
                hpcl_sales['dom'] += float(rec['Average_Sales'])
            elif rec['MATERIAL_NUMBER'] in material_code_non_domestic:
                hpcl_sales['non_dom'] += float(rec['Average_Sales'])
            elif rec['MATERIAL_NUMBER'] in material_code_bulk:
                hpcl_sales['bulk'] += float(rec['Average_Sales'])
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
    omc_sales = {"dom": 0, "non_dom": 0, "bulk": 0}
    resp = await fetch_from_tibco(query_omc_sales)
    df = pd.DataFrame(resp)
    if not df.empty:
        for rec in df.groupby('MATERIAL_NUMBER', as_index=False).sum().to_dict(orient='records'):
            if rec['MATERIAL_NUMBER'] in material_code_domestic:
                omc_sales['dom'] += float(rec['Average_Sales'])
            elif rec['MATERIAL_NUMBER'] in material_code_non_domestic:
                omc_sales['non_dom'] += float(rec['Average_Sales'])
            elif rec['MATERIAL_NUMBER'] in material_code_bulk:
                omc_sales['bulk'] += float(rec['Average_Sales'])
    return omc_sales


async def fetch_stock_transfer(plants):
    """
    For fetching Stock Transfer data
    :param plants:
    :return:
    """
    plant_cond = ''
    if plants:
        in_clause_raw = ", ".join(f"'{value}'" for value in plants)
        plant_cond = f" AND ZM.plant in ({in_clause_raw})"
    query = f"""SELECT ZM.MATERIAL_NUMBER,ZM.plant as Locationcode, sum(quantity)/(1000 * 7) AS Average_Sales 
from  CONN_ENT.ZMMCI_MATDOC_V1_STG ZM
LEFT JOIN CONN_ENT.ZSDCV_CUST_SA_STG ZS ON ZM.GOODS_RECIPIENT = ZS.CUSTOMER
WHERE ZM.MVT_TYPE_INVENTORY_MANAGEMENT in ('641') AND ZM.GOODS_RECIPIENT LIKE 'P%' AND ZS.SALES_ORG='2000'
AND ZM.MATERIAL_NUMBER in ('0949036', '0949109', '0948064', '0948450', '0949000', '0948042', '0948149')
AND DATE_FORMAT( ZM.POSTING_DATE_IN_THE_DOCUMENT,'%Y-%m-%d') between date_sub(CURRENT_DATE,interval 7 day) 
and date_sub(CURRENT_DATE,interval 1 day) {plant_cond}
group by  ZM.plant,ZM.MATERIAL_NUMBER"""
    resp = await fetch_from_tibco(query)
    df = pd.DataFrame(resp)
    receipt_stock = {"dom": 0, "non_dom": 0, "bulk": 0}
    if not df.empty:
        for rec in df.groupby('MATERIAL_NUMBER', as_index=False).sum().to_dict(orient='records'):
            if rec['MATERIAL_NUMBER'] in material_code_domestic:
                receipt_stock['dom'] += float(rec['Average_Sales'])
            elif rec['MATERIAL_NUMBER'] in material_code_non_domestic:
                receipt_stock['non_dom'] += float(rec['Average_Sales'])
            elif rec['MATERIAL_NUMBER'] in material_code_bulk:
                receipt_stock['bulk'] += float(rec['Average_Sales'])
    return receipt_stock


async def fetch_receipt_stock_transfer(plants):
    """
    For fetching Receipt Stock data
    :param plants:
    :return:
    """
    plant_cond = ''
    if plants:
        in_clause_raw = ", ".join(f"'{value}'" for value in plants)
        plant_cond = f" AND ZM.plant in ({in_clause_raw})"
    query = f"""SELECT ZM.MATERIAL_NUMBER,ZM.plant as Locationcode, sum(quantity)/(1000 * 7) AS Average_Sales 
from  CONN_ENT.ZMMCI_MATDOC_V1_STG ZM
LEFT JOIN CONN_ENT.ZSDCV_CUST_SA_STG ZS ON ZM.GOODS_RECIPIENT = ZS.CUSTOMER
WHERE ZM.MVT_TYPE_INVENTORY_MANAGEMENT in ('101') AND 
ZM.MATERIAL_NUMBER in ('0949036', '0949109', '0948064', '0948450', '0949000', '0948042', '0948149')
AND DATE_FORMAT( ZM.POSTING_DATE_IN_THE_DOCUMENT,'%Y-%m-%d') between date_sub(CURRENT_DATE,interval 7 day) 
and date_sub(CURRENT_DATE,interval 1 day) {plant_cond}
group by  ZM.plant,ZM.MATERIAL_NUMBER"""
    resp = await fetch_from_tibco(query)
    df = pd.DataFrame(resp)
    receipt_stock = {"dom": 0, "non_dom": 0, "bulk": 0}
    if not df.empty:
        for rec in df.groupby('MATERIAL_NUMBER', as_index=False).sum().to_dict(orient='records'):
            if rec['MATERIAL_NUMBER'] in material_code_domestic:
                receipt_stock['dom'] += float(rec['Average_Sales'])
            elif rec['MATERIAL_NUMBER'] in material_code_non_domestic:
                receipt_stock['non_dom'] += float(rec['Average_Sales'])
            elif rec['MATERIAL_NUMBER'] in material_code_bulk:
                receipt_stock['bulk'] += float(rec['Average_Sales'])
    return receipt_stock


async def fetch_intransit_stock_transfer(plants):
    """
    For fetching Intransit Stock data
    :param plants:
    :return:
    """
    plant_cond = ''
    if plants:
        in_clause_raw = ", ".join(f"'{value}'" for value in plants)
        plant_cond = f" AND ZM.plant in ({in_clause_raw})"
    current_date = helpers.get_time_stamp_by_delta(urdhva_base.utilities.get_present_time(), days=1,
                                                    with_month_start_day=False, date_time_format='%Y%m%d')
    query = f"""SELECT ZM.plant as Locationcode, sum(quantity)/(1000 * 7) AS Average_Sales 
from  CONN_ENT.ZMMCI_MATDOC_V1_STG ZM
LEFT JOIN CONN_ENT.ZSDCV_CUST_SA_STG ZS ON ZM.GOODS_RECIPIENT = ZS.CUSTOMER
WHERE ZM.MVT_TYPE_INVENTORY_MANAGEMENT in ('101') AND 
ZM.MATERIAL_NUMBER in ('0949000')
AND ZM.POSTING_DATE_IN_THE_DOCUMENT={current_date} {plant_cond}
group by  ZM.plant"""
    resp = await fetch_from_tibco(query)
    receipt_stock = sum([float(rec['Average_Sales']) for rec in resp])
    return receipt_stock


async def fetch_opening_stock(plants):
    """
    For fetching opening stock  data
    :param plants:
    :return:
    """
    plant_cond = ''
    if plants:
        in_clause_raw = ", ".join(f"'{value}'" for value in plants)
        plant_cond = f" AND plant in ({in_clause_raw})"
    current_date = helpers.get_time_stamp_by_delta(urdhva_base.utilities.get_present_time(), days=1,
                                                   with_month_start_day=False, date_time_format='%Y%m%d')
    # Opening Stock
    query_open_stock = f"""select plant,valuation_type as val_type,sum(stock_quantity)/1000 QTY from 
    CONN_ENT.ZMMCI_MATDOC_V1_STG WHERE POSTING_DATE_IN_THE_DOCUMENT between '20230601' and '{current_date}' and 
    valuation_type in ('HPC_DOM', 'HPC_NDM') and plant like "2%" and 
    (STORAGE_LOCATION <> '' and storage_location <> 'PINT') and MATERIAL_NUMBER ='0949000' {plant_cond} 
    group by plant,valuation_type
"""
    tank_capacity_master_data = load_lpg_tank_capacity()
    if plants:
        tank_capacity_master_data = tank_capacity_master_data[tank_capacity_master_data['LPGPlantCode'].isin(plants)]
    operating_tankage = tank_capacity_master_data['OperatingTankage'].sum()

    resp = await fetch_from_tibco(query_open_stock)
    df = pd.DataFrame(resp)
    df = df[['val_type', 'QTY']]
    dom, non_dom = df[df['val_type'] == 'HPC_DOM'].sum()['QTY'], df[df['val_type'] == 'HPC_NDM'].sum()['QTY']
    return round(float(dom)), round(float(non_dom)), round(operating_tankage)


async def get_hpcl_average_sale(plants):
    """
        For fetching average stock data for plants provided by HPCL
        :param plants:
        :return:
    """
    tank_capacity_master_data = load_lpg_tank_capacity()
    if plants:
        tank_capacity_master_data = tank_capacity_master_data[tank_capacity_master_data['LPGPlantCode'].isin(plants)]
    dom, non_dom = (tank_capacity_master_data['DAILY_AVERAGE_SALES_DOM'].sum(),
                    tank_capacity_master_data['DAILY_AVERAGE_SALES_NonDOM'].sum())
    return dom, non_dom
