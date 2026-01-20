import asyncio


async def get_pipeline_locations():
    # All pipeline details provided by HPCL
    # Todo:- Need to create mapping through nginx instead of allowing to browse from here
    pipeline_details = [
        {
            "name": "MPSPL",
            "url": "http://10.2.64.45",
            "description": "Mumbai Pune Solapur Pipeline (MPSPL), ~508 km originating from Mumbai Refinery, spans Maharashtra transporting MS, HSD, ATF to Pune and Solapur terminals."
        },
        {
            "name": "VVSPL",
            "url": "http://10.4.80.10",
            "description": "Vizag Vijayawada Secunderabad Pipeline (VVSPL), ~572 km from Visakhapatnam Refinery, covers Andhra Pradesh and Telangana for MS, HSD, SKO delivery with extensions to Dharmapuri."
        },
        {
            "name": "MDPL",
            "url": "http://10.2.114.40/detail.aspx",
            "description": "Mundra Delhi Pipeline (MDPL), ~1054 km major cross-country line from Mundra to Delhi terminals, handles multi-products including MS and HSD across Gujarat, Rajasthan, Haryana."
        },
        {
            "name": "RBPL",
            "url": "http://10.1.126.252/ggsr/Overview.aspx",
            "description": "Ramanmandi-Bahadurgarh Pipeline (RBPL), 243 km from Bhatinda (Punjab) to Haryana, evacuates 4.71 MMTPA of MS, HSD, SKO, ATF from GGSR."
        },
        {
            "name": "RKPL",
            "url": "http://10.1.28.80:8080/home.aspx",
            "description": "Rewari Kanpur Pipeline (RKPL), ~443 km connects Rewari (Haryana) to Kanpur (UP) for POL products like MS and HSD, enhancing northern inland supply."
        },
        {
            "name": "MHMSPL",
            "url": "http://10.4.75.47:8080/mobileoperator/",
            "description": "Mangalore-Hassan-Mysore-Solur LPG Pipeline (MHMSPL), ~356 km from Mangalore Refinery through Karnataka to bottling plants at Mysore and Solur/Yediyur."
        },
        {
            "name": "UCSPL",
            "url": "http://10.2.93.9",
            "description": "Uran-Chakan-Shikrapur LPG Pipeline (UCSPL), ~169 km joint HPCL-BPCL line from Uran (Raigad) to Pune bottling plants at Chakan and Shikrapur."
        },
        {
            "name": "VDPL",
            "url": "http://10.4.61.70:8080/default.aspx",
            "description": "Vijayawada Dharmapuri Pipeline (VDPL), ~679 km extension of VVSPL from Vijayawada to new Dharmapuri terminal, commissioned around 2022 for product evacuation."
        }
    ]
    return {'status':True, 'message':'Success', 'data':pipeline_details}
