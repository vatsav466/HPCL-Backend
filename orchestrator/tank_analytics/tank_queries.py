queries = {

# QUERY TO TANK DETAILS 
"tank_details" : """
    SELECT 
        live_data.sap_id,
        live_data.location_name,
        live_data.tank_name as "name",
        live_data.tank_code as "tank_id",
        tank_details.type as "type",
        ((tank_details.kl_per_mm::numeric * live_data.curr_level::numeric) * 100) / tank_details.gross_capacity_kl as "percent",
        tank_details.tank_no,
        live_data.tank_mode,
        live_data.curr_level,
        tank_details.kl_per_mm::numeric,
        tank_details.kl_per_mm::numeric * live_data.curr_level::numeric as "curr_stock_kl",
        tank_details.dead_stock_kl,
        ROUND(tank_details.kl_per_mm::numeric * live_data.curr_level::numeric - tank_details.dead_stock_kl, 2) as "available_stock_kl",
        live_data.water_level,
        tank_details.product as "product",
        tank_details.gross_capacity_kl as "gross_capacity_kl",
        tank_details.peso_capacity_kl,
        tank_details.pumpable_volume_kl,
        tank_details.diameter,
        tank_details.height,
        tank_details.gross_capacity_kl - (tank_details.kl_per_mm::numeric * live_data.curr_level::numeric) as "ullage"
    FROM (
            SELECT hltd.*,
				   lm.zone
			FROM host_live_tank_details hltd LEFT JOIN location_master lm 
			     ON hltd.sap_id = lm.sap_id
			WHERE {}
        ) live_data
    LEFT JOIN public.tank_dia_details tank_details 
    ON live_data.sap_id = tank_details.location_sap_code  
        AND (
            substring(live_data.tank_name FROM '^[A-Z]+') = substring(tank_details.tank_no FROM '^[A-Z]+')
            OR
            substring(live_data.tank_name FROM '\d+')::int = substring(tank_details.tank_no FROM '\d+')::int
        )
""",

# QUERY TO GET PRODUCT DISPATCH
"dispatch" : """
    WITH todays_readings AS (
        SELECT
            hltd.sap_id,
            hltd.tank_name,
            hltd.curr_level,
            hltd.date_time,
            lm.zone,
            LAG(hltd.curr_level) OVER (PARTITION BY hltd.tank_name, hltd.date_time::DATE ORDER BY hltd.date_time) AS prev_level,
            ROW_NUMBER() OVER (PARTITION BY hltd.tank_name, hltd.date_time::DATE ORDER BY hltd.date_time) AS rn
        FROM host_live_tank_details hltd LEFT JOIN location_master lm 
        ON hltd.sap_id = lm.sap_id
        WHERE {}
    ),
    combined AS (
        SELECT
            tr.sap_id,
            tr.zone,
            tr.tank_name,
            tr.curr_level,
            CASE
                WHEN rn = 1 THEN (
                    SELECT curr_level FROM host_live_tank_details h2
                    WHERE h2.tank_name = tr.tank_name
                    AND h2.sap_id = tr.sap_id
                    AND h2.date_time::DATE = tr.date_time::DATE - INTERVAL '1 day'  -- ← dynamic prev day
                    ORDER BY h2.date_time DESC
                    LIMIT 1
                )
                ELSE tr.prev_level
            END AS prev_level,
            tr.date_time,
            tdd.product,
            tdd.kl_per_mm
        FROM todays_readings tr
        LEFT JOIN (
            SELECT tank_no, product, location_sap_code, kl_per_mm FROM tank_dia_details
            ) tdd
            ON tr.sap_id = tdd.location_sap_code
            AND (
                substring(tr.tank_name FROM '^[A-Z]+') = substring(tdd.tank_no FROM '^[A-Z]+')
                OR
                substring(tr.tank_name FROM '\d+')::int = substring(tdd.tank_no FROM '\d+')::int
            )
    ),
    t_dispatch AS (
        SELECT
            sap_id,
            tank_name,
            product,
            zone,
            SUM(
                CASE
                    WHEN COALESCE(prev_level, 0) > curr_level
                    THEN COALESCE(prev_level, 0) - curr_level
                    ELSE 0
                END
            )::numeric * kl_per_mm::numeric  AS total_dispatch                
        FROM combined
        GROUP BY sap_id, zone, tank_name, kl_per_mm, product
    )
    SELECT
        zone,
        sap_id,
        product,
        ROUND(SUM(total_dispatch), 2) as sum
    FROM t_dispatch
    GROUP BY sap_id, zone, product  
""",

#QUERY TO GET PRODUCT RECEIPT
"receipt" : """
    WITH todays_readings AS (
        SELECT
            hltd.sap_id,
            lm.zone,
            hltd.tank_name,
            hltd.curr_level,
            hltd.date_time,
            LAG(hltd.curr_level) OVER (PARTITION BY hltd.tank_name, hltd.date_time::DATE ORDER BY hltd.date_time) AS prev_level,
            ROW_NUMBER() OVER (PARTITION BY hltd.tank_name, hltd.date_time::DATE ORDER BY hltd.date_time) AS rn
        FROM host_live_tank_details hltd LEFT JOIN location_master lm
        ON hltd.sap_id = lm.sap_id
        WHERE {}
        ),
    combined AS (
        SELECT
            tr.sap_id,
            tr.zone,
            tr.tank_name,
            tr.curr_level,
            CASE
                WHEN rn = 1 THEN (
                    SELECT curr_level FROM host_live_tank_details h2
                    WHERE h2.tank_name = tr.tank_name
                    AND h2.sap_id = tr.sap_id
                    AND h2.date_time::DATE = tr.date_time::DATE - INTERVAL '1 day'  -- ← dynamic prev day
                    ORDER BY h2.date_time DESC
                    LIMIT 1
                )
                ELSE tr.prev_level
            END AS prev_level,
            tr.date_time,
            tdd.product,
            tdd.kl_per_mm
        FROM todays_readings tr
        LEFT JOIN (
            SELECT tank_no, product, location_sap_code, kl_per_mm FROM tank_dia_details
            ) tdd
            ON tr.sap_id = tdd.location_sap_code
            AND (
                substring(tr.tank_name FROM '^[A-Z]+') = substring(tdd.tank_no FROM '^[A-Z]+')
                OR
                substring(tr.tank_name FROM '\d+')::int = substring(tdd.tank_no FROM '\d+')::int
            )
        ),
    t_receipt AS (
        SELECT
            sap_id,
            zone,
            tank_name,
            product,
            SUM(
                CASE
                    WHEN COALESCE(prev_level, 0) < curr_level
                    THEN COALESCE(curr_level, 0) - prev_level
                    ELSE 0
                END
            )::numeric * kl_per_mm::numeric AS total_receipt               
        FROM combined
        GROUP BY sap_id, zone, tank_name, kl_per_mm, product
    )
    SELECT
        sap_id,
        zone,
        product,
        ROUND(SUM(total_receipt), 2) as sum
    FROM t_receipt
    GROUP BY sap_id, zone, product  
""",

#QUERY TO GET TOTAL BCU DISPATCH
"bcu_total_dispatch" : """
    SELECT hltd.sap_id, lm.zone, hltd.stock as product, ROUND(SUM(hltd.bcu_net_totalizer), 2) as sum
    FROM public.host_day_end_details hltd LEFT JOIN location_master lm
	ON hltd.sap_id = lm.sap_id
    WHERE {}
    GROUP BY hltd.sap_id, lm.zone, hltd.stock;
""",

#QUERY TO GET PRODUCT WISE DISPATCH AVERAGE
"dispatch_average_prodwise" : """
    WITH todays_readings AS (
    SELECT
        hltd.sap_id,
		lm.zone,
        hltd.tank_name,
        hltd.curr_level,
        hltd.date_time,
        LAG(hltd.curr_level) OVER (PARTITION BY hltd.tank_name, hltd.date_time::DATE ORDER BY hltd.date_time) AS prev_level,
        ROW_NUMBER() OVER (PARTITION BY hltd.tank_name, hltd.date_time::DATE ORDER BY hltd.date_time) AS rn
    FROM host_live_tank_details hltd LEFT JOIN location_master lm
	ON hltd.sap_id = lm.sap_id
    --WHERE date_time::DATE BETWEEN CURRENT_DATE - INTERVAL '8 days' AND CURRENT_DATE - INTERVAL '1 day')
    WHERE hltd.date_time::DATE BETWEEN DATE '2026-02-05' - INTERVAL '8 days' AND DATE '2026-02-05' - INTERVAL '1 day'
          {}
    ),
    combined AS (
        SELECT
            tr.sap_id,
            -- tr.zone,
            tr.tank_name,
            tr.curr_level,
            CASE
                WHEN rn = 1 THEN (
                    SELECT curr_level FROM host_live_tank_details h2
                    WHERE h2.tank_name = tr.tank_name
                    AND h2.sap_id = tr.sap_id
                    AND h2.date_time::DATE = tr.date_time::DATE - INTERVAL '1 day'
                    ORDER BY h2.date_time DESC
                    LIMIT 1
                )
                ELSE tr.prev_level
            END AS prev_level,
            tr.date_time,
            CASE tdd.product
                WHEN 'ETHANOL'   THEN 'ETHANOL'
                WHEN 'Ethanol'   THEN 'ETHANOL'
                WHEN 'ETH'       THEN 'ETHANOL'
                WHEN 'BIODIESEL' THEN 'BIODIESEL'
                WHEN 'Biodiesel' THEN 'BIODIESEL'
                WHEN 'BIO-HSD'   THEN 'BIODIESEL'
                ELSE tdd.product  -- fallback: keep as-is for unmapped products
            END AS product,
            tdd.kl_per_mm
        FROM todays_readings tr
        LEFT JOIN (
            SELECT tank_no, product, location_sap_code, kl_per_mm FROM tank_dia_details
        ) tdd
            ON tr.sap_id = tdd.location_sap_code
            AND (
                substring(tr.tank_name FROM '^[A-Z]+') = substring(tdd.tank_no FROM '^[A-Z]+')
                OR
                substring(tr.tank_name FROM '\d+')::int = substring(tdd.tank_no FROM '\d+')::int
            )
    ),
    t_dispatch AS (
        SELECT
            date_time::DATE AS dispatch_date,
            sap_id,
            tank_name,
            product,
            SUM(
                CASE
                    WHEN COALESCE(prev_level, 0) > curr_level
                    THEN COALESCE(prev_level, 0) - curr_level
                    ELSE 0
                END
            )::numeric * kl_per_mm::numeric AS total_dispatch
        FROM combined
        GROUP BY date_time::DATE, sap_id, tank_name, kl_per_mm, product
    ),
    daily_totals AS (
        SELECT
            product,
            dispatch_date,
            SUM(total_dispatch) AS day_total
        FROM t_dispatch
        GROUP BY dispatch_date, product
    )
    SELECT
        product,
        ROUND(AVG(day_total), 2) AS seven_day_avg
    FROM daily_totals
    WHERE NOT (daily_totals IS NULL)
    GROUP BY product 
""",

# QUERY TO GET AVERAGE DISPATCH
"dispatch_average" : """
    WITH todays_readings AS (
            SELECT
                hltd.sap_id,
                hltd.tank_name,
                hltd.curr_level,
                hltd.date_time,
                LAG(hltd.curr_level) OVER (PARTITION BY hltd.tank_name, hltd.date_time::DATE ORDER BY hltd.date_time) AS prev_level,
                ROW_NUMBER() OVER (PARTITION BY hltd.tank_name, hltd.date_time::DATE ORDER BY hltd.date_time) AS rn
            FROM host_live_tank_details hltd JOIN location_master lm 
			ON hltd.sap_id = lm.sap_id
            --WHERE hltd.date_time::DATE BETWEEN CURRENT_DATE - INTERVAL '8 days' AND CURRENT_DATE - INTERVAL '1 day'),
            WHERE hltd.date_time::DATE BETWEEN DATE '2026-02-05' - INTERVAL '8 days' AND DATE '2026-02-05' - INTERVAL '1 day'
                  {}
        ),
        combined AS (
            SELECT
                tr.sap_id,
                tr.tank_name,
                tr.curr_level,
                CASE
                    WHEN rn = 1 THEN (
                        SELECT curr_level FROM host_live_tank_details h2
                        WHERE h2.tank_name = tr.tank_name
                        AND h2.sap_id = tr.sap_id
                        AND h2.date_time::DATE = tr.date_time::DATE - INTERVAL '1 day'
                        ORDER BY h2.date_time DESC
                        LIMIT 1
                    )
                ELSE tr.prev_level
                END AS prev_level,
                tr.date_time,
                tdd.product,
                tdd.kl_per_mm
            FROM todays_readings tr
            LEFT JOIN (
                SELECT tank_no, product, location_sap_code, kl_per_mm FROM tank_dia_details
                ) tdd
                ON tr.sap_id = tdd.location_sap_code
                AND (
                substring(tr.tank_name FROM '^[A-Z]+') = substring(tdd.tank_no FROM '^[A-Z]+')
                OR
                substring(tr.tank_name FROM '\d+')::int = substring(tdd.tank_no FROM '\d+')::int
                )
            ),
        t_dispatch AS (
            SELECT
                date_time::DATE AS dispatch_date,  -- ← added to group per day
                sap_id,
                tank_name,
                product,
                SUM(
                    CASE
                        WHEN COALESCE(prev_level, 0) > curr_level
                        THEN COALESCE(prev_level, 0) - curr_level
                    ELSE 0
                END
                )::numeric * kl_per_mm::numeric  AS total_dispatch
            FROM combined
            GROUP BY date_time::DATE, sap_id, tank_name, kl_per_mm, product
        ),
        daily_totals AS (
            SELECT
                dispatch_date,
                SUM(total_dispatch) AS day_total  -- ← total per day across all tanks/products
            FROM t_dispatch
            GROUP BY dispatch_date
        )
        SELECT
            ROUND(AVG(day_total), 2) AS seven_day_avg  -- ← average of 7 daily totals
        FROM daily_totals 
""",

#QUERY TO GET TANK ULLAGE
"tank_ullage" : """
    with ullage_data as (
        select
            tank_details.gross_capacity_kl as capacity,
            tank_details.dead_stock_kl as dead_stock,
            tank_details.product as "product",
	        ROUND(tank_details.gross_capacity_kl - (tank_details.kl_per_mm::numeric * live_data.curr_level::numeric), 2) as "ullage"
        FROM (
            SELECT hltd.* FROM host_live_tank_details hltd LEFT JOIN location_master lm 
			ON hltd.sap_id = lm.sap_id 
            --WHERE date_time::DATE = CURRENT_DATE 
            WHERE hltd.date_time::DATE BETWEEN DATE '2026-02-05' AND DATE ' 2026-02-05' 
                 {} 
            ) live_data
        LEFT JOIN public.tank_dia_details tank_details  
        ON live_data.sap_id = tank_details.location_sap_code 
            AND (
                substring(live_data.tank_name FROM '^[A-Z]+') = substring(tank_details.tank_no FROM '^[A-Z]+')
            OR
                substring(live_data.tank_name FROM '\d+')::int = substring(tank_details.tank_no FROM '\d+')::int
                )
    ) 
    select "product", SUM(capacity) as capacity, SUM("ullage") as ullage, SUM("dead_stock") as dead_stock
    FROM ullage_data GROUP BY "product"
""",

#QUERY TO GET DAYWISE TRENDS'
"daywise_trends" : """
    WITH todays_readings AS (
        SELECT
            hltd.sap_id,
            hltd.tank_name,
            hltd.curr_level,
            hltd.date_time::DATE,
            LAG(hltd.curr_level) OVER (PARTITION BY hltd.tank_name, hltd.date_time::DATE ORDER BY hltd.date_time) AS prev_level,
            ROW_NUMBER() OVER (PARTITION BY hltd.tank_name, hltd.date_time::DATE ORDER BY hltd.date_time) AS rn
        FROM host_live_tank_details hltd LEFT JOIN location_master lm ON
        hltd.sap_id = lm.sap_id
        WHERE {}
    ),
    combined AS (
        SELECT
            tr.sap_id,
            tr.tank_name,
            tr.curr_level,
            CASE
                WHEN rn = 1 THEN (
                    SELECT curr_level FROM host_live_tank_details h2
                    WHERE h2.tank_name = tr.tank_name
                    AND h2.sap_id = tr.sap_id
                    AND h2.date_time::DATE = tr.date_time::DATE - INTERVAL '1 day'  -- ← dynamic prev day
                    ORDER BY h2.date_time DESC
                    LIMIT 1
                )
                ELSE tr.prev_level
            END AS prev_level,
            tr.date_time,
            tdd.product,
            tdd.kl_per_mm
        FROM todays_readings tr
        LEFT JOIN (
            SELECT tank_no, product, location_sap_code, kl_per_mm FROM tank_dia_details
            ) tdd
            ON tr.sap_id = tdd.location_sap_code
            AND (
                substring(tr.tank_name FROM '^[A-Z]+') = substring(tdd.tank_no FROM '^[A-Z]+')
                OR
                substring(tr.tank_name FROM '\d+')::int = substring(tdd.tank_no FROM '\d+')::int
            )
    ),
    t_dispatch AS (
        SELECT
            sap_id,
            tank_name,
            product,
            date_time,
            SUM(
                CASE
                    WHEN COALESCE(prev_level, 0) > curr_level
                    THEN COALESCE(prev_level, 0) - curr_level
                    ELSE 0
                END
            )::numeric * kl_per_mm::numeric  AS total_dispatch                
        FROM combined
        GROUP BY sap_id, tank_name, date_time, kl_per_mm, product
    ),
	t_reciept AS (
        SELECT 
            sap_id,
            tank_name,
            product,
            date_time,
            SUM(
                CASE
                    WHEN COALESCE(prev_level, 0) < curr_level
                    THEN COALESCE(curr_level, 0) - prev_level
                    ELSE 0
                END
            )::numeric * kl_per_mm::numeric  AS total_reciept               
        FROM combined
        GROUP BY sap_id, tank_name, date_time, kl_per_mm, product
	)
    SELECT
        dis.product,
        dis.date_time,
        ROUND(SUM(dis.total_dispatch), 2) as dispatch,
        ROUND(SUM(rec.total_reciept), 2) as reciept
    FROM t_dispatch as dis LEFT JOIN t_reciept as rec ON 
        dis.sap_id = rec.sap_id AND dis.tank_name = rec.tank_name AND dis.product = rec.product AND dis.date_time = rec.date_time
    GROUP BY dis.date_time, dis.product
""",

#QUERY TO GET DAYWISE ULLAGE 
"ullage_daywise_trends" : """
    with ullage_data as (
        select 
	        live_data.date_time::DATE,
	        tank_details.dead_stock_kl,
	        tank_details.gross_capacity_kl as capacity,
        ROUND((tank_details.kl_per_mm::numeric * live_data.curr_level::numeric - tank_details.dead_stock_kl), 2) as "available_stock",
        tank_details.product as "product",
        ROUND(tank_details.gross_capacity_kl - (tank_details.kl_per_mm::numeric * live_data.curr_level::numeric), 2) as "ullage"
    FROM (
        SELECT hltd.* FROM host_live_tank_details hltd LEFT JOIN location_master lm 
	    ON hltd.sap_id = lm.sap_id
	    WHERE {}
    ) live_data
    LEFT JOIN public.tank_dia_details tank_details  
        ON live_data.sap_id = tank_details.location_sap_code 
        AND (
            substring(live_data.tank_name FROM '^[A-Z]+') = substring(tank_details.tank_no FROM '^[A-Z]+')
            OR
            substring(live_data.tank_name FROM '\d+')::int = substring(tank_details.tank_no FROM '\d+')::int
        )
    ) 
    SELECT 
        "product", date_time,SUM(available_stock) AS available_stock, SUM(dead_stock_kl) as dead_stock, SUM(capacity) AS capacity, SUM("ullage") as ullage
    FROM ullage_data GROUP BY date_time, "product"
"""

}





queries_old = {
    "tank_details" : """
            select 
            live_data.sap_id,
            live_data.location_name,
            live_data.tank_name as "name",
            live_data.tank_code as "tank_id",
            tank_details.type as "type",
            ((tank_details.kl_per_mm::numeric * live_data.curr_level::numeric) * 100) / tank_details.gross_capacity_kl as "percent",
            tank_details.tank_no,
            live_data.tank_mode,
            live_data.curr_level,
            tank_details.kl_per_mm::numeric,
            tank_details.kl_per_mm::numeric * live_data.curr_level::numeric as "curr_stock_kl",
            tank_details.dead_stock_kl,
            ROUND(tank_details.kl_per_mm::numeric * live_data.curr_level::numeric - tank_details.dead_stock_kl, 2) as "available_stock_kl",
            live_data.water_level,
            tank_details.product as "product",
            tank_details.gross_capacity_kl as "gross_capacity_kl",
            tank_details.peso_capacity_kl,
            tank_details.pumpable_volume_kl,
            tank_details.diameter,
            tank_details.height,
            tank_details.gross_capacity_kl - (tank_details.kl_per_mm::numeric * live_data.curr_level::numeric) as "ullage"
        FROM (
            SELECT * FROM host_live_tank_details WHERE {}
        ) live_data
        LEFT JOIN public.tank_dia_details tank_details 
            ON live_data.sap_id = tank_details.location_sap_code  
            AND (
                substring(live_data.tank_name FROM '^[A-Z]+') = substring(tank_details.tank_no FROM '^[A-Z]+')
                OR
                substring(live_data.tank_name FROM '\d+')::int = substring(tank_details.tank_no FROM '\d+')::int
            )
        """,

    "dispatch" : """
        WITH todays_readings AS (
            SELECT
                sap_id,
                tank_name,
                curr_level,
                date_time,
                LAG(curr_level) OVER (PARTITION BY tank_name, date_time::DATE ORDER BY date_time) AS prev_level,
                ROW_NUMBER() OVER (PARTITION BY tank_name, date_time::DATE ORDER BY date_time) AS rn
            FROM host_live_tank_details
            WHERE {} 
        ),
        combined AS (
            SELECT
                tr.sap_id,
                tr.tank_name,
                tr.curr_level,
                CASE
                    WHEN rn = 1 THEN (
                        SELECT curr_level FROM host_live_tank_details h2
                        WHERE h2.tank_name = tr.tank_name
                        AND h2.sap_id = tr.sap_id
                        AND h2.date_time::DATE = tr.date_time::DATE - INTERVAL '1 day'  -- ← dynamic prev day
                        ORDER BY h2.date_time DESC
                        LIMIT 1
                    )
                    ELSE tr.prev_level
                END AS prev_level,
                tr.date_time,
                tdd.product,
                tdd.kl_per_mm
            FROM todays_readings tr
            LEFT JOIN (
                SELECT tank_no, product, location_sap_code, kl_per_mm FROM tank_dia_details
                ) tdd
                ON tr.sap_id = tdd.location_sap_code
                AND (
                    substring(tr.tank_name FROM '^[A-Z]+') = substring(tdd.tank_no FROM '^[A-Z]+')
                    OR
                    substring(tr.tank_name FROM '\d+')::int = substring(tdd.tank_no FROM '\d+')::int
                )
        ),
        t_dispatch AS (
            SELECT
                sap_id,
                tank_name,
                product,
                SUM(
                    CASE
                        WHEN COALESCE(prev_level, 0) > curr_level
                        THEN COALESCE(prev_level, 0) - curr_level
                        ELSE 0
                    END
                )::numeric * kl_per_mm::numeric  AS total_dispatch                
            FROM combined
            GROUP BY sap_id, tank_name, kl_per_mm, product
        )
        SELECT
            sap_id,
            product,
            ROUND(SUM(total_dispatch), 2) as sum
        FROM t_dispatch
        GROUP BY sap_id, product            
    """,

    "receipt": """
        WITH todays_readings AS (
            SELECT
                sap_id,
                tank_name,
                curr_level,
                date_time,
                LAG(curr_level) OVER (PARTITION BY tank_name, date_time::DATE ORDER BY date_time) AS prev_level,
                ROW_NUMBER() OVER (PARTITION BY tank_name, date_time::DATE ORDER BY date_time) AS rn
            FROM host_live_tank_details
            WHERE {} 
        ),
        combined AS (
            SELECT
                tr.sap_id,
                tr.tank_name,
                tr.curr_level,
                CASE
                    WHEN rn = 1 THEN (
                        SELECT curr_level FROM host_live_tank_details h2
                        WHERE h2.tank_name = tr.tank_name
                        AND h2.sap_id = tr.sap_id
                        AND h2.date_time::DATE = tr.date_time::DATE - INTERVAL '1 day'  -- ← dynamic prev day
                        ORDER BY h2.date_time DESC
                        LIMIT 1
                    )
                    ELSE tr.prev_level
                END AS prev_level,
                tr.date_time,
                tdd.product,
                tdd.kl_per_mm
            FROM todays_readings tr
            LEFT JOIN (
                SELECT tank_no, product, location_sap_code, kl_per_mm FROM tank_dia_details
                ) tdd
                ON tr.sap_id = tdd.location_sap_code
                AND (
                    substring(tr.tank_name FROM '^[A-Z]+') = substring(tdd.tank_no FROM '^[A-Z]+')
                    OR
                    substring(tr.tank_name FROM '\d+')::int = substring(tdd.tank_no FROM '\d+')::int
                )
        ),
        t_receipt AS (
            SELECT
                sap_id,
                tank_name,
                product,
                SUM(
                    CASE
                        WHEN COALESCE(prev_level, 0) < curr_level
                        THEN COALESCE(curr_level, 0) - prev_level
                        ELSE 0
                    END
                )::numeric * kl_per_mm::numeric AS total_receipt               
            FROM combined
            GROUP BY sap_id, tank_name, kl_per_mm, product
        )
        SELECT
            sap_id,
            product,
            ROUND(SUM(total_receipt), 2) as sum
        FROM t_receipt
        GROUP BY sap_id, product  
    """,

    "tank_dispatch" : """
        WITH todays_readings AS (
            SELECT
                sap_id,
                        tank_name,
                        curr_level,
                        date_time,
                        LAG(curr_level) OVER (PARTITION BY tank_name ORDER BY date_time) AS prev_level,
                        ROW_NUMBER() OVER (PARTITION BY tank_name ORDER BY date_time) AS rn
                    FROM host_live_tank_details
                    WHERE sap_id = '{}'
                    AND date_time::DATE = DATE '{}'    
                ),
                combined AS (
                    SELECT
                        tr.sap_id,
                        tr.tank_name,
                        tr.curr_level,
                    CASE
                    WHEN rn = 1 THEN (
                        SELECT curr_level FROM host_live_tank_details h2
                        WHERE h2.tank_name = tr.tank_name
                        AND h2.date_time::DATE = DATE '{}' --mention previous date
                        AND h2.sap_id = '{}'
                        ORDER BY h2.date_time DESC
                        LIMIT 1
                    )
                    ELSE tr.prev_level 
                END,
                    tr.date_time,
                    tdd.product,
                    tdd.kl_per_mm
                    FROM todays_readings tr left join
                    (select tank_no, product, kl_per_mm from tank_dia_details where location_sap_code='1856' )tdd
                    ON substring(tr.tank_name FROM '^[A-Z]+') 
                    = substring(tdd.tank_no   FROM '^[A-Z]+')
                OR substring(tr.tank_name FROM '\d+')::int
                    = substring(tdd.tank_no   FROM '\d+')::int
                    
                ),
                t_dispatch AS (
                SELECT
                    sap_id,
                    tank_name,
                    product,
                    SUM(
                        CASE
                            WHEN COALESCE(prev_level, 0) > curr_level 
                            THEN COALESCE(prev_level, 0) - curr_level
                            ELSE 0
                        END
                    )::numeric  * kl_per_mm::numeric  AS total_dispatch 
                FROM combined 
                GROUP BY sap_id, tank_name, kl_per_mm, product
                ORDER BY sap_id, tank_name
                )
                select 
                sap_id,
                product,
                ROUND(SUM(total_dispatch), 2) as sum
                from t_dispatch
                GROUP BY sap_id, product
        """,

    "tank_reciept" : """
                    WITH todays_readings AS (
                    SELECT
                        sap_id,
                        tank_name,
                        curr_level,
                        date_time,
                        LAG(curr_level) OVER (PARTITION BY tank_name ORDER BY date_time) AS prev_level,
                        ROW_NUMBER() OVER (PARTITION BY tank_name ORDER BY date_time) AS rn
                    FROM host_live_tank_details
                    WHERE sap_id = '{}'
                    AND date_time::DATE = DATE '{}'    
                ),
                combined AS (
                    SELECT
                        tr.sap_id,
                        tr.tank_name,
                        tr.curr_level,
                    CASE
                    WHEN rn = 1 THEN (
                        SELECT curr_level FROM host_live_tank_details h2
                        WHERE h2.tank_name = tr.tank_name
                        AND h2.date_time::DATE = DATE '{}' --mention previous date
                        AND h2.sap_id = '{}'
                        ORDER BY h2.date_time DESC
                        LIMIT 1
                    )
                    ELSE tr.prev_level 
                END,
                    tr.date_time,
                    tdd.product,
                    tdd.kl_per_mm
                    FROM todays_readings tr left join
                    (select tank_no, product, kl_per_mm from tank_dia_details where location_sap_code='1856' )tdd
                    ON substring(tr.tank_name FROM '^[A-Z]+') 
                    = substring(tdd.tank_no   FROM '^[A-Z]+')
                OR substring(tr.tank_name FROM '\d+')::int
                    = substring(tdd.tank_no   FROM '\d+')::int
                    
                ),
                t_dispatch AS (
                SELECT
                    sap_id,
                    tank_name,
                    product,
                    SUM(
                        CASE
                            WHEN COALESCE(prev_level, 0) < curr_level 
                            THEN COALESCE(curr_level, 0) - prev_level
                            ELSE 0
                        END
                    )::numeric  * kl_per_mm::numeric  AS total_dispatch 
                FROM combined 
                GROUP BY sap_id, tank_name, kl_per_mm, product
                ORDER BY sap_id, tank_name
                )
                select 
                sap_id,
                product,
                ROUND(SUM(total_dispatch), 2) as sum
                from t_dispatch
                GROUP BY sap_id, product
    """,
    
    "bcu_total_dispatch": """
        SELECT sap_id, stock as product, ROUND(SUM(bcu_net_totalizer), 2) as sum
        FROM public.host_day_end_details 
        WHERE {}
        GROUP BY sap_id, stock;
    """,

    "dispatch_average": """
        WITH todays_readings AS (
            SELECT
                sap_id,
                tank_name,
                curr_level,
                date_time,
                LAG(curr_level) OVER (PARTITION BY tank_name, date_time::DATE ORDER BY date_time) AS prev_level,
                ROW_NUMBER() OVER (PARTITION BY tank_name, date_time::DATE ORDER BY date_time) AS rn
            FROM host_live_tank_details
            --WHERE date_time::DATE BETWEEN CURRENT_DATE - INTERVAL '8 days' AND CURRENT_DATE - INTERVAL '1 day'),
            WHERE date_time::DATE BETWEEN DATE '2026-02-05' - INTERVAL '8 days' AND DATE '2026-02-05' - INTERVAL '1 day'
                  {}
        ),
        combined AS (
            SELECT
                tr.sap_id,
                tr.tank_name,
                tr.curr_level,
                CASE
                    WHEN rn = 1 THEN (
                        SELECT curr_level FROM host_live_tank_details h2
                        WHERE h2.tank_name = tr.tank_name
                        AND h2.sap_id = tr.sap_id
                        AND h2.date_time::DATE = tr.date_time::DATE - INTERVAL '1 day'
                        ORDER BY h2.date_time DESC
                        LIMIT 1
                    )
                ELSE tr.prev_level
                END AS prev_level,
                tr.date_time,
                tdd.product,
                tdd.kl_per_mm
            FROM todays_readings tr
            LEFT JOIN (
                SELECT tank_no, product, location_sap_code, kl_per_mm FROM tank_dia_details
                ) tdd
                ON tr.sap_id = tdd.location_sap_code
                AND (
                substring(tr.tank_name FROM '^[A-Z]+') = substring(tdd.tank_no FROM '^[A-Z]+')
                OR
                substring(tr.tank_name FROM '\d+')::int = substring(tdd.tank_no FROM '\d+')::int
                )
            ),
        t_dispatch AS (
            SELECT
                date_time::DATE AS dispatch_date,  -- ← added to group per day
                sap_id,
                tank_name,
                product,
                SUM(
                    CASE
                        WHEN COALESCE(prev_level, 0) > curr_level
                        THEN COALESCE(prev_level, 0) - curr_level
                    ELSE 0
                END
                )::numeric * kl_per_mm::numeric  AS total_dispatch
            FROM combined
            GROUP BY date_time::DATE, sap_id, tank_name, kl_per_mm, product
        ),
        daily_totals AS (
            SELECT
                dispatch_date,
                SUM(total_dispatch) AS day_total  -- ← total per day across all tanks/products
            FROM t_dispatch
            GROUP BY dispatch_date
        )
        SELECT
            ROUND(AVG(day_total), 2) AS seven_day_avg  -- ← average of 7 daily totals
        FROM daily_totals 
    """,

    "dispatch_average_prodwise_OLD" : """
        WITH todays_readings AS (
            SELECT
                sap_id,
                tank_name,
                curr_level,
                date_time,
                LAG(curr_level) OVER (PARTITION BY tank_name, date_time::DATE ORDER BY date_time) AS prev_level,
                ROW_NUMBER() OVER (PARTITION BY tank_name, date_time::DATE ORDER BY date_time) AS rn
            FROM host_live_tank_details
            WHERE date_time::DATE BETWEEN DATE '2026-02-05' - INTERVAL '8 days' AND DATE '2026-02-05' - INTERVAL '1 day'
                  {}
        ),
        combined AS (
            SELECT
                tr.sap_id,
                tr.tank_name,
                tr.curr_level,
                CASE
                WHEN rn = 1 THEN (
                    SELECT curr_level FROM host_live_tank_details h2
                    WHERE h2.tank_name = tr.tank_name
                    AND h2.sap_id = tr.sap_id
                    AND h2.date_time::DATE = tr.date_time::DATE - INTERVAL '1 day'
                    ORDER BY h2.date_time DESC
                    LIMIT 1
                )
                ELSE tr.prev_level
                END AS prev_level,
                tr.date_time,
                tdd.product,
                tdd.kl_per_mm
            FROM todays_readings tr
            LEFT JOIN (
                SELECT tank_no, product, location_sap_code, kl_per_mm FROM tank_dia_details
            ) tdd
            ON tr.sap_id = tdd.location_sap_code
            AND (
                substring(tr.tank_name FROM '^[A-Z]+') = substring(tdd.tank_no FROM '^[A-Z]+')
                OR
                substring(tr.tank_name FROM '\d+')::int = substring(tdd.tank_no FROM '\d+')::int
            )
        ),
        t_dispatch AS (
            SELECT
                date_time::DATE AS dispatch_date,  -- ← added to group per day
                sap_id,
                tank_name,
                product,
                SUM(
                    CASE
                        WHEN COALESCE(prev_level, 0) > curr_level
                        THEN COALESCE(prev_level, 0) - curr_level
                    ELSE 0
                END
                )::numeric * kl_per_mm::numeric  AS total_dispatch
            FROM combined
                GROUP BY date_time::DATE, sap_id, tank_name, kl_per_mm, product
        ),
        daily_totals AS (
            SELECT
		        product,
                dispatch_date,
                SUM(total_dispatch) AS day_total  -- ← total per day across all tanks/products
            FROM t_dispatch
            GROUP BY dispatch_date, product
        )
        SELECT
	        product,
            ROUND(AVG(day_total), 2) AS seven_day_avg  -- ← average of 7 daily totals
            FROM daily_totals WHERE NOT (daily_totals IS NULL)
            GROUP BY product
    """,
    "dispatch_average_prodwise": """
       WITH todays_readings AS (
    SELECT
        sap_id,
        tank_name,
        curr_level,
        date_time,
        LAG(curr_level) OVER (PARTITION BY tank_name, date_time::DATE ORDER BY date_time) AS prev_level,
        ROW_NUMBER() OVER (PARTITION BY tank_name, date_time::DATE ORDER BY date_time) AS rn
    FROM host_live_tank_details
    WHERE date_time::DATE BETWEEN DATE '2026-02-05' - INTERVAL '8 days' AND DATE '2026-02-05' - INTERVAL '1 day'
    {}
),
combined AS (
    SELECT
        tr.sap_id,
        tr.tank_name,
        tr.curr_level,
        CASE
            WHEN rn = 1 THEN (
                SELECT curr_level FROM host_live_tank_details h2
                WHERE h2.tank_name = tr.tank_name
                AND h2.sap_id = tr.sap_id
                AND h2.date_time::DATE = tr.date_time::DATE - INTERVAL '1 day'
                ORDER BY h2.date_time DESC
                LIMIT 1
            )
            ELSE tr.prev_level
        END AS prev_level,
        tr.date_time,
        CASE tdd.product
            WHEN 'ETHANOL'   THEN 'ETHANOL'
            WHEN 'Ethanol'   THEN 'ETHANOL'
            WHEN 'ETH'       THEN 'ETHANOL'
            WHEN 'BIODIESEL' THEN 'BIODIESEL'
            WHEN 'Biodiesel' THEN 'BIODIESEL'
            WHEN 'BIO-HSD'   THEN 'BIODIESEL'
            ELSE tdd.product  -- fallback: keep as-is for unmapped products
        END AS product,
        tdd.kl_per_mm
    FROM todays_readings tr
    LEFT JOIN (
        SELECT tank_no, product, location_sap_code, kl_per_mm FROM tank_dia_details
    ) tdd
        ON tr.sap_id = tdd.location_sap_code
        AND (
            substring(tr.tank_name FROM '^[A-Z]+') = substring(tdd.tank_no FROM '^[A-Z]+')
            OR
            substring(tr.tank_name FROM '\d+')::int = substring(tdd.tank_no FROM '\d+')::int
        )
),
t_dispatch AS (
    SELECT
        date_time::DATE AS dispatch_date,
        sap_id,
        tank_name,
        product,
        SUM(
            CASE
                WHEN COALESCE(prev_level, 0) > curr_level
                THEN COALESCE(prev_level, 0) - curr_level
                ELSE 0
            END
        )::numeric * kl_per_mm::numeric AS total_dispatch
    FROM combined
    GROUP BY date_time::DATE, sap_id, tank_name, kl_per_mm, product
),
daily_totals AS (
    SELECT
        product,
        dispatch_date,
        SUM(total_dispatch) AS day_total
    FROM t_dispatch
    GROUP BY dispatch_date, product
)
SELECT
    product,
    ROUND(AVG(day_total), 2) AS seven_day_avg
FROM daily_totals
WHERE NOT (daily_totals IS NULL)
GROUP BY product            
""",

"tank_ullage" : """
    with ullage_data as (
        select
            tank_details.gross_capacity_kl as capacity,
            tank_details.product as "product",
	        ROUND(tank_details.gross_capacity_kl - (tank_details.kl_per_mm::numeric * live_data.curr_level::numeric), 2) as "ullage"
        FROM (
            SELECT * FROM host_live_tank_details 
            --WHERE date_time::DATE = CURRENT_DATE 
            WHERE date_time::DATE BETWEEN DATE '2026-02-05' AND DATE ' 2026-02-05' 
                  {}
            ) live_data
        LEFT JOIN public.tank_dia_details tank_details  
        ON live_data.sap_id = tank_details.location_sap_code 
            AND (
                substring(live_data.tank_name FROM '^[A-Z]+') = substring(tank_details.tank_no FROM '^[A-Z]+')
            OR
                substring(live_data.tank_name FROM '\d+')::int = substring(tank_details.tank_no FROM '\d+')::int
                )
    ) 
    select "product", SUM(capacity) as capacity, SUM("ullage") as ullage
    FROM ullage_data GROUP BY "product"
    """,

"daywise_trends" : """
        WITH todays_readings AS (
            SELECT
                sap_id,
                tank_name,
                curr_level,
                date_time::DATE,
                LAG(curr_level) OVER (PARTITION BY tank_name, date_time::DATE ORDER BY date_time) AS prev_level,
                ROW_NUMBER() OVER (PARTITION BY tank_name, date_time::DATE ORDER BY date_time) AS rn
            FROM host_live_tank_details
            WHERE {}
        ),
        combined AS (
            SELECT
                tr.sap_id,
                tr.tank_name,
                tr.curr_level,
                CASE
                    WHEN rn = 1 THEN (
                        SELECT curr_level FROM host_live_tank_details h2
                        WHERE h2.tank_name = tr.tank_name
                        AND h2.sap_id = tr.sap_id
                        AND h2.date_time::DATE = tr.date_time::DATE - INTERVAL '1 day'  -- ← dynamic prev day
                        ORDER BY h2.date_time DESC
                        LIMIT 1
                    )
                    ELSE tr.prev_level
                END AS prev_level,
                tr.date_time,
                tdd.product,
                tdd.kl_per_mm
            FROM todays_readings tr
            LEFT JOIN (
                SELECT tank_no, product, location_sap_code, kl_per_mm FROM tank_dia_details
                ) tdd
                ON tr.sap_id = tdd.location_sap_code
                AND (
                    substring(tr.tank_name FROM '^[A-Z]+') = substring(tdd.tank_no FROM '^[A-Z]+')
                    OR
                    substring(tr.tank_name FROM '\d+')::int = substring(tdd.tank_no FROM '\d+')::int
                )
        ),
        t_dispatch AS (
            SELECT
                sap_id,
                tank_name,
                product,
				date_time,
                SUM(
                    CASE
                        WHEN COALESCE(prev_level, 0) > curr_level
                        THEN COALESCE(prev_level, 0) - curr_level
                        ELSE 0
                    END
                )::numeric * kl_per_mm::numeric  AS total_dispatch                
            FROM combined
            GROUP BY sap_id, tank_name, date_time, kl_per_mm, product
        ),
		t_reciept AS (
			SELECT 
			 sap_id,
                tank_name,
                product,
				date_time,
                SUM(
                    CASE
                        WHEN COALESCE(prev_level, 0) < curr_level
                        THEN COALESCE(curr_level, 0) - prev_level
                        ELSE 0
                    END
                )::numeric * kl_per_mm::numeric  AS total_reciept               
            FROM combined
            GROUP BY sap_id, tank_name, date_time, kl_per_mm, product
		)
        SELECT
            dis.product,
			dis.date_time,
            ROUND(SUM(dis.total_dispatch), 2) as dispatch,
			ROUND(SUM(rec.total_reciept), 2) as reciept
        FROM t_dispatch as dis LEFT JOIN t_reciept as rec ON 
		 dis.sap_id = rec.sap_id AND dis.tank_name = rec.tank_name AND dis.product = rec.product AND dis.date_time = rec.date_time
        GROUP BY dis.date_time, dis.product
    """,

"ullage_daywise_trends" : """
    with ullage_data as (select 
	live_data.date_time::DATE,
	tank_details.dead_stock_kl,
	tank_details.gross_capacity_kl as capacity,
    ROUND((tank_details.kl_per_mm::numeric * live_data.curr_level::numeric - tank_details.dead_stock_kl), 2) as "available_stock",
    tank_details.product as "product",
    ROUND(tank_details.gross_capacity_kl - (tank_details.kl_per_mm::numeric * live_data.curr_level::numeric), 2) as "ullage"
FROM (
    SELECT * FROM host_live_tank_details WHERE {}
) live_data
LEFT JOIN public.tank_dia_details tank_details  
    ON live_data.sap_id = tank_details.location_sap_code 
    AND (
        substring(live_data.tank_name FROM '^[A-Z]+') = substring(tank_details.tank_no FROM '^[A-Z]+')
        OR
        substring(live_data.tank_name FROM '\d+')::int = substring(tank_details.tank_no FROM '\d+')::int
    )
) select "product", date_time,SUM(available_stock) AS available_stock, SUM(dead_stock_kl) as dead_stock, SUM(capacity) AS capacity, SUM("ullage") as ullage
FROM ullage_data GROUP BY date_time, "product"
    """

}

product_mapping = {
    "1856" : {
        "host_day_end_details" : {
            "ATF": "ATF",
            "BIO DIESEL": "BIODIESEL",
            "BS VI HSD": "HSD",
            "BS VI MS": "MS",
            "ETHANOL": "ETHANOL"
        }
    },
    "1845" : {
        "host_day_end_details" : {
            "ETHANOL": "ETHANOL",
            "HEXANE": "HEXANE",
            "BS VI HSD": "HSD",
            "BS VI MS": "MS",
            "MTO": "MTO",
            "SKO": "SKO",
            "SOLVENT": "SOLVENT"
        }
    },
    "1146": {
        "host_day_end_details" : {
            "BS VI HSD": "HSD",
            "BIO DIESEL": "Biodiesel",
            "BS VI MS": "MS",
            "ETHANOL": "Ethanol"
        }
    },
    "1216": {
        "host_day_end_details" : {
            "BS VI HSD": "HSD"
        }
    }
}

product_name_mapping = {
    'ATF': 'ATF',
    'MS' : 'MS',
    "BS VI MS": "MS",
    "BS VI HSD": "HSD",
    'HSD': 'HSD',
    'ETHANOL': 'ETHANOL',
    'Ethanol': 'ETHANOL',
    'ETH': 'ETHANOL',
    'BIODIESEL': 'BIODIESEL',
    'Biodiesel' : 'BIODIESEL',
    'BIO DIESEL': 'BIODIESEL',
    'BIO-HSD' : 'BIODIESEL',
    'SOLVENT': 'SOLVENT',
    'HEXANE': 'HEXANE',
    'SKO': 'SKO',
    'MTO': 'MTO'

}

ACTION_MAP = {
        "tank_details":  "tank_details",
        "tank_dispatch": "dispatch",
        "tank_receipt":  "receipt",
        "bcu_dispacth":  "bcu_total_dispatch",
        "total_dispatch":"dispatch",
        "total_receipt": "receipt",
        "total_product": "tank_details"
    }

SUM_ACTIONS = {"total_dispatch": "sum", "total_receipt": "sum"}

# "1892"	"BIO-HSD"
# "1892"	"ETH"
# "1892"	"HSD"
# "1892"	"MS"