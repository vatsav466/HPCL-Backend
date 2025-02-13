"""
import polars as pl

df = pl.read_excel("/Users/mac_1/Downloads/Raw_Location_Master/CRIS_All_Sites.xlsx").with_columns(pl.all().cast(pl.Utf8, strict=False))
df1 = pl.read_excel("/Users/mac_1/Downloads/Raw_Location_Master/Retail_Export_Purushotam.xls").with_columns(pl.all().cast(pl.Utf8, strict=False))

merge = df.join(df1, left_on="RO SAP Code", right_on="DEALER_CODE", how="outer")

merge.write_csv("/Users/mac_1/Downloads/CRIS_All_Sites_new.csv")
"""

"""
import polars as pl

df = pl.read_csv("/Users/mac_1/Downloads/CRIS_All_Sites_new.csv").with_columns(pl.all().cast(pl.Utf8, strict=False))
df1 = pl.read_excel("/Users/mac_1/Downloads/Raw_Location_Master/HPCL_Site_GeoCoordinates copy.xlsx", sheet_name='Retails').with_columns(pl.all().cast(pl.Utf8, strict=False))

merge = df.join(df1, left_on="RO Code", right_on="SiteCode", how="outer")

merge.write_csv("/Users/mac_1/Downloads/CRIS_All_Sites_new.csv")
"""

"""

import polars as pl

df = pl.read_csv("/Users/mac_1/Downloads/CRIS_All_Sites_new.csv").with_columns(pl.all().cast(pl.Utf8, strict=False))
df1 = pl.read_excel("/Users/mac_1/Downloads/Raw_Location_Master/HPCL_Site_GeoCoordinates copy.xlsx", sheet_name='SOD').with_columns(pl.all().cast(pl.Utf8, strict=False))

merge = df.join(df1, left_on="LOCN_CODE", right_on="SiteCode", how="outer")

merge.write_csv("/Users/mac_1/Downloads/CRIS_All_Sites_new.csv")

"""

"""
LPG Location Master 

import polars as pl
geo_df = pl.read_excel("/Users/mac_1/Downloads/HPCL/Raw_Location_Master/HPCL_Site_GeoCoordinates.xlsx", sheet_name="LPG")
lpg_df = pl.read_csv("/Users/mac_1/Downloads/HPCL/Raw_Location_Master/Inserted_to_db/LPG_LocationMaster.csv")

merge = geo_df.join(lpg_df, left_on="SiteCode", right_on="LocationID", how="left")
merge.write_csv("/Users/mac_1/Downloads/HPCL/Raw_Location_Master/HPCL_lpg_matched.csv")

"""




"""

ROLE MASTER MAPPING
"""
import polars as pl

sod = pl.read_csv("/Users/mac_1/Downloads/HPCL/ROLE_MASTERS/SOD_ROLE_MASTER.csv", infer_schema_length=0)
print(sod["LOCATION"].unique().to_list())
lpg = pl.read_csv("/Users/mac_1/Downloads/HPCL/ROLE_MASTERS/LPG_ROLE_MASTER.csv", infer_schema_length=0)
print(lpg["LOCATION"].unique().to_list())
role_mapping = pl.read_csv("/Users/mac_1/Downloads/HPCL/ROLE_MASTERS/RoleMapping.csv", infer_schema_length=0)

sod_locwise_zone = pl.read_csv("/Users/mac_1/Downloads/HPCL/ROLE_MASTERS/SOD.csv", infer_schema_length=0)
lpg_locwise_zone = pl.read_csv("/Users/mac_1/Downloads/HPCL/ROLE_MASTERS/LPG.csv", infer_schema_length=0)

print(sod.columns, len(sod))
print(lpg.columns, len(lpg))
print(role_mapping.columns, len(role_mapping))
print(sod_locwise_zone.columns, lpg_locwise_zone.columns)

sod = sod.join(sod_locwise_zone, left_on="LOCATION", right_on="sap_id", how="left")

lpg = lpg.join(lpg_locwise_zone, left_on="LOCATION", right_on="sap_id", how="left")

rem_sod_plant_id = sod.with_columns(
    pl.when(pl.col("ROLE_NAME").str.contains(r"(MANAGER|DGM|GM|ED|SRMNGR)"))
    .then(pl.lit(None))
    .otherwise(
        pl.when(pl.col("ROLE_NAME").str.contains("ZONE"))
        .then(pl.lit(None))
        .otherwise(pl.col("LOCATION"))
    )
    .alias("LOCATION"),

    pl.when(pl.col("ROLE_NAME").str.contains(r"(MANAGER|DGM|GM|ED|SRMNGR)"))
    .then(pl.lit(None))
    .otherwise(pl.col("Zone"))
    .alias("Zone")
)

print("rem_sod_plant_id", rem_sod_plant_id["ROLE_NAME", "LOCATION"].unique().to_dict())

rem_lpg_plant_id = lpg.with_columns(
    pl.when(pl.col("ROLE_NAME").str.contains("ZONE")).then(pl.lit(None)).otherwise(pl.col("LOCATION")).alias("LOCATION")
    )
print("rem_lpg_plant_id", rem_lpg_plant_id["ROLE_NAME", "LOCATION"].unique().to_dict())

rem_sod_plant_id = rem_sod_plant_id.with_columns(
    pl.when((pl.col("Zone").is_not_null()) & (pl.col("zone").is_null()))
    .then(pl.col("Zone"))
    .otherwise(pl.col("zone"))
    .alias("zone")
    .str.replace('NCR', 'NCZ')
    .str.replace('SCR', 'SCZ')
    .str.replace('NWF', 'NWFZ')
    .str.replace('CEN', 'CZ')
    .str.replace('NWR', 'NWZ')  # Ensure we update 'zone'
)

rem_lpg_plant_id = rem_lpg_plant_id.with_columns(
    pl.when((pl.col("Zone").is_not_null()) & (pl.col("zone").is_null()))
    .then(pl.col("Zone"))
    .otherwise(pl.col("zone"))
    .alias("zone")  # Ensure we update 'zone'
)
novex_sod_col = rem_sod_plant_id.join(role_mapping.select(["ROLE_NAME", "NOVEX Role"]), on="ROLE_NAME",  how="left").with_columns(
    pl.col("NOVEX Role").fill_null(pl.col("ROLE_NAME")).alias("NOVEX_ROLE")).drop("NOVEX Role")

print("novex_sod_col --> ", novex_sod_col)
novex_sod_col.write_csv("/Users/mac_1/Downloads/HPCL/ROLE_MASTERS/SOD_ROLE_MASTER_UPDATED.csv")

novex_lpg_col = rem_lpg_plant_id.join(role_mapping.select(["ROLE_NAME", "NOVEX Role"]), on="ROLE_NAME",  how="left").with_columns(
    pl.col("NOVEX Role").fill_null(pl.col("ROLE_NAME")).alias("NOVEX_ROLE")).drop("NOVEX Role")

print("novex_lpg_col --> ", novex_lpg_col)
novex_lpg_col.write_csv("/Users/mac_1/Downloads/HPCL/ROLE_MASTERS/LPG_ROLE_MASTER_UPDATED.csv")

sod_loc = pl.read_csv("/Users/mac_1/Downloads/HPCL/ROLE_MASTERS/SOD.csv", infer_schema_length=0)
sod_merge = novex_sod_col.join(sod_loc.select(["sap_id"]), left_on="LOCATION", right_on="sap_id", how="full")
sod_merge.write_csv("/Users/mac_1/Downloads/HPCL/ROLE_MASTERS/SOD_ROLE_MASTER_UPDATED.csv")

lpg_loc = pl.read_csv("/Users/mac_1/Downloads/HPCL/ROLE_MASTERS/LPG.csv", infer_schema_length=0)
lpg_merge = novex_lpg_col.join(lpg_loc.select(["sap_id"]), left_on="LOCATION", right_on="sap_id", how="full")
lpg_merge.write_csv("/Users/mac_1/Downloads/HPCL/ROLE_MASTERS/LPG_ROLE_MASTER_UPDATED.csv")
