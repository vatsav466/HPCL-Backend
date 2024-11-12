import api_manager


async def get_global_bu_statistics(bus: list):
    """
    Retrieves global statistics for specified business units.

    Parameters:
    bus (list): A list of business unit identifiers (IDs or names) to retrieve statistics for.

    Returns:
    dict: A dictionary containing aggregated statistics for each business unit in `bus`.

    Functionality:
    - Iterates through each business unit in the provided list.
    - For each business unit, fetches relevant statistics from the data source (database, API, etc.).
    - Aggregates and processes data to generate summary statistics for each business unit.
    - Formats the data into a dictionary structure to be returned to the caller.
    """
    resp_order = ['RO', 'TAS', 'LPG', 'CP', 'RDI']
    resp = {key: {"bu": key, "count": 0, "alerts_count": 0, "critical": 0, "high": 0, "medium": 0, "low": 0}
            for key in resp_order}
    query = "select bu,Count(*) from location_master group by bu"
    if bus:
        query += " AND".join(bus)
    query_resp = api_manager.hpcl_cng_model.LocationMasterCreate.get_aggr_data(query, limit=1000)
    alert_query = "select bu, severity, Count(*) from alerts group by bu, severity"
    if bus:
        query += " AND".join(bus)
    alert_resp = api_manager.hpcl_cng_model.LocationMasterCreate.get_aggr_data(alert_query, limit=1000)
    return resp
