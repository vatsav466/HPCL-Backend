"""
Daily TAS data monitor.

Runs via cron/systemd timer (cron should schedule at 10:00).
Checks whether each TAS location has alerts posted in the last 24 hours
and sends an email report.
"""
import datetime
import urdhva_base  # type: ignore[import-not-found]
import hpcl_ceg_model  # type: ignore[import-not-found]

from orchestrator.notification_manager.notify_email import NotifyEMail


def _html_report(rows: list[dict], window_hours: int) -> str:
    header = f"""
    <p><b>TAS Daily Data Monitor</b></p>
    <p>Checked window: last {window_hours} hours</p>
    <table border="1" cellpadding="6" cellspacing="0" style="border-collapse:collapse;">
      <thead>
        <tr>
          <th>SAP ID</th>
          <th>Location</th>
          <th>Last alert created_at</th>
          <th>Last alert unique_id</th>
          <th>Status</th>
        </tr>
      </thead>
      <tbody>
    """
    body = ""
    for r in rows:
        status = r["status"]
        color = "#d4edda" if status == "OK" else "#f8d7da"
        last_ts = r["last_created_at"] or "-"
        last_uid = r.get("last_unique_id") or "-"
        body += f"""
        <tr>
          <td>{r["sap_id"]}</td>
          <td>{r["name"]}</td>
          <td>{last_ts}</td>
          <td>{last_uid}</td>
          <td style="background:{color};"><b>{status}</b></td>
        </tr>
        """
    footer = """
      </tbody>
    </table>
    """
    return header + body + footer


async def run_daily_check(
    bu: str = "TAS",
    window_hours: int = 24,
    only_active_locations: bool = True,
):
    # Load locations
    loc_query = f"bu = '{bu}'"
    if only_active_locations:
        loc_query += " and location_onboard = true"

    loc_params = urdhva_base.queryparams.QueryParams(
        q=loc_query,
        limit=500,
        fields='["sap_id","name","dealer_email","is_active","location_onboard"]',
    )
    loc_resp = await hpcl_ceg_model.LocationMaster.get_all(loc_params, resp_type="plain")
    locations = loc_resp.get("data", []) if isinstance(loc_resp, dict) else []

    if not locations:
        raise RuntimeError(f"No locations found in location_master for query: {loc_query}")

    now = datetime.datetime.now()
    cutoff = now - datetime.timedelta(hours=window_hours)

    rows: list[dict] = []
    missing: list[str] = []

    for loc in locations:
        sap_id = (loc.get("sap_id") or "").strip()
        name = (loc.get("name") or "").strip() or sap_id
        dealer_email = (loc.get("dealer_email") or "").strip()

        last_created_at = None
        last_unique_id = None
        try:
            q = (
                "SELECT id, unique_id, created_at "
                "FROM alerts "
                f"WHERE bu = '{bu}' AND alert_section = '{bu}' AND sap_id = '{sap_id}' "
                "ORDER BY created_at DESC "
                "LIMIT 1"
            )
            resp = await hpcl_ceg_model.Alerts.get_aggr_data(q, limit=0)
            data = (resp or {}).get("data", [])
            if data:
                row = data[0]
                last_created_at = row.get("created_at")
                last_unique_id = row.get("unique_id")
        except Exception as e:
            print(f"[tas_daily_data_monitor] Failed query for sap_id={sap_id}: {e}")

        ok = bool(last_created_at and isinstance(last_created_at, datetime.datetime) and last_created_at >= cutoff)
        status = "Online" if ok else "Offline"
        if not ok:
            missing.append(sap_id)

        rows.append(
            {
                "sap_id": sap_id,
                "name": name,
                "dealer_email": dealer_email,
                "last_created_at": last_created_at.isoformat(sep=" ", timespec="seconds") if isinstance(last_created_at, datetime.datetime) else None,
                "last_unique_id": last_unique_id,
                "status": status,
            }
        )

    to_recipients =  ['mohith.p@algofusiontech.com',"moufikali@algofusiontech.com","pawann.k@algofusiontec.com","manohar.v@algofusiontech.com"]
    if not to_recipients:
        raise RuntimeError("No email recipients configured. Set TAS_DAILY_MONITOR_TO env var (comma-separated).")

    subject = f"[TAS] Daily data check @ {now.strftime('%Y-%m-%d %H:%M')} - Missing: {len(missing)}/{len(rows)}"
    body = _html_report(rows, window_hours=window_hours)
    from_url = "Novex<novex@hpcl.in>"
    notify = NotifyEMail()
    await notify.publish_message(
        from_url = from_url,
        recipients=to_recipients,
        cc_recipients=[],
        subject=subject,
        body=body,
        html_content=True,
        force_send=True,
    )

    return {
        "status": "sent",
        "now": now.isoformat(),
        "checked_locations": len(rows),
        "missing_locations": missing,
    }


if __name__ == "__main__":
    import asyncio
    asyncio.run(run_daily_check())