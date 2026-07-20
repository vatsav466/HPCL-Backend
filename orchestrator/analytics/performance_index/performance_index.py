import asyncio
import orchestrator.analytics.performance_index.tas_performance_index as tas_pi


async def generate_operation_performance_index(bu, location_id):
    if bu == "TAS":
        return await tas_pi.TASPerformanceIndex().generate_performance_index(
            location_id
        )
    # elif bu == "CP":
    #     return await cp_pi.CPPerformanceIndex().generate_performance_index(location_id)
    # elif bu == "LPG":
    #     return await lpg_pi.LPGPerformanceIndex().generate_performance_index(location_id)
    # elif bu == "RO":
    #     return await ro_pi.ROPerformanceIndex().generate_performance_index(location_id)
    else:
        return 0


async def performance_index_calculator():
    # for bu in ['TAS', 'LPG', 'RO']:
    for bu in ["TAS"]:
        locations = []
        # Get locations
        for location in locations:
            await generate_operation_performance_index(bu, location)


if __name__ == "__main__":
    asyncio.run(performance_index_calculator())
