import urdhva_base
import sys
import time
import asyncio
import traceback
import numpy as np
import pandas as pd
from zoneinfo import ZoneInfo
sys.path.append("/opt/ceg/algo")
from datetime import datetime, timedelta
from utilities.helpers import get_location_details
from orchestrator.dbconnector.widget_actions import lpg_plant_operations
from api_manager.hpcl_ceg_model import LpgPlantOperations, LpgPlantOperationsCreate

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
            
            for col in net_hours_column + production_columns:
                if col in df.columns:
                    df[col] = df[col].fillna(0).astype(np.float64).abs()

            df["total_net_hours"] = df["normal_net_hours"] + df["break_net_hours"] + df["overtime_net_hours"]
            df["total_production"] = df["normal_total_production"] + df["break_total_production"] + df["overtime_total_production"]
            df["total_productivity"] = df["total_production"] / df["total_net_hours"]
            print("*"*20)
            print("--- productivity ---")
            print(df[["carousal", "total_production", "total_net_hours", "total_productivity"]])
            print("*"*20)
            return df
        except Exception as e:
            logger.error(f"--- Error In Calculating Productivity {e}---")
            logger.error(f"Traceback : {traceback.format_exc()}")
            return pd.DataFrame()
        
    async def calculate_rejections(self):
        try:
            df = pd.DataFrame()
            cs_rejection = await lpg_plant_operations.LPGOperationsActions.get_cs_rejection(self.params)
            gd_rejection = await lpg_plant_operations.LPGOperationsActions.get_gd_rejection(self.params)
            pt_rejection = await lpg_plant_operations.LPGOperationsActions.get_pt_rejection(self.params)
            
            #### CS REJECTION ####
            cs_rejection = pd.DataFrame.from_dict(cs_rejection, orient="index").reset_index()
            cs_rejection.rename(columns={"index": "carousal"}, inplace=True)
            cs_rejection.rename(columns={"handled": "cs_handled", "sortout": "cs_sortout", 
                                         "rejection_rate": "cs_rejection"}, inplace=True)
            if not cs_rejection.empty:
                cs_rejection = cs_rejection[["carousal", "cs_handled", "cs_sortout", "cs_rejection"]]

            #### GD REJECTION ####
            gd_rejection = pd.DataFrame.from_dict(gd_rejection, orient="index").reset_index()
            gd_rejection.rename(columns={"index": "carousal"}, inplace=True)
            gd_rejection.rename(columns={"handled": "gd_handled", "sortout": "gd_sortout", 
                                         "rejection_rate": "gd_rejection"}, inplace=True)
            if not gd_rejection.empty:
                gd_rejection = gd_rejection[["carousal", "gd_handled", "gd_sortout", "gd_rejection"]]
            
            #### PT REJECTION ####
            pt_rejection = pd.DataFrame.from_dict(pt_rejection, orient="index").reset_index()
            pt_rejection.rename(columns={"index": "carousal"}, inplace=True)
            pt_rejection.rename(columns={"handled": "pt_handled", "sortout": "pt_sortout", 
                                         "rejection_rate": "pt_rejection"}, inplace=True)
            if not pt_rejection.empty:
                pt_rejection = pt_rejection[["carousal", "pt_handled", "pt_sortout", "pt_rejection"]]

            df = pd.concat([cs_rejection, gd_rejection, pt_rejection])
            df = df.fillna(0)
            df = df.groupby("carousal").sum().reset_index()
            print("*"*20)
            print("--- Rejections ---")
            print(df)
            print("*"*20)
            return df
        except Exception as e:
            print("traceback :", traceback.format_exc())
            logger.error("--- Error In Calculating Rejections ---")
            logger.error(f"Traceback : {traceback.format_exc()}")
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
            print("*"*20)
            print("--- Bottling Summary ---")
            print(df)
            print("*"*20)
            return df
        except Exception as e:
            logger.error("--- Error In Calculating Rejections ---")
            logger.error(f"Traceback : {traceback.format_exc()}")
            return pd.DataFrame()
    

    async def generate_summary(self):
        try:
            productivity = await self.calculate_productivity()
            rejections = await self.calculate_rejections()
            bottling_summary = await self.calculate_bottling_summary()
            summary = pd.concat([productivity, rejections, bottling_summary])
            if summary.empty or summary['total_production'].sum() == 0:
                print(f"--- No Data Found for {self.params['sap_id']} ---")
                logger.info(f"--- No Data Found for {self.params['sap_id']} ---")
                return
            summary = summary.fillna(0)
            summary = summary.groupby("carousal").sum().reset_index()

            status, location_data = await get_location_details("LPG", self.params["sap_id"])
            summary["zone"] = location_data["zone"]
            summary["region"] = location_data["region"]
            summary["sales_area"] = location_data["sales_area"]
            summary["location_name"] = location_data["name"]

            carousals = await lpg_plant_operations.LPGOperationsActions.get_carousals('full', self.params["sap_id"])
            for carousal, data in carousals.items():
                summary.loc[summary["carousal"].astype(int) == int(carousal), "filling_head"] = str(int(data["heads"])) + "H"
            
            for col in summary.columns:
                try:
                    summary[col] = summary[col].fillna(0).astype(np.float64).abs().round(2)
                except Exception:
                    continue
            summary["carousal"] = summary["carousal"].astype(int).astype(str)
            summary.rename(columns={"carousal": "carousel", 
                                    "production_19": "production_19kg", 
                                    "production_14_2": "production_14_2kg"}, inplace=True)
            summary["process_date"] = datetime.strptime(self.params["to_date"], "%Y-%m-%d")
            summary["sap_id"] = self.params["sap_id"]

            print(f"Inserting the {self.params["from_date"]} summary for the plant {self.params["sap_id"]}")
            for data in summary.to_dict(orient="records"):                
                await LpgPlantOperationsCreate(**data).create()

            return summary
        except Exception as e:
            print("traceback :", traceback.format_exc())
            logger.error("--- Error in Generating Summary ---")
            logger.error(f"Traceback : {traceback.format_exc()}")


# async def main():
#     plants = pd.read_csv("/opt/ceg/algo/orchestrator/sync_services/lpg/LPG_PLANTS_CREDENTIALS.csv")
#     print(plants[["erp_id", "plant_name", "host_ip"]])

#     for plant in plants.to_dict(orient="records"):
#         print("-"*50)
#         query = f"""
#             SELECT MAX(DATE(process_date)) AS max_date
#             FROM lpg_plant_operations
#             WHERE sap_id='{plant["erp_id"]}'
#         """
#         res = await urdhva_base.BasePostgresModel.get_aggr_data(query=query, limit=1)

#         if res.get("data", None) and res["data"][0]["max_date"]:
#             from_date = res["data"][0]["max_date"]
#         else:
#             print(f"No records found in summary for {plant['plant_name']}, Checking data in production_log...")
#             query = f"""
#                     SELECT MAX(DATE(process_date)) AS max_date
#                     FROM production_log
#                     WHERE sap_id='{plant["erp_id"]}'
#                 """
#             raw_availability = await urdhva_base.BasePostgresModel.get_aggr_data(query=query, limit=1)
#             if raw_availability.get("data", None) and raw_availability["data"][0]["max_date"]:
#                 from_date = raw_availability["data"][0]["max_date"]
#             else:
#                 print(f"No records found in production_log for {plant['plant_name']}, skipping...")
#                 continue
        
#         to_date = datetime.now(ZoneInfo("Asia/Kolkata")).date()

#         current_date = from_date
#         count = 1
#         while current_date <= to_date:   
#             print("-"*20)         
#             print(f"Processing plant={plant['plant_name']} date={current_date}")
#             if count == 1:
#                 query = f"""
#                         SELECT id FROM lpg_plant_operations 
#                         WHERE sap_id='{plant["erp_id"]}' AND DATE(process_date)='{from_date.strftime("%Y-%m-%d")}' 
#                         """
#                 old_summary = await urdhva_base.BasePostgresModel.get_aggr_data(query=query, limit=0)
#                 if old_summary.get("data", None):
#                     print("-"*20)
#                     print(f"Deleting total {len(old_summary['data'])} records")
#                     print("-"*20)
#                     for x in old_summary["data"]:
#                         await LpgPlantOperations.delete(x["id"])

#             params = {
#                 "sap_id": str(plant["erp_id"]),
#                 "from_date": current_date.strftime("%Y-%m-%d"),
#                 "to_date": current_date.strftime("%Y-%m-%d")
#             }
            
#             ins = GenerateLPGSummary(**params)
#             await ins.generate_summary()

#             current_date += timedelta(days=1)
#             count += 1


# CONCURRENT PROCESSING WITH ASYNCIO
async def process_plant_concurrent(plant, semaphore):
    """Process a single plant with concurrency control"""
    async with semaphore:  # Limit concurrent operations
        try:
            print(f"Starting processing for {plant['plant_name']}")
            
            # Get the last processed date
            query = f"""
                SELECT MAX(DATE(process_date)) AS max_date
                FROM lpg_plant_operations
                WHERE sap_id='{plant["erp_id"]}'
            """
            res = await urdhva_base.BasePostgresModel.get_aggr_data(query=query, limit=1)

            if res.get("data", None) and res["data"][0]["max_date"]:
                from_date = res["data"][0]["max_date"]
            else:
                print(f"No records found in summary for {plant['plant_name']}, Checking data in production_log...")
                query = f"""
                        SELECT MAX(DATE(process_date)) AS max_date
                        FROM production_log
                        WHERE sap_id='{plant["erp_id"]}'
                    """
                raw_availability = await urdhva_base.BasePostgresModel.get_aggr_data(query=query, limit=1)
                if raw_availability.get("data", None) and raw_availability["data"][0]["max_date"]:
                    from_date = raw_availability["data"][0]["max_date"]
                else:
                    print(f"No records found in production_log for {plant['plant_name']}, skipping...")
                    return
            
            to_date = datetime.now(ZoneInfo("Asia/Kolkata")).date()
            current_date = from_date
            count = 1
            
            while current_date <= to_date:            
                print(f"Processing plant={plant['plant_name']} date={current_date}")
                
                if count == 1:
                    # Delete existing records for the first date
                    query = f"""
                            SELECT id FROM lpg_plant_operations 
                            WHERE sap_id='{plant["erp_id"]}' AND DATE(process_date)='{from_date.strftime("%Y-%m-%d")}' 
                            """
                    old_summary = await urdhva_base.BasePostgresModel.get_aggr_data(query=query, limit=0)
                    if old_summary.get("data", None):
                        print(f"Deleting {len(old_summary['data'])} existing records for {plant['plant_name']}")
                        for x in old_summary["data"]:
                            await LpgPlantOperations.delete(x["id"])

                params = {
                    "sap_id": str(plant["erp_id"]),
                    "from_date": current_date.strftime("%Y-%m-%d"),
                    "to_date": current_date.strftime("%Y-%m-%d")
                }
                
                ins = GenerateLPGSummary(**params)
                await ins.generate_summary()

                current_date += timedelta(days=1)
                count += 1
                
            print(f"Completed processing for {plant['plant_name']}")
            
        except Exception as e:
            print(f"Error processing plant {plant['plant_name']}: {e}")
            logger.error(f"Error processing plant {plant['plant_name']}: {traceback.format_exc()}")


async def main_concurrent():
    """Main function using concurrent processing"""
    plants = pd.read_csv("/opt/ceg/algo/orchestrator/sync_services/lpg/LPG_PLANTS_CREDENTIALS.csv")
    print(f"Processing {len(plants)} plants concurrently...")
    
    # Create semaphore to limit concurrent operations (adjust based on your system capacity)
    # Start with 10-15 concurrent operations, adjust based on database/API limits
    semaphore = asyncio.Semaphore(15)
    
    # Create tasks for all plants
    tasks = [process_plant_concurrent(plant, semaphore) for plant in plants.to_dict(orient="records")]
    
    # Run all tasks concurrently
    await asyncio.gather(*tasks, return_exceptions=True)
    print("All plants processed!")

if __name__ == "__main__":
    start_time = time.time()
    asyncio.run(main_concurrent())
    
    end_time = time.time()
    total_time = end_time - start_time    
    print(f"Total time taken: {total_time/60:.2f} minutes")