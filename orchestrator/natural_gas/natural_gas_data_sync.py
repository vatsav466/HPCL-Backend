import urdhva_base.redispool

import sys
import json
import io
import uuid
import typing
import fastapi
import asyncio
import polars as pl
import hpcl_ceg_model
import pandas as pd  # only for reading Excel sheets
from typing import Dict, Union
import dateutil.parser as parser
from collections import defaultdict

from orchestrator.natural_gas.daily_cmd_dpr_decode import (
    decode_daily_cmd_dpr_workbook,
    json_safe_records,
)
from orchestrator.natural_gas.natural_gas_record_mapping import (
    decoded_payload_to_db_records,
)


def clean_dataframe(df: pd.DataFrame) -> pl.DataFrame:
    """
    Clean Excel sheet and convert to Polars
    """
    # Drop empty rows/cols
    df = df.dropna(how="all").dropna(axis=1, how="all").reset_index(drop=True)

    # Fix headers
    if df.iloc[0].isnull().sum() > len(df.columns) * 0.5:
        df.columns = df.iloc[1]
        df = df[2:]
    else:
        df.columns = df.iloc[0]
        df = df[1:]

    df.columns = [str(c).strip() for c in df.columns]

    # Convert to Polars
    return pl.from_pandas(df)


def load_all_sheets(file_path: Union[str, typing.Any]) -> Dict[str, pl.DataFrame]:
    xls = pd.ExcelFile(file_path)
    data = {}

    for sheet in xls.sheet_names:
        try:
            pdf = pd.read_excel(file_path, sheet_name=sheet)
            data[sheet] = clean_dataframe(pdf)
        except Exception as e:
            print(f"Skipping sheet {sheet}: {e}")

    return data


def extract_company_data(data: Dict[str, pl.DataFrame]) -> Dict:
    company_data = defaultdict(list)

    for sheet_name, df in data.items():
        cols = [c.lower() for c in df.columns]

        company_col = None
        state_col = None

        for c in df.columns:
            if "entity" in c.lower() or "company" in c.lower():
                company_col = c
            if "state" in c.lower():
                state_col = c

        if not company_col:
            continue

        # Convert to dict rows (fast enough after filtering)
        rows = df.to_dicts()

        for row in rows:
            company = str(row.get(company_col, "")).strip()
            if not company:
                continue

            entry = {
                "sheet": sheet_name,
                "company": company,
                "state": row.get(state_col),
                "data": row
            }

            company_data[company].append(entry)

    return company_data


def generate_summary(data: Dict[str, pl.DataFrame]) -> Dict:
    summary = {}

    for sheet_name, df in data.items():

        # Detect company column
        company_col = None
        for c in df.columns:
            if "entity" in c.lower() or "company" in c.lower():
                company_col = c
                break

        if not company_col:
            continue

        # Select numeric columns
        numeric_cols = [
            c for c, dtype in zip(df.columns, df.dtypes)
            if dtype in (pl.Int64, pl.Float64)
        ]

        if not numeric_cols:
            continue

        grouped = (
            df
            .groupby(company_col)
            .agg([pl.col(c).sum().alias(c) for c in numeric_cols])
        )

        for row in grouped.to_dicts():
            company = row[company_col]
            if company not in summary:
                summary[company] = {}

            for k, v in row.items():
                if k != company_col:
                    summary[company][k] = summary[company].get(k, 0) + (v or 0)

    return summary


async def convert_dpr_file_data(
    file_pointer: fastapi.UploadFile,
    *,
    include_grand_total_ngc_column: bool = False,
    include_cumulative_columns: bool = False,
):
    """
    Parse uploaded workbook: **MIS Summary** (entity × summary columns) and
    **HPCL-JV MIS** (company × GA × metrics). Returns JSON for
    ``/naturalgasconnections/upload_connection_data``.

    See :func:`decode_daily_cmd_dpr_workbook` for ``include_cumulative_columns`` and
    ``include_grand_total_ngc_column``.
    """
    raw = await file_pointer.read()
    buf = io.BytesIO(raw)
    decoded = decode_daily_cmd_dpr_workbook(
        buf,
        include_grand_total_ngc_column=include_grand_total_ngc_column,
        include_cumulative_columns=include_cumulative_columns,
    )
    db_rows = decoded_payload_to_db_records(
        decoded,
        include_cumulative_columns=include_cumulative_columns,
    )
    unique_id = str(uuid.uuid4()).replace('-', '')
    payload = {
        "Summary Data": db_rows["natural_gas_connections_summary"],
        "JV Data": db_rows["natural_gas_connections"]
    }
    r_ins = await urdhva_base.redispool.get_redis_connection()
    await r_ins.setex(
        f"natural_gas_connections_{unique_id}",
        10 * 60, # Max 10 mins cached data
        json.dumps(payload))
    await r_ins.close()
    return fastapi.responses.JSONResponse(content={"ack_id": unique_id, "payload": payload})


async def _sync_data(data):
    for key, records in data.items():
        for index, _ in enumerate(records):
            data[key][index]['conn_date'] = parser.parse(records[index]['conn_date'])
    await hpcl_ceg_model.NaturalGasConnectionsSummary.bulk_update(data['Summary Data'], upsert=True)
    await hpcl_ceg_model.NaturalGasConnections.bulk_update(data['JV Data'], upsert=True)
    return True, "Success"


async def sync_dpr_data(ack_id: str):
    r_ins = await urdhva_base.redispool.get_redis_connection()
    payload = await r_ins.get(f"natural_gas_connections_{ack_id}")
    if not payload:
        return False, "Expired records, Please upload file again"
    db_rows = json.loads(payload)
    return await _sync_data(db_rows)


async def main(file_path) -> None:
    decoded = decode_daily_cmd_dpr_workbook(
        file_path,
        include_cumulative_columns=False,
        include_grand_total_ngc_column=False,
    )
    db_rows = decoded_payload_to_db_records(
        decoded,
        include_cumulative_columns=False,
    )
    payload = {
        "sheets_present": decoded.get("sheets_present", []),
        "mis_summary_sheet": decoded.get("mis_summary_sheet"),
        "hpcl_jv_mis_sheet": decoded.get("hpcl_jv_mis_sheet"),
        "mis_summary": json_safe_records(decoded.get("mis_summary") or []),
        "hpcl_jv_mis": json_safe_records(decoded.get("hpcl_jv_mis") or []),
        "natural_gas_connections_summary": db_rows["natural_gas_connections_summary"],
        "natural_gas_connections": db_rows["natural_gas_connections"],
        "report_year": db_rows["report_year"],
        "decode_options": {
            "include_grand_total_ngc_column": False,
            "include_cumulative_columns": False,
        },
    }
    print(json.dumps(payload, indent=2, default=str))


if __name__ == "__main__":
    if len(sys.argv) == 1:
        print("Usage: python natural_gas_data_sync.py <file_path>")
        sys.exit(1)
    else:
        asyncio.run(main(sys.argv[1]))
