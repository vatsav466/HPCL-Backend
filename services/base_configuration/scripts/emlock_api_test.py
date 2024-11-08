import requests


def test_emlock_api():
    url = 'https://localhost/api/emlock/ingest_data'
    headers = {
        "vendor": "hpcl_emlock",
        "ceg-auth-token": "ghArMdF7wcjSLUpo9fvDoRXfoExJlSqBaT9rd1gxotblW7VmFtROy9qFQMjqJkEo",
        "content-type": "application/json"
    }
    data = {
        "vendor_id": "vendor001122337",
        "location_id": "867152",
        "location_type": "TAS",
        "data": [
            {
                "vehicle_number": "MH10ABC2367",
                "violation_type": "decantation_issue",
                "initiated_date": "10/12/24 10:00:00 AM",
                "approved_date": "11/12/24 10:00:00 AM",
                "approved_by": "venu@algofusiontech.com"
            }
        ]
    }

    response = requests.post(url, headers=headers, json=data, verify=False)
    print(response.status_code, "  ", response.text)


if __name__ == "__main__":
    test_emlock_api()
