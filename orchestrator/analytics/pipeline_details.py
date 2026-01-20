import asyncio


async def get_pipeline_locations():
    # All pipeline details provided by HPCL
    # Todo:- Need to create mapping through nginx instead of allowing to browse from here
    pipeline_details = [
        {"name": "MPSPL", "url": "http://10.2.64.45"},
        {"name": "VVSPL", "url": "http://10.4.80.10"},
        {"name": "MDPL", "url": "http://10.2.114.40/detail.aspx"},
        {"name": "RBPL", "url": "http://10.1.126.252/ggsr/Overview.aspx"},
        {"name": "RKPL", "url": "http://10.1.28.80:8080/home.aspx"},
        {"name": "MHMSPL", "url": "http://10.4.75.47:8080/mobileoperator/"},
        {"name": "UCSPL", "url": "http://10.2.93.9"},
        {"name": "VDPL", "url": "http://10.4.61.70:8080/default.aspx"}
    ]
    return {'status':True, 'message':'Success', 'data':pipeline_details}
