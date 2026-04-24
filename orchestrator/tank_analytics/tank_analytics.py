import urdhva_base
import asyncio
import polars as pl
import charts_actions
from decimal import Decimal
import dashboard_studio_model
from datetime import datetime, timedelta, date
import orchestrator.tank_analytics.tank_queries as tank_queries

def process_rows(rows: list[dict]) -> list[dict]:
    """Convert Decimal fields to float and map product names."""
    return [
        {
            k: tank_queries.product_name_mapping.get(v, v) if k == "product"
                else (float(v) if isinstance(v, Decimal) else v)
            for k, v in row.items()
        }
        for row in rows
    ]

async def generate_filters_cond(filters):
    """
    generates filter conditions
    Args: 
        filters: list of WidgetFilter objects 
    Returns:
        dictionary with key as condition name and value as condition string
    """
    conds = {}
    for filter in filters:
        key = filter.key
        if key == 'date_time':
            date = filter.value
            cond = f"hltd.{key}::DATE BETWEEN DATE '{date.replace(",", "' AND DATE '")}'"
            conds[key] = cond
        elif key == 'sap_id':
            sap_id = filter.value
            cond = f"hltd.{key} = '{sap_id}' "
            conds[key] = cond
        elif key == 'zone':
            zone = filter.value
            cond = f"lm.{key} = '{zone}' "
            conds[key] = cond
    return conds


async def stock_dispatch_receipt(filter_clause, connection_params):
    """
    Gets available stock data, product dispatch and receipt data from host_live_tank_details.
    Args:
        filter_clause: string with filter conditions to be used in query
        connection_params: Charts_Connection_Vault_RoutingParams to establish db connection
    Returns:
        dictionary with polars dataframes
    """
    # Build queries
    query_keys = ("dispatch", "receipt", "tank_details")
    queries = [tank_queries.queries.get(key, "").format(filter_clause) for key in query_keys]

    # Execute all queries concurrently
    function = await charts_actions.charts_connection_vault_routing(connection_params)
    results = await asyncio.gather(*(function(query=q) for q in queries))
    print(type(results))

    # Process and return as polars DataFrames
    keys = ("dispatch", "receipt", "stock")
    return {
        key: pl.DataFrame(process_rows(rows))
        for key, rows in zip(keys, results)
    }


async def calculate_net_stock(tank_data):
    """
    calculating net stock = (total stock + total receipt) - total dispatch
    Args:
        tank_data: dictionary 
                    {
                    "dispatch" : polars dataframe,
                    "receipt" : polars dataframe,
                    "stock" : polars dataframe
                    }
    Returns:
        net_stock (float value)
    """
    dispatch: pl.DataFrame = tank_data.get("dispatch", pl.DataFrame())
    receipt: pl.DataFrame  = tank_data.get("receipt",  pl.DataFrame())
    stock: pl.DataFrame    = tank_data.get("stock",    pl.DataFrame())

    total_dispatch = dispatch["sum"].sum() if not dispatch.is_empty() else 0.0
    total_receipt  = receipt["sum"].sum()  if not receipt.is_empty()  else 0.0
    print(stock)
    total_stock    = (
        stock.filter(pl.col("available_stock_kl") > 0)["available_stock_kl"].sum()
        if not stock.is_empty() else 0.0
    )
    print(total_stock)
    return (total_stock + total_receipt) - total_dispatch


async def tank_ullage(filter_clause, connection_params):
    """
    calculate tank ullage
    Args:
        filter_clause: string with filter conditions to be used in query
        connection_params: Charts_Connection_Vault_RoutingParams to establish db connection
    Returns:
        polars dataframe with tank ullage and tank capacity product wise 
    """
    ullage_query = tank_queries.queries.get('tank_ullage', '').format(filter_clause)
    function = await charts_actions.charts_connection_vault_routing(connection_params)
    ullage_resp = await function(query=ullage_query)
    ullage_data  = pl.DataFrame(process_rows(ullage_resp)).group_by("product").agg(
                        pl.col("ullage").sum(), pl.col("capacity").sum(), pl.col("dead_stock").sum()
            )
    return ullage_data


async def action_stock_sustainability(filter_clause, connection_params):
    """
    calculates stock sustainability
    Args: 
        filter_clause: string with filter conditions to be used in query
        connection_params: Charts_Connection_Vault_RoutingParams to establish db connection
    Returns:
        api response dictionary with calculated stock_sustainability

    """
    # generate filter clause with current date
    # stock_clause = f"date_time::DATE = DATE '2026-02-05' {filter_clause}" #hardcoded date for testing 
    stock_clause = f"date_time::DATE = DATE '{date.today().strftime("%Y-%m-%d")}' {filter_clause}"

    # get net stock
    tank_data = await stock_dispatch_receipt(filter_clause=stock_clause, connection_params=connection_params)
    net_stock = await calculate_net_stock(tank_data) 

    # get dispatch average
    dispatch_average_query = tank_queries.queries.get('dispatch_average', '').format(filter_clause)
    function = await charts_actions.charts_connection_vault_routing(connection_params)
    avg_resp = await function(query=dispatch_average_query)
    avg = avg_resp[0].get('seven_day_avg', 0)
    dispatch_average = float(avg)

    # calculte stock sustainability
    stock_sustainability = net_stock/dispatch_average if dispatch_average else 0

    return{"status": True, "data": stock_sustainability, "message": "successfully retrieved data"}


async def action_product_wise_trends(filter_clause, connection_params):
    """
    product wise bifurcation for available_stock, tank_dispatch, tank_receipt, seven_day_avg, net_stock, 
    stock_sustainability, ullage, capacity for given date range and sap id filter 
    Args: 
        filter_clause: string with filter conditions to be used in query
        connection_params: Charts_Connection_Vault_RoutingParams to establish db connection
    Returns:
        api response dictionary with product wise trends data 
    """
    # generate filter clause with current date
    # stock_clause = f"date_time::DATE = DATE '2026-02-05' {filter_clause}" #hard coded date for testing
    stock_clause = f"date_time::DATE = DATE '{date.today().strftime('%Y-%m-%d')}' {filter_clause}"

    # fetch stock/dispatch/receipt and average dispatch concurrently
    prod_avg_dispatch_query = tank_queries.queries.get("dispatch_average_prodwise", "").format(filter_clause)
    function = await charts_actions.charts_connection_vault_routing(connection_params)

    (data, prod_avg_resp) = await asyncio.gather(
        stock_dispatch_receipt(filter_clause=stock_clause, connection_params=connection_params),
        function(query=prod_avg_dispatch_query)
    )

    # process dispatch
    dispatch_data = (
        data.get("dispatch", pl.DataFrame())
        .rename({"sum": "tank_dispatch"})
        .select(["product", "tank_dispatch"])
        .group_by("product")
        .agg(pl.col("tank_dispatch").sum())
    )

    # process receipt
    receipt_data = (
        data.get("receipt", pl.DataFrame())
        .rename({"sum": "tank_receipt"})
        .select(["product", "tank_receipt"])
        .group_by("product")
        .agg(pl.col("tank_receipt").sum())
    )

    # process stock
    stock_data = (
        data.get("stock", pl.DataFrame())
        .select(["product", "available_stock_kl"])
        .group_by("product")
        .agg(
            pl.when(pl.col("available_stock_kl") > 0)
            .then(pl.col("available_stock_kl"))
            .otherwise(0)
            .sum()
            .alias("available_stock")
        )
    )

    # process average dispatch
    prod_avg_dispatch = (
        pl.DataFrame(process_rows(prod_avg_resp))
        .drop_nulls()
    )

    # join all dataframes
    res = (
        stock_data
        .join(dispatch_data, on="product", how="full", coalesce=True)
        .join(receipt_data,  on="product", how="full", coalesce=True)
        .drop_nulls()
        .join(prod_avg_dispatch, on="product", how="full", coalesce=True)
    )

    # calculate net stock and sustainability in one with_columns call
    res = res.with_columns(
        (
            (
                pl.when(pl.col("available_stock") < 0).then(0).otherwise(pl.col("available_stock"))
                + pl.col("tank_receipt")
                - pl.col("tank_dispatch")
            )
            .round(2)
            .alias("net_stock")
        )
    ).with_columns(
        pl.when(pl.col("seven_day_avg") != 0)
        .then((pl.col("net_stock") / pl.col("seven_day_avg")).round(2))
        .otherwise(0)
        .alias("stock_sustainability")
    )
    # fetch ullage and join
    ullage_data = await tank_ullage(filter_clause=filter_clause, connection_params=connection_params)
    print(ullage_data)
    res = res.join(ullage_data, on="product", how="left")

    return {"status": True, "data": res.to_dicts(), "message": "data fetched successfully"}


async def action_daily_trends(filter_clause, connection_params):
    """
        gets tank_dispatch, bcu_dispatch, tank_receipt, difference between tank_dispatch and bcu_dispatch
        for all products for a given date and sap id filter
        Args: 
            filter_clause: string with filter conditions to be used in query
            connection_params: Charts_Connection_Vault_RoutingParams to establish db connection
        Returns:
            api response dictionary with product wise trends data 
    """
    tank_dispatch = tank_queries.queries.get('dispatch', '').format(filter_clause)
    tank_receipt = tank_queries.queries.get('receipt', '').format(filter_clause)
    bcu_dispatch  = tank_queries.queries.get('bcu_total_dispatch', '').format(filter_clause)

    function = await charts_actions.charts_connection_vault_routing(connection_params)
    tank_dispatch_resp = await function(query=tank_dispatch)
    tank_reciept_resp  = await function(query=tank_receipt)
    bcu_dispatch_resp = await function(query=bcu_dispatch)

    tank_dis_resp = [
        {k: float(v) if isinstance(v, Decimal) else v for k, v in row.items()}
        for row in tank_dispatch_resp
    ]

    tank_rec_resp = [
        {k: float(v) if isinstance(v, Decimal) else v for k, v in row.items()}
        for row in tank_reciept_resp
    ]

    bcu_resp = [
        {k: float(v) if isinstance(v, Decimal) else v for k, v in row.items()}
        for row in bcu_dispatch_resp
    ]

    for prod_data in bcu_resp:
        prod = prod_data['product']
        sap_id = prod_data['sap_id']
        prod_data['product'] = tank_queries.product_mapping[sap_id]['host_day_end_details'][prod]
    
    dispatch_df = (
        pl.DataFrame(tank_dis_resp)
        .rename({"sum": "tank_dispatch"})
    )

    bcu_df = (
        pl.DataFrame(bcu_resp)
        .rename({"sum": "bcu_dispatch"})
    )

    reciept_df = (
        pl.DataFrame(tank_rec_resp)
        .rename({"sum": "tank_receipt"})
    )
    dispatch_df = dispatch_df.drop_nulls()
    bcu_df = bcu_df.drop_nulls()
    reciept_df = reciept_df.drop_nulls()

    print(dispatch_df)
    print(bcu_df)
    print(reciept_df)

    resp = (
        dispatch_df
        .join(bcu_df, on=["product", "sap_id", "zone"], how="full", coalesce=True)
        .join(reciept_df, on=["product", "sap_id", "zone"], how="full", coalesce=True)
        .fill_null(0)  
        .with_columns(
            (pl.col("tank_dispatch") - pl.col("bcu_dispatch")).alias("difference")
        )
        .select(["sap_id","product", "tank_dispatch", "bcu_dispatch", "tank_receipt", "difference"])
        .to_dicts()
    )
    return {"status": True, "data": resp, "message": "data fetched successfully"}


async def action_daywise_trends(filter_clause, connection_params):
    """
    daywise and product wise data for product dispatch, reciept, available_stock, dead_stock, capacity, ullage
    for given sap id and date filter
    Args: 
        filter_clause: string with filter conditions to be used in query
        connection_params: Charts_Connection_Vault_RoutingParams to establish db connection
    Returns:
        api response dictionary with daywise trends data 
    """
    products_query = tank_queries.queries.get('daywise_trends', '').format(filter_clause)
    print("products query -->", products_query)
    ullage_query = tank_queries.queries.get('ullage_daywise_trends', '').format(filter_clause)
    print("ullage query -->", ullage_query)

    function = await charts_actions.charts_connection_vault_routing(connection_params)
    products_res = await function(query=products_query)
    ullage_res = await function(query=ullage_query)

    for daywise_data in products_res:
        daywise_data['product'] = tank_queries.product_name_mapping.get(daywise_data['product'], daywise_data['product'])
    products_res = [
        {k: float(v) if isinstance(v, Decimal) else v for k, v in row.items()}
        for row in products_res
    ]

    for daywise_data in ullage_res:
        daywise_data['product'] = tank_queries.product_name_mapping.get(daywise_data['product'], daywise_data['product'])
    ullage_res = [
        {k: float(v) if isinstance(v, Decimal) else v for k, v in row.items()}
        for row in ullage_res
    ]

    products_data = pl.DataFrame(products_res)
    products_data = products_data.group_by(["product", "date_time"]).agg(
        pl.col("dispatch").sum(),
        pl.col("reciept").sum()
    ).drop_nulls() 

    ullage_data = pl.DataFrame(ullage_res)
    ullage_data = ullage_data.group_by(["product", "date_time"]).agg(
        pl.col("available_stock").sum(),
        pl.col("dead_stock").sum(),
        pl.col("capacity").sum(),
        pl.col("ullage").sum()
    ).drop_nulls() 

    res = products_data.join(ullage_data, 
                            on=["product", "date_time"], 
                            how="left"
                        ).drop_nulls()
    return {"status": True, "data": res.to_dicts(), "message": "data retrieved successfully"}


async def tank_analytics(filters, action, drill_state, cross_filters, payload):
    """
    get_tank_details api action function
    """
    # action map -> actions with common execution
    # sum_actions -> actions inside action map with total count output
    ACTION_MAP = tank_queries.ACTION_MAP
    SUM_ACTIONS = tank_queries.SUM_ACTIONS
    try:
        filter_conditions = await generate_filters_cond(filters)
        sap_id_filter = f"AND {filter_conditions['sap_id']}" if filter_conditions.get('sap_id', "") else ""
        zone_filter = f"AND {filter_conditions['zone']}" if filter_conditions.get('zone', "") else ""
        filter_clause = " AND ".join([value for key, value in filter_conditions.items()])
        print("filter clause -->", filter_clause)
        # filter_clause = " AND ".join(filter_conditions)

        #connection to db
        params = dashboard_studio_model.Charts_Connection_Vault_RoutingParams
        params.connection_id = 1
        params.action = 'execute_query'
        
        if action == "stock_sustainability":  
            return await action_stock_sustainability(sap_id_filter + zone_filter, params)   
            
        if action == "product_wise_trends":
            # add dead stock
            return await action_product_wise_trends(sap_id_filter + zone_filter, params)
    
        if action == "daily_trends":
            return await action_daily_trends(filter_clause, params)
        
        if action == 'daywise_trends': 
            return await action_daywise_trends(filter_clause, params)
        
        if action == 'total_capacity' or action == 'total_ullage':
            ullage = await tank_ullage(filter_clause=sap_id_filter + zone_filter, connection_params=params)
            data = ullage["ullage"].sum() if action == "total_ullage" else ullage['capacity'].sum()
            return {"status": True, "data": data, "message": "successfully retrieved data"}
        
        if action == 'net_stock':
            tank_data = await stock_dispatch_receipt(filter_clause=filter_clause, connection_params=params)
            net_stock = await calculate_net_stock(tank_data) 
            return{
                "status" : True,
                "data": net_stock,
                "message": "fetched data successfully"
            }
  
        query_key = ACTION_MAP[action]

        query_template = tank_queries.queries.get(query_key, '')
        query = query_template.format(filter_clause)

        function = await charts_actions.charts_connection_vault_routing(params)
        resp = await function(query=query)

        if action == 'total_product':
            resp = [
            {k: float(v) if isinstance(v, Decimal) else v for k, v in row.items()}
            for row in resp
            ]
            resp = pl.DataFrame(resp)
            resp = (
                resp.filter(pl.col("available_stock_kl") > 0)["available_stock_kl"].sum()
                if not resp.is_empty() else 0.0
            )
           

        if action in SUM_ACTIONS.keys():
            total = sum(row.get(SUM_ACTIONS.get(action, 'sum')) or 0 for row in resp)
            return {"status": True, "data": total, "message": "data fetched successfully"}

        return {"status": True, "data": resp, "message": "data fetched successfully"}

    except Exception as e:
        print(e)
        return {"status": False, "data": [], "message": f"error: {e}"}