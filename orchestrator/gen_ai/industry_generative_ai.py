import urdhva_base
import os
import hpcl_ceg_model
import orchestrator.gen_ai.sql_query_generator as sql_query_generator

pkl_file = f"{os.path.dirname(sql_query_generator.__file__)}/industry_performance.pkl"


async def generative_ai(prompt):
    sql_query = sql_query_generator.nl_to_sql(prompt, pkl_file)
    if sql_query and sql_query[-1] == ';':
        sql_query = sql_query[:-1]
    print(sql_query)
    resp = await hpcl_ceg_model.Alerts.get_aggr_data(sql_query, limit=0)
    return resp['data']
