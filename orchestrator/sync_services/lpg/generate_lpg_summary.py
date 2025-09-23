import urdhva_base
import sys
import asyncio
import psycopg2
import traceback
import pandas as pd
import polars as pl
import numpy as np
from sqlalchemy import create_engine
from datetime import datetime, timedelta
sys.path.append("/opt/ceg/algo")
from utilities.helpers import get_location_details
import orchestrator.dbconnector.credential_loader as credential_loader
from orchestrator.dbconnector.widget_actions import lpg_plant_operations

logger = urdhva_base.logger.Logger.getInstance("generate_lpg_summary")

class GenerateLPGSummary():
    def __init__(self, sap_id, from_date, to_date):
        self.params = {
            "sap_id": sap_id,
            "from_date": from_date,
            "to_date": to_date
        }
    
    async def calculate_productivity(self):
        try:
            productivity = await lpg_plant_operations.LPGOperationsActions.get_productivity(self.params)
            rows = []
            for carousal, phases in productivity.items():
                row = {"carousal": int(carousal)}
                for phase, metrics in phases.items():
                    for key, value in metrics.items():
                        row[f"{phase}_{key}"] = value
                rows.append(row)
            df = pd.DataFrame(rows)

            net_hours_column = ["normal_net_hours", "break_net_hours", "overtime_net_hours"]
            production_columns = ["normal_total_production", "break_total_production", "overtime_total_production"]
            
            for col in net_hours_column+production_columns:
                if col in df.columns:
                    df[col] = df[col].fillna(0).astype(np.float64).abs()

            df["total_net_hours"] = df["normal_net_hours"] + df["break_net_hours"] + df["overtime_net_hours"]
            df["total_production"] = df["normal_total_production"] + df["break_total_production"] + df["overtime_total_production"]
            df["total_productivity"] = df["total_production"] / df["total_net_hours"]
            print("productivity :", df[["total_production", "total_net_hours", "total_productivity"]])
            return df
        except Exception as e:
            logger.info(f"--- Error In Calculating Productivity {e}---")
            logger.info(f"Traceback : {traceback.format_exc()}")
            return pd.DataFrame()
        
    async def calculate_rejections(self):
        try:
            df = pd.DataFrame()
            cs_rejection = await lpg_plant_operations.LPGOperationsActions.get_cs_rejection(self.params)
            gd_rejection = await lpg_plant_operations.LPGOperationsActions.get_gd_rejection(self.params)
            pt_rejection = await lpg_plant_operations.LPGOperationsActions.get_pt_rejection(self.params)
            #### CS REJECTION ####
            cs_rejection_data = {
                "cs_handled": 0,
                "cs_sortout": 0,
                "cs_rejection": 0
            }
            for key, val in cs_rejection.items():
                cs_rejection_data["cs_handled"] = cs_rejection_data["cs_handled"] + val["handled"]
                cs_rejection_data["cs_sortout"] = cs_rejection_data["cs_sortout"] + val["sortout"]
                cs_rejection_data["cs_rejection"] = cs_rejection_data["cs_rejection"] + val["rejection_rate"]

            cs_rejection = pd.DataFrame([cs_rejection_data])
            gd_rejection = pd.DataFrame([gd_rejection]).rename(
                        columns={"handled": "gd_handled", "sortout": "gd_sortout", "rejection_rate": "gd_rejection"})
            pt_rejection = pd.DataFrame([pt_rejection]).rename(
                        columns={"handled": "pt_handled", "sortout": "pt_sortout", "rejection_rate": "pt_rejection"})

            df = pd.concat([cs_rejection, gd_rejection, pt_rejection], axis=1)
            print("Rejections :", df)
            return df
        except Exception as e:
            print("traceback :", traceback.format_exc())
            logger.info("--- Error In Calculating Rejections ---")
            logger.info(f"Traceback : {traceback.format_exc()}")
            return pd.DataFrame()
        
    async def calculate_bottling_summary(self):
        try:
            bottling_summary = await lpg_plant_operations.LPGOperationsActions.get_bottling_summary(self.params)
            rows = []
            for carousal, metrics in bottling_summary.items():
                row = {"carousal": int(carousal)}
                row.update(metrics)
                rows.append(row)
            df = pd.DataFrame(rows)
            print("bottling_summary :", df)
            return df
        except Exception as e:
            logger.info("--- Error In Calculating Rejections ---")
            logger.info(f"Traceback : {traceback.format_exc()}")
            return pd.DataFrame()
    

    async def generate_summary(self):
        try:
            productivity = await self.calculate_productivity()
            rejections = await self.calculate_rejections()
            bottling_summary = await self.calculate_bottling_summary()
            summary = pd.concat([productivity, rejections, bottling_summary])
            summary = summary.fillna(0)
            summary = summary.groupby("carousal").sum().reset_index()

            status, location_data = await get_location_details("LPG", self.params["sap_id"])
            print("location_data :", location_data)
            summary["zone"] = location_data["zone"]
            summary["region"] = location_data["region"]
            summary["sales_area"] = location_data["sales_area"]
            summary["location_name"] = location_data["name"]

            return summary
        except Exception as e:
            logger.info("--- Error in Generating Summary ---")
            logger.info(f"Traceback : {traceback.format_exc()}")


if __name__ == "__main__":
    params = {
        "sap_id": "2330", 
        "from_date": "2025-09-21", 
        "to_date": "2025-09-21"
    }
    ins = GenerateLPGSummary(**params)
    summary = asyncio.run(ins.generate_summary())
    summary.to_csv("/tmp/summary.csv", index=False)