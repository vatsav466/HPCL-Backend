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
    "NWF": "NWZ",
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

required_field = ["bu", "sap_id", "name", "city", "district", "region", "sales_area", "state", "zone", "adress", "pincode", "terminal_plant_id", "dealer_phone","dealer_email"]

_rename = {"PLANT": "sap_id", "PLANT_DESC": "name", "ZZONE": "zone", "STATE_NAME": "state", 
           "SALES_OFFICE_DESC": "region", "SALES_GROUP_DESC": "sales_area", "CITY1": "city", 
           "POST_CODE1": "pincode", "STREET": "land_mark", "STR_SUPPL1": "location"}

location_configs = [
    {
        "bu": "lpg",
        "query": """
                SELECT 
                    PLT.PLANT, PLT.PLANT_DESC, PLT.ZZONE, PLT.CITY1, PLT.POST_CODE1,PLT.STREET,
                    PLT.STR_SUPPL1, PLT.REPORTING_OFFICE, PLT.STATE_NAME
                FROM
                    EDW_DC_PLANT PLT
                    LEFT JOIN ZSDCV_SO_PARAM_STG ZN ON PLT.PLANT = ZN.PLANT
                WHERE
                    ZLOC_TYPE IN ('33');
                """,
        "reporting_office_query":"""
                    SELECT
                        PLT.PLANT AS RO_CODE, ZN.SALES_OFFICE_DESC, ZN.SALES_GROUP_DESC
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
                SELECT
                    PLT.PLANT, PLT.PLANT_DESC, PLT.ZZONE, PLT.CITY1, PLT.POST_CODE1,PLT.STREET,
                    PLT.STR_SUPPL1, PLT.REPORTING_OFFICE, PLT.STATE_NAME
                FROM
                    EDW_DC_PLANT PLT
                    LEFT JOIN ZSDCV_SO_PARAM_STG ZN ON PLT.PLANT = ZN.PLANT
                WHERE 
                    PLT.SBU='RET' AND CODE2 IN ('O&D','QC') AND ZLOC_TYPE!='66' AND FACILITY!='13';
                """,
        "reporting_office_query": """ 
                SELECT
                    PLT.PLANT AS RO_CODE, ZN.SALES_OFFICE_DESC, ZN.SALES_GROUP_DESC
                FROM
                    EDW_DC_PLANT PLT
                    LEFT JOIN ZSDCV_SO_PARAM_STG ZN ON PLT.PLANT = ZN.PLANT
                WHERE
                    ZLOC_TYPE IN ('38');
                """
    },
    {
        "bu": "ro",
        "query": """
                SELECT
                    zca.customer AS PLANT, zcs.name1 AS PLANT_DESC, zca.sales_district, zso.sales_district_desc, zca.deliv_plant AS terminal_plant_id,
                    zso.SALES_OFFICE_DESC, zso.SALES_GROUP_DESC, plt.ZZONE, zcs.CITY AS CITY1, zcs.POSTAL_CODE AS POST_CODE1, zcs.ADDRESS1, zcs.ADDRESS2, zcs.ADDRESS3, zcs.ADDRESS4,
                    zcs.ADDRESS5, plt.PLANT_DESC AS terminal_plant_name, plt.STATE_NAME, zcs.first_telephone_number AS dealer_phone,
                    zcs.second_tel_no, zcs.email_id AS dealer_email, zca.inactive, zcs.OUTLET_TYPE, zcs.gstin, zcs.mrn, zcs.OUTLET_TYPE, zcs.gstin,
                    zcs.mrn, zcs.permanent_Account_number
                FROM ZSDCV_CUST_SA_STG zca 
                    INNER join ZSDCV_CUSTOMER_STG zcs on zcs.customer_number = zca.customer 
                    INNER join ZSDCV_SO_PARAM_STG zso on zso.sales_district = zca.sales_district AND
                    zso.sales_org=zca.sales_org AND zso.sales_office=zca.sales_off AND zso.sales_group=zca.sales_grp
                    INNER join EDW_DC_PLANT plt on zso.PLANT=plt.PLANT
                WHERE 
                    zca.deliv_plant <> '' AND zca.sales_org='7000' AND zca.DIST_CHANNEL=11 AND zca.division in (11,12) AND
                    zca.customer BETWEEN 4000000 AND 49999999 AND zca.INACTIVE=''
                ORDER BY zca.deliv_plant,zso.plant_desc,zca.sales_off,zso.sales_office_desc,zca.sales_grp,zso.sales_group_desc
                 """
    }
]