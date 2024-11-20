from dashboard_studio_enum import *
from dashboard_studio_model import *
from hpcl_ceg_model import *
import fastapi
import json
import httpx
import base64
import traceback
import hpcl_ceg_model
import urdhva_base.redispool
import urdhva_base.context
from orchestrator.dashboard.chart_factory import charts_functions
from orchestrator.dashboard.chart_factory import charts_helpers
from orchestrator.dashboard.chart_factory import JSONHashing
from orchestrator.dashboard.chart_factory import date_actions

router = fastapi.APIRouter(prefix='/charts')


# Action get_tables
@router.post('/get_tables', tags=['Charts'])
async def charts_get_tables(data: Charts_Get_TablesParams):
    '''
    Description:
        Retrieves the tables from the given database and schema
    Input:
        {
            "database": "zolix_c2o",
            "schema": "public"
        }
    Returns: 
        List: A list of table names
    Output:
        ["organization","credential_vault","billing_cost","cloud_accounts","recommendations","metrics"]
    '''
    async_session = await charts_functions.check_db(data.database)
    session = async_session()
    try:
        tables_list = await charts_functions.getTables(session, data.schema)
        return {"status": True, "message": "success", "data": tables_list}
    except Exception as e:
        return {"status": False, "message": str(e), "data": []}
    finally:
        await session.close()


# Action get_columns
@router.post('/get_columns', tags=['Charts'])
async def charts_get_columns(data: Charts_Get_ColumnsParams):
    '''
    Description:
        Retrieves the column names from the given table, schema and database
    Input:
        {
            "database": "zolix_c2o",
            "schema": "public",
            "table": "recommendations"
        }
    Returns:
        List: A list of column names
    Output:
        ["resource_type","cloud_account_id","cloud_account_name","tenant_id"]
    '''

    async_session = await charts_functions.check_db(data.database)
    if not async_session:
        return {"status": False, "message": "check the database name", "data": []}
    session = async_session()
    try:
        columns_list = await charts_functions.getColumns(session, data.schema, data.table)
        if not columns_list:
            return {"status": False, "message": "check the table or schema name", "data": []}
        columns_mapping_list = [{"name": col[0],"display_name": col[0].replace("_", " ").title() ,"type": col[1]} for col in columns_list]
        return {"status": True, "message": "success", "data": columns_mapping_list}
    except Exception as e:
        return {"status": False, "message": str(e), "data": []}
    finally:
        await session.close()


@router.post('/get_databases', tags=['Charts'])
async def get_databases():
    """
    Description:
        Retrieves the available databases
    Returns:
        List of databases
    Output:
        ["database1","database2","database3 "]
    """
    database_list = await charts_functions.get_dbs()
    if not database_list:
        return {"status": False, "message": "Failed to get databases", "data": []}
    return {"status": True, "message": "success", "data": database_list}


# Action get_unique_values
@router.post('/get_unique_values', tags=['Charts'])
async def charts_get_unique_values(data: Charts_Get_Unique_ValuesParams):
    '''
    Description:
        Retrives unique values of the given column names
    Input:
        {
            "database": "zolix_c2o",
            "schema": "public",
            "table": "recommendations",
            "column": ["resource_type"]
        }
    Returns:
        Dictionary: A dictionary of column as a key and its respective unique values as value
    Output:
        {"jobStatus":["Success","Failed","Running","RolledBack"]}
    '''

    async_session = await charts_functions.check_db(data.database)
    if not async_session:
        return {"status": False, "message": "check the database name", "data": []}
    session = async_session()
    try:
        columns_mapping = await charts_functions.getUniqueValues(session, data.schema, data.table, data.column)
        if not columns_mapping:
            return {"status": False, "message": "check the table or column name", "data": []}
        return {"status": True, "message": "success", "data": columns_mapping}
    except Exception as e:
        return {"status": False, "message": str(e), "data": []}
    finally:
        await session.close()


# Action create_charts
@router.post('/chart', tags=['Charts'])
async def create_charts(data: ChartsCreate):
    """
    Description:
        Retrieves data as per the model and return the data in the respective chart format
    Input:
        Look into the model 'ChartsCreate'
    Returns:
        List of dictionaries
    Output:
        {"data":[{}]}
    """

    viztype = data.visualization_name
    if not data.table:
        data.table = "zolix_c2o"
    if not data.schema:
        data.schema = "public"
    chart_data_str = await charts_functions.retrieve_data(viztype, data)
    if not isinstance(chart_data_str, dict):
        chart_data = json.loads(chart_data_str)
    chart_data = chart_data_str
    if not chart_data['status']:
        return {"status": False, "message": str(chart_data['message']), "data": chart_data['data']}
    if viztype in ['bar', 'line', 'area', 'custom_bar', 'time_series_bar']:
        return {"status": True, "message": "success", "query":chart_data['query'],"x_axis": chart_data['x_axis'], "data": chart_data['data']}
    return {"status": True, "message": "success", "query":chart_data['query'], "data": chart_data['data']}


@router.post('/get_drill_down_data', tags=['Charts'])
async def drill_down_data(data: Charts_Drill_Down_DataParams):
    """
    Description:
        Retrieves data as per the model and return the data in the respective chart format
    Input:
        Look into the model 'Drill_Down_DataParams'
    Returns:
        List of dictionaries
    Output:
        {"data":[{}]}
    """
    table_name = data.table
    table_schema = data.schema
    filter_mapping = data.filter_mapping
    limit = 1000
    return {
        "status": True, "message": "success", "data": await charts_functions.get_drill_down_data(
            table_name, table_schema, filter_mapping, limit
        )
    }


@router.post('/dashboard_charts', tags=['Charts'])
async def dashboard_charts(data: Charts_Dashboard_ChartsParams):
    """
    Description:
        Retrieves data as per the model and return the data in the respective chart format
    Input:
        Look into the model 'DashBoard_ChartsParams'
    Returns:
        List of dictionaries
    Output:
        {"data":[{}]}
    """
    return {
        "status": True, "message": "success", "data": await charts_functions.get_list_of_charts()
    }


@router.post('/get_chart_form', tags=['Charts'])
async def get_dashboard_chart_form(data: Charts_Get_Dashboard_Chart_FormParams):
    """
    Description:
        Retrieves data as per the model and return the data in the respective chart format
    Input:
        Look into the model 'Get_Chart_DataParams'
    Returns:
        List of dictionaries
    Output:
        {"data":[{}]}
    """
    return {
        "status": True, "message": "success", "data": await charts_functions.get_chart_data(data.unique_id)
    }


@router.post('/get_distinct_values', tags=['Charts'])
async def charts_get_distinct_values(data: Charts_Get_Distinct_ValuesParams):
    """
    Description:
        Retrives unique values of the given column names
    Input:
        {
            "database": "zolix_c2o",
            "schema": "public",
            "table": "recommendations",
            "column": ["resource_type"]
        }
    Returns:
        Dictionary: A dictionary of column as a key and its respective unique values as value
    Output:
        {"jobStatus":["Success","Failed","Running","RolledBack"]}
    """

    async_session = await charts_functions.check_db(urdhva_base.settings.db_urls['postgres_async'][0].path[1:])
    if not async_session:
        return {"status": False, "message": "check the database name", "data": []}
    session = async_session()
    try:
        columns_mapping = await charts_functions.getUniqueValues(session, "public", data.table, data.column, data.where_cond)
        if not columns_mapping:
            return {"status": False, "message": "check the table or column name", "data": []}
        return {"status": True, "message": "success", "data": columns_mapping}
    except Exception as e:
        return {"status": False, "message": str(e), "data": []}
    finally:
        await session.close()


# Action drill_down_data
@router.post('/drill_down_data', tags=['Charts'])
async def charts_drill_down_data(data: Charts_Drill_Down_DataParams):
    ...


# Action generate_dynamic_chart_query
@router.post('/generate_dynamic_chart_query', tags=['Charts'])
async def charts_generate_dynamic_chart_query(data: Charts_Generate_Dynamic_Chart_QueryParams):
    """
    Description:
        This function will generate NLP queries by using the trained model in openai
    Input:
        {
            "query_context": "<NLP Query String>",
        }
    Returns:
        Dictionary: A dictionary of column as a key and its respective unique values as value
    Output:
        {"jobStatus":["Success","Failed","Running","RolledBack"]}
    """
    redis_ins = await urdhva_base.redispool.get_redis_connection()
    if not data.query_context:
        return False, "Invalid inputs"

    redis_key = base64.b64encode("_".join(data.query_context.lower().split()).encode()).decode()
    if await redis_ins.hexists("nlp_cache", redis_key):
        nlp_data = await redis_ins.hget("nlp_cache", redis_key)
        return True, json.loads(nlp_data)

    base_url = "https://api.openai.com/v1/completions"

    # Encrypted key
    nlp_key = ('c2stcHJvai11NHNBWmJsTy1CWDVBaVZwUl95aEwwWjlzSkhJT0ZXV2NMU1FPTW9FaGxnLWZKd2NsZi0wQ3NuQ'
               '2xpVkRsUXhaLWwwLXlWV2htN1QzQmxia0ZKVTVhM1F3ejRud0tWTlF1N0IxeHM3d1pyTUpNZEVQTTBsMTVTdDlx'
               'QTZpbWlnaERETWdoM0cxQUFYQXFwSXZlbE1sQm82YUNIZ0E=')

    # Creating authentication headers
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {base64.b64decode(nlp_key.encode()).decode()}"
    }

    # Generating json data required for data query
    input_context = {
        "model": "ft:davinci-002:personal::AKgLf2q5", "prompt": data.query_context, "temperature": 1,
        "max_tokens": 512, "top_p": 1, "frequency_penalty": 0, "presence_penalty": 0
    }

    # Running http request for fetching data from base url
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(base_url, headers=headers, json=input_context, timeout=120)
            if resp.status_code // 100 != 2:
                return False, "Error getting data, Please retry after few seconds"
            response = resp.json()
            if not response.get("choices"):
                return False, "Error: The response does not contain valid choices."
            if not response['choices'][0].get('text'):
                return False, "Error: The first choice does not contain a 'text' field."

            # Extract the text from the first choice
            result_text = response['choices'][0]['text']

            # Try to parse the result as JSON
            try:
                context_result = json.loads(result_text)
                context_result["database"] = urdhva_base.settings.db_urls['postgres_async'][0].path.split("/")[-1]
                context_result["schema"] = "public"
                await redis_ins.hset("nlp_cache", redis_key, json.dumps(context_result))
                return True, context_result
            except json.JSONDecodeError as e:
                print(f"Exception while decoding response {e}, Traceback: {traceback.format_exc()}")
                return False, ("Error: The response text is not a valid JSON object. "
                               "Please try again with a different prompt.")
    except httpx._exceptions.TimeoutException as e:
        print(f"Exception while getting response {e}")
        return False, "Response timedout"
    except Exception as e:
        print(f"Exception while running openai api {e}, Traceback: {traceback.format_exc()}")
        return False, f"Error: Request failed due to {str(e)}"

# Action save_charts
@router.post('/save_charts', tags=['Charts'])
async def charts_save_charts(data: Charts_Save_ChartsParams):
    """
    Description:
        This function will save the chart if no record id and update the chart if record id
    Input:
        Charts_Save_ChartsParams
    Returns:
        A dictionary of status and message
    Output:
        {"status":True, "message": "Chart Data Created"}
    """
    if urdhva_base.context.context.exists():
        rpt = urdhva_base.context.context.get('rpt', {})
    else:
        rpt = {}
    created_by = rpt.get('email', 'system')
    created_user = rpt.get('given_name', 'Zolix') +' '+ rpt.get('family_name', 'Engine')
    data.created_by = created_by
    data.created_user = created_user
    fields_included_in_hash = ['database', 'schema', 'table', 'visualization_name', 'type', 'created_by']
    filtered_fields = {field: getattr(data, field) for field in fields_included_in_hash if hasattr(data, field)}
    chart_params = {"params": data.params.dict()}
    filtered_fields.update(chart_params)
    hashed_value = JSONHashing.generate_json_hash(filtered_fields)
    data.hashed_value = hashed_value
    if data.group_id == 0:
        grp_data = GroupsCreate(**{"name": data.group_name, "created_by": data.created_by,
                                   "created_user": data.created_user, "organization_id": data.organization_id})
        collected  = await grp_data.create()
        print("collected create: ", collected)
        print("Groups created")
        data.group_id = collected['id'] if isinstance(collected, dict) else collected.id
    else:
        grp_data = Groups(**{"id": data.group_id, "name": data.group_name,
                             "created_by": data.created_by, "created_user": data.created_user,
                             "organization_id": data.organization_id})
        await grp_data.modify()
        collected = grp_data
        print("collected modified: ", collected)
        print("Groups modified")

    if data.record_id:
        chart_data = data.dict()
        chart_data.update({"id": data.record_id, "params": data.params.dict()})
        chart_data = Charts(**chart_data)
        await chart_data.modify()
        message = "Chart Data Modified"

    else:
        chart_data = data.dict()
        chart_data.update({"params": data.params.dict()})
        chart_data = ChartsCreate(**chart_data)
        await chart_data.create()
        message = "Chart Data Created"

    return {"status": True, "message": message}

# Action get_time_range
@router.post('/get_time_range', tags=['Charts'])
async def charts_get_time_range(data: Charts_Get_Time_RangeParams):
    """
    Description:
        This function will provide the time range data
    Input:
        {
            "text": "Last week"
        }
    Returns:
        A dictionary of time range
    Output:
        {
          "since": "2024-10-22T00:00:00",
          "until": "2024-10-29T00:00:00",
          "timeRange": "Last week",
          "shift": null
        }
    """
    return await date_actions.time_range(**data.dict())


# Action dashboard_charts
@router.post('/dashboard_charts', tags=['Charts'])
async def charts_dashboard_charts(data: Charts_Dashboard_ChartsParams):
    ...


# Action get_dashboard_chart_form
@router.post('/get_dashboard_chart_form', tags=['Charts'])
async def charts_get_dashboard_chart_form(data: Charts_Get_Dashboard_Chart_FormParams):
    ...


# Action get_distinct_values
@router.post('/get_distinct_values', tags=['Charts'])
async def charts_get_distinct_values(data: Charts_Get_Distinct_ValuesParams):
    ...


# Action get_auto_complete_text
@router.post('/get_auto_complete_text', tags=['Charts'])
async def charts_get_auto_complete_text(data: Charts_Get_Auto_Complete_TextParams):
    """
   Description:
       This function will provide the text based on the prompt
   Input:
       {
        "prompt" : "top"
       }
   Returns:
       List of texts that contains prompt
   Output:
      [
        "Display the total billing amount for the top 30 regions and components, grouped by region and component",
        "Display the total billing amount for the top 30 regions and components, grouped by region and component in a pivot table format.",
      ]
   """
    return await charts_functions.generate_auto_complete_text(data.prompt)
