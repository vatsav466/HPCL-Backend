import pickle
import re


def extract_parameters(query):
    """Extract parameters from the natural language query"""
    params = {}
    
    # Extract company name
    companies = ['IOCL', 'BPCL', 'HPCL']
    for company in companies:
        if company in query:
            params['COMPANY'] = company
            break
    
    # Extract SBU
    sbus = ['I&C', 'RETAIL', 'LPG', 'AVIATION', 'LUBES', 'PETCHEM', 'GAS']
    for sbu in sbus:
        if sbu.lower() in query.lower():
            params['SBU'] = sbu
            break
    
    # Extract year
    year_match = re.search(r'(\d{4}-\d{4})', query)
    if year_match:
        params['YEAR'] = year_match.group(1)
    else:
        params['YEAR'] = '2024-2025'  # Default to current year
    
    return params


def nl_to_sql(natural_language_query, model_path):
    # Load the model
    with open(model_path, 'rb') as f:
        pipeline = pickle.load(f)
    
    # Predict the SQL template
    template = pipeline.predict([natural_language_query])[0]
    
    # Extract parameters from the query
    params = extract_parameters(natural_language_query)
    
    # Replace placeholders with actual values
    sql_query = template
    for param, value in params.items():
        sql_query = sql_query.replace(f"'{param}'", f"'{value}'")
    
    return sql_query
