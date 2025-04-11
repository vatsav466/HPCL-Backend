zone_map = {
    "WZL": "WZ",
    "NWL": "NWZ",
    "EZL": "EZ",
    "NZL": "NZ",
    "NCL": "NCZ",
    "SZL": "SZ",
    "SCL": "SCZ",
    "SZ": "SZ",
    "EZ": "EZ",
    "SCZ": "SCZ",
    "NWZ": "NWZ",
    "NZ": "NZ",
    "NCZ": "NCZ",
    "WZ": "WZ",
    "NFZ": "NZ",
    "NWF": "NW",
    "NCR": "NCZ",
    "SCR": "SCZ",
    "NWR": "NWZ",
    "SC": "SCZ",
    "NW": "NWZ",
    "COR": "COR",
    "ECZ": "ECZ",
    "SWZ": "SWZ",
    "CEN": "CEN"
}

# Add required roles in novex_role_master.csv
lpg_query = """ SELECT distinct(ZE.EMPLOYEE_NUMBER) as EMPLOYEE_NUMBER, ZE.EMPLOYEE_NAME as EMPLOYEE_NAME,  ZE.EMP_EMAIL as EMP_EMAIL, 
                    ZE.EMP_BU_CODE,ZE.PLANT_CODE,ZE.PLANT_DESC,ZE.SALES_GRP, ZSA.SALES_GROUP_DESC,ZR.ROLE_NAME as ROLE_NAME, ZR.LOCATION as LOCATION, EPL.ZZONE as Zone
                FROM ZGRCCV_ROLE_STG ZR left JOIN ZHRCV_EMP_NONHCM_STG ZE on ZR.USER_NAME = ZE.EMPLOYEE_NUMBER 
                    LEFT JOIN ZMMCV_PLANT_STG EPL on ZR.LOCATION = EPL.PLANT
                    LEFT JOIN ZSDCV_SO_PARAM_STG ZSA on ZSA.SALES_GROUP = ZE.SALES_GRP
                WHERE ZR.LOCATION like '2%' """

# Add required roles in novex_role_master.csv
tas_query = f""" SELECT ZE.EMPLOYEE_NUMBER as EMPLOYEE_NUMBER, ZE.EMPLOYEE_NAME as EMPLOYEE_NAME,  ZE.EMP_EMAIL as EMP_EMAIL, 
                    ZE.EMP_BU_CODE,ZE.PLANT_CODE,ZE.PLANT_DESC, ZR.ROLE_NAME as ROLE_NAME, ZR.LOCATION as LOCATION, EPL.ZZONE as zone
                FROM ZGRCCV_ROLE_STG ZR LEFT JOIN ZHRCV_EMP_NONHCM_STG ZE on ZR.USER_NAME = ZE.EMPLOYEE_NUMBER 
                    LEFT JOIN EDW_DC_PLANT EPL on ZR.LOCATION = EPL.PLANT
                WHERE ZR.LOCATION like '1%' """

# Add required roles in novex_role_master.csv
ro_query = f""" SELECT distinct(ZE.EMPLOYEE_NUMBER) as EMPLOYEE_NUMBER, ZE.EMPLOYEE_NAME as EMPLOYEE_NAME,  ZE.EMP_EMAIL as EMP_EMAIL, 
                    ZE.EMP_BU_CODE,ZE.PLANT_CODE,ZE.PLANT_DESC,ZE.SALES_GRP, ZSA.SALES_GROUP_DESC,ZR.ROLE_NAME as ROLE_NAME, ZR.LOCATION as LOCATION, EPL.ZZONE as Zone
                FROM ZGRCCV_ROLE_STG ZR left JOIN ZHRCV_EMP_NONHCM_STG ZE on ZR.USER_NAME = ZE.EMPLOYEE_NUMBER 
                    LEFT JOIN ZMMCV_PLANT_STG EPL on ZR.LOCATION = EPL.PLANT
                    LEFT JOIN ZSDCV_SO_PARAM_STG ZSA on ZSA.SALES_GROUP = ZE.SALES_GRP
                WHERE ZR.LOCATION like '7%' """
# AND ZR.ROLE_NAME IN ('SD_RREGNL_MNGR','SD_RHQO_OFFICER','SD_RSALES_OFFICER','SD_RHQO_GMSALES')

# Zonal
# query = """ SELECT distinct(ZE.EMPLOYEE_NUMBER) as EMPLOYEE_NUMBER, ZE.EMPLOYEE_NAME as EMPLOYEE_NAME,  ZE.EMP_EMAIL as EMP_EMAIL,
#                 ZE.EMP_BU_CODE,ZE.PLANT_CODE,ZE.PLANT_DESC,ZE.SALES_GRP, ZSA.SALES_GROUP_DESC,ZR.ROLE_NAME as ROLE_NAME, ZR.LOCATION as LOCATION, EPL.ZZONE as Zone
#             FROM ZHRCV_EMP_NONHCM_STG ZE left JOIN ZGRCCV_ROLE_STG ZR on ZR.USER_NAME = ZE.EMPLOYEE_NUMBER 
#                 LEFT JOIN ZMMCV_PLANT_STG EPL on ZE.PLANT_CODE = EPL.PLANT
#                 LEFT JOIN ZSDCV_SO_PARAM_STG ZSA on ZSA.SALES_GROUP = ZE.SALES_GRP
#             WHERE ZR.ROLE_NAME IN ('SD_LZONAL_HEAD') """

required_field = ["bu", "sap_id", "name", "city", "district", "region", "sales_area", "state", "zone", "adress"]

_rename = {"PLANT": "sap_id", "PLANT_DESC": "name", "ZZONE": "zone", "STATE_NAME": "state", 
           "SALES_OFFICE_DESC": "region", "SALES_GROUP_DESC": "sales_area", "CITY1": "city", 
           "POST_CODE1": "pincode", "STREET": "land_mark", "STR_SUPPL1": "location"}

location_configs = [
    {
        "bu": "lpg",
        "query": """
                SELECT * 
                    FROM 
                    EDW_DC_PLANT PLT
                    LEFT JOIN ZSDCV_SO_PARAM_STG ZN ON PLT.PLANT = ZN.PLANT
                WHERE 
                    ZLOC_TYPE IN ('33');
                """,
        "reporting_office_query":""" 
                SELECT * 
                    FROM 
                    EDW_DC_PLANT PLT
                    LEFT JOIN ZSDCV_SO_PARAM_STG ZN ON PLT.PLANT = ZN.PLANT
                WHERE 
                    ZLOC_TYPE IN ('68');
                """
    },
    {
        "bu": "tas",
        "query": """
                SELECT * 
                    FROM 
                    EDW_DC_PLANT PLT
                    LEFT JOIN ZSDCV_SO_PARAM_STG ZN ON PLT.PLANT = ZN.PLANT
                WHERE 
                    PLT.SBU='RET' AND CODE2 IN ('O&D','QC') AND ZLOC_TYPE!='66' AND FACILITY!='13';
                """,
        "reporting_office_query": """ 
                SELECT * 
                    FROM 
                    EDW_DC_PLANT PLT
                    LEFT JOIN ZSDCV_SO_PARAM_STG ZN ON PLT.PLANT = ZN.PLANT
                WHERE
                    ZLOC_TYPE IN ('38');
                """
    }   
]