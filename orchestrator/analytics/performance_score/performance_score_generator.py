import urdhva_base
import asyncio
import datetime
import pandas as pd
import hpcl_ceg_model
import performance_score_lpg as pslpg
import performance_score_sod as pssod
import orchestrator.analytics.va_analysis as va_analysis


def get_performance_score_instance(bu):
    if bu == 'LPG':
        return pslpg.LPGPerformanceScore()
    elif bu == 'TAS':
        return pssod.SODPerformanceScore()
    return None


async def fetch_va_score(bu):
    resp = await va_analysis.get_ro_terminal_scores({'LocationType': bu,
                                                     'StartDate': datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")})
    if resp['status']:
        va_score = {rec.get('LOCATION_ID', '').split(',')[-1].strip(): rec for rec in resp.get('data', []) if rec.get('LOCATION_ID', '')}
        return va_score
    return {}


async def generate_performance_score(bu, location_id=None):
    """Generating Performance Score per location for the given BU"""
    locations = []
    required_keys = ['sap_id', 'zone', 'region', 'name']
    if not location_id:
        query = f"""SELECT {','.join(required_keys)} from location_master where bu='{bu}' AND name not ilike '%import%'"""
    else:
        location_id = [location_id] if isinstance(location_id, str) else location_id
        location_id = ", ".join(f"'{value}'" for value in location_id)
        query = f"""SELECT {','.join(required_keys)} from location_master where bu='{bu}' AND 
        sap_id in ({location_id}) AND name not ilike '%import%'"""
    limit = 1000
    skip = 0

    # Listing all locations for the given BU
    while True:
        resp = await hpcl_ceg_model.LocationMaster.get_aggr_data(query, limit=limit, skip=skip)
        locations.extend(resp['data'])
        if len(resp['data']) < limit:
            break
        skip += 1

    # Getting PI Score class instance
    ins = get_performance_score_instance(bu)
    await ins.initialize()
    va_data = await fetch_va_score(bu)
    # generating performance score for every plant
    performance_score = {}
    present_timestamp = datetime.datetime.now(tz=datetime.timezone.utc)
    for location in locations:
        print("location --> ", location)
        # Generating performance score for each location
        print(f"Generating performance score for {location['sap_id']}")
        await ins.configure_va(va_data.get(location['sap_id']))
        response, _ = await ins.generate_performance_index(location['sap_id'])
        print("response --> ", response)
        score = sum([rec['score'] for rec in list(response.values())])
        performance_score[location['sap_id']] = {"sap_id": location['sap_id'],
                                                 "score": round(score if score < 100 else 100, 2),
                                                 "category": list(response.values()),
                                                 'timestamp': present_timestamp, "region": location["region"],
                                                 'bu': bu, "zone": location["zone"], "name": location["name"]}
    # Generating rank and national average
    df = pd.DataFrame(list(performance_score.values()))
    df = df[['sap_id', 'score']]
    df['rank'] = df['score'].rank(method='dense', ascending=False).astype(int)
    national_avg = round(float(df['score'].mean()), 2)
    for sap_id, rec in performance_score.items():
        performance_score[sap_id]['rank'] = int(df[df['sap_id'] == sap_id]['rank'].values[0])
        performance_score[sap_id]['national_score'] = national_avg
    performance_score = list(performance_score.values())
    print("performance_score --> ", performance_score)
    # Updating performance score to database
    await hpcl_ceg_model.PerformanceScore.bulk_update(performance_score.copy(), upsert=True)
    await hpcl_ceg_model.PerformanceScoreHistory.bulk_update(performance_score, upsert=False)
    return performance_score


async def main():
    supported_bus = ['LPG', 'TAS']
    for bu in supported_bus:
        await generate_performance_score(bu)


if __name__ == "__main__":
    asyncio.run(main())
