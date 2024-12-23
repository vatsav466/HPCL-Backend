import urdhva_base
import json
import pandas as pd
import urdhva_base.redispool

req_keys = {
    "TAS": ["zone", "sap_id", "name", "category"],
    "RO": ["zone", 'region', "sales_area", "terminal_plant_id", "terminal_plant_name", "category", "sap_id", "name"]
}


async def get_locations(bu, zone=[], region=[], sales_area=[]):
    """
    This function is used to get the location information for a given BU.
    It fetches the location master data from Redis and filters based on the BU provided.
    If zone, region and sales_area are provided, then it filters based on those as well.
    :param bu:
    :param zone:
    :param region:
    :param sales_area:
    :return:
    """
    redis_client = await urdhva_base.redispool.get_redis_connection()
    location_data = await redis_client.hgetall("location_master")

    def get_string_output(input_value):
        if isinstance(input_value, bytes):
            return input_value.decode()
        else:
            return input_value

    bu_data = [json.loads(get_string_output(rec)) for key, rec in location_data.items()
               if get_string_output(key).startswith(f"{bu.upper()}_")]
    bu_data = pd.DataFrame(bu_data)
    bu_data = bu_data[req_keys[bu.upper()]]
    bu_data.fillna("", inplace=True)
    if bu.upper() == "RO":
        # Updating Plant Name in case if missing
        tas_data = [json.loads(get_string_output(rec)) for key, rec in location_data.items()
                    if get_string_output(key).startswith(f"TAS_")]
        terminal_name_mapping = {rec['sap_id']: rec['name'] for rec in tas_data}
        bu_data['terminal_plant_name'] = bu_data['terminal_plant_id'].apply(lambda x: terminal_name_mapping.get(x, x))
        bu_data = bu_data[bu_data['terminal_plant_name'].notna()]
    final_data = {"zone": {}, "plant": {}}
    if bu.upper() == "RO":
        final_data.update({"region": {}, "sales_area": {}, "customer": {}})

    def check_category(category):
        if category and category.upper() == "R01":
            return "A"
        return ""

    key_mapping = {}

    # Filtering zone
    for rec in bu_data.to_dict(orient='records'):
        if rec["zone"]:
            final_data["zone"][rec["zone"]] = {"name": rec["zone"], "id": rec["zone"]}
    if zone:
        key_mapping["zone"] = zone
    if bu.upper() == "TAS":
        for rec in bu_data.to_dict(orient='records'):
            skip_record = False
            if key_mapping:
                for key, value in key_mapping.items():
                    if rec.get(key) not in value:
                        skip_record = True
                        break
            if skip_record or not rec["sap_id"]:
                continue
            if rec["sap_id"]:
                final_data["plant"][rec["sap_id"]] = {"name": rec["name"], "id": rec["sap_id"]}
    else:
        if region:
            key_mapping["region"] = region

        # Filtering region
        for rec in bu_data.to_dict(orient='records'):
            skip_record = False
            if key_mapping:
                for key, value in key_mapping.items():
                    if rec.get(key) not in value:
                        skip_record = True
                        break
            if skip_record or not rec["region"]:
                continue
            if rec["region"]:
                final_data["region"][rec["region"]] = {"name": rec["region"], "id": rec["region"]}

        # Filtering Sales Area
        if sales_area:
            key_mapping["sales_area"] = sales_area
        for rec in bu_data.to_dict(orient='records'):
            skip_record = False
            if key_mapping:
                for key, value in key_mapping.items():
                    if rec.get(key) not in value:
                        skip_record = True
                        break
            if skip_record or not rec["sales_area"]:
                continue
            if rec["sales_area"]:
                final_data["sales_area"][rec["sales_area"]] = {"name": rec["sales_area"], "id": rec["sales_area"]}

        # Filtering Plant
        for rec in bu_data.to_dict(orient='records'):
            skip_record = False
            if key_mapping:
                for key, value in key_mapping.items():
                    if rec.get(key) not in value:
                        skip_record = True
                        break
            if skip_record or not rec["sap_id"]:
                continue
            if rec["sap_id"]:
                final_data["customer"][rec["sap_id"]] = {"name": rec["name"], "id": rec["sap_id"],
                                                         "category": check_category(rec['category'])}

    for key, details in final_data.items():
        final_data[key] = list(details.values())
    return final_data
