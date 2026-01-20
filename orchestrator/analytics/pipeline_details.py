import asyncio


async def get_pipeline_locations():
    # All pipeline details provided by HPCL
    # Todo:- Need to create mapping through nginx instead of allowing to browse from here
    pipeline_details = [
        {
            "name": "MPSPL",
            "url": "http://10.2.64.45",
            "description": "Mumbai Pune Solapur Pipeline (MPSPL), 508 km (MPPL 162km + PSPL 346km), commissioned Dec 1985/Nov 2006, from Trombay through Vashi-Khopoli-Talegaon-Loni to Vashi, Loni, Hazarwadi, Pakni terminals. Transports MS-BSVI, SKO, HSD-BSVI, ATF (4.3 MMT capacity)."
        },
        {
            "name": "VVSPL",
            "url": "http://10.4.80.10",
            "description": "Visakha Vijayawada Secunderabad Pipeline (VVSPL), 572 km (VVPL 349km + VSPL 224km), commissioned May 1998/Mar 2002, from Visakha through MB Patnam-Rajahmundry-JK Gudem-Vijayawada-Suryapet-Bhogaram to Rajahmundry, Vijayawada, Suryapet, Secunderabad. Transports MS-BSVI, SKO, ATF, HSD-BSVI (7.7 MMT)."
        },
        {
            "name": "MDPL",
            "url": "http://10.2.114.40/detail.aspx",
            "description": "Mundra Delhi Pipeline (MDPL), 1054 km mainline (18\" 979km + 16\" 74km), commissioned May 2007, from Mundra through BIPS-SIPS-PIPS-AIPS to PRPS, VRS, SRS, ARPS, JRPS terminals across Gujarat-Rajasthan-Haryana. Transports SKO, HPCK, HSD, MS, LAN (6.9 MMT)."
        },
        {
            "name": "RBPL",
            "url": "http://10.1.126.252/ggsr/Overview.aspx",
            "description": "Ramanmandi Bahadurgarh Pipeline (RBPL), 243 km, commissioned Aug 2012, from Ramanmandi Dispatch (Punjab) through Barwala IPS to Hisar, Bahadurgarh terminals (Punjab-Haryana). Transports MS-BSVI, SKO, SSKO, HSD-BSVI (7.11 MMT)."
        },
        {
            "name": "RKPL",
            "url": "http://10.1.28.80:8080/home.aspx",
            "description": "Rewari Kanpur Pipeline (RKPL), 443 km, commissioned Oct 2015, from RRPS (Rewari) to Bharatpur, Mathura, Kanpur terminals spanning Haryana-Rajasthan-Uttar Pradesh. Transports MSVI, HSDVI, SSKO, SKO (4.3 MMT)."
        },
        {
            "name": "MHMSPL",
            "url": "http://10.4.75.47:8080/mobileoperator/",
            "description": "Mangalore Hassan Mysore Bangalore Pipeline (MHMBPL), 357 km, from Mangalore through Neriya-Hassan IPS to Mysore, Yediyur terminals (Karnataka). LPG pipeline with 3.1 MMT capacity."
        },
        {
            "name": "UCSPL",
            "url": "http://10.2.93.9",
            "description": "Uran Chakan Shikrapur Pipeline (UCSPL), 169 km total (Uran-Shikrapur 157km + SV-11 Chakan 7km + SV-13 Chakan 5km), commissioned Nov 2019, from Uran Dispatch to Chakan, Shikrapur receiving stations (Maharashtra). LPG pipeline (1.16 MMT)."
        },
        {
            "name": "VDPL",
            "url": "http://10.4.61.70:8080/default.aspx",
            "description": "Vijayawada Dharmapuri Pipeline (VDPL), 699 km, commissioned Mar 2023, from Visakha/Vijayawada through Donokonda-Kadapa-Kalakada to Kadapa & Dharmapuri terminals (Andhra Pradesh-Tamilnadu). Transports MS-BSVI, HPCK, HSD-BSVI (4.24 MMT)."
        }
    ]

    return {'status':True, 'message':'Success', 'data':pipeline_details}
