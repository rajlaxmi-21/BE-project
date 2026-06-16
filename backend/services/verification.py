import psycopg2

def verify_deforestation_against_permits():
    conn = psycopg2.connect(
        dbname="FinalYearProject",
        host="localhost",
        port="5432"
    )
    cur = conn.cursor()

    query = """
    DROP TABLE IF EXISTS verification_results;

    CREATE TABLE verification_results AS
    WITH permit_matches AS (
        SELECT
            d.detection_id,
            d.detected_at,
            d.geometry,
            d.centroid,
            p.permit_id,

            -- Areas
            ST_Area(d.geometry::geography) AS detected_area,
            ST_Area(ST_Intersection(d.geometry, p.geometry)::geography) AS intersection_area,

            -- Coverage
            ST_Area(ST_Intersection(d.geometry, p.geometry)::geography)
            / NULLIF(ST_Area(d.geometry::geography), 0) AS coverage_ratio,

            ROW_NUMBER() OVER (
                PARTITION BY d.detection_id
                ORDER BY ST_Area(ST_Intersection(d.geometry, p.geometry)::geography) DESC
            ) AS rn

        FROM detected_deforestation d
        LEFT JOIN permits p
            ON ST_Intersects(d.geometry, p.geometry)
            AND p.status = 'active'
            AND d.detected_at >= p.issue_date
    ),

    best_matches AS (
        SELECT *
        FROM permit_matches
        WHERE rn = 1
    )

    SELECT
        detection_id,
        detected_at,
        permit_id,

        ROUND(detected_area::numeric, 2) AS area_m2,
        ROUND(COALESCE(intersection_area, 0)::numeric, 2) AS intersection_area_m2,
        ROUND(COALESCE(coverage_ratio, 0)::numeric, 3) AS coverage_ratio,

        CASE
            WHEN COALESCE(coverage_ratio, 0) >= 0.8 THEN 'PERMITTED'
            ELSE 'POTENTIALLY_ILLEGAL'
        END AS status,

        centroid,
        geometry

    FROM best_matches;
    """

    cur.execute(query)
    conn.commit()

    cur.close()
    conn.close()

    print("Verification completed. Results stored in verification_results table.")



def calculate_summary_stats():
    conn = psycopg2.connect(
        dbname="FinalYearProject",
        host="localhost",
        port="5432"
    )
    cur = conn.cursor()

    query = """
    SELECT
    ROUND(COALESCE(SUM(area_m2), 0) / 1000000.0, 4) AS total_green_cover_loss_km2,

    ROUND(COALESCE(SUM(CASE 
        WHEN status = 'POTENTIALLY_ILLEGAL' THEN area_m2 
        ELSE 0 
    END), 0) / 1000000.0, 4) AS illegal_area_km2,

    ROUND(COALESCE(SUM(CASE 
        WHEN status = 'PERMITTED' THEN area_m2 
        ELSE 0 
    END), 0) / 1000000.0, 4) AS legal_area_km2,

    COUNT(CASE 
        WHEN status = 'PERMITTED' THEN 1 
    END) AS total_legal_deforestation_count

    FROM verification_results;
    """

    cur.execute(query)
    result = cur.fetchone()

    stats = {
        "total_green_cover_loss_km2": result[0] or 0,
        "illegal_area_km2": result[1] or 0,
        "legal_area_km2": result[2] or 0,
        "total_legal_deforestation_count": result[3] or 0
    }

    cur.close()
    conn.close()

    return stats

def get_top_illegal_polygons(limit=5):

    conn = psycopg2.connect(
        dbname="FinalYearProject",
        host="localhost",
        port="5432"
    )

    cur = conn.cursor()

    query = """
    SELECT
        detection_id,
        area_m2,
        ST_X(centroid) AS lon,
        ST_Y(centroid) AS lat

    FROM verification_results

    WHERE status = 'POTENTIALLY_ILLEGAL'

    ORDER BY area_m2 DESC

    LIMIT %s;
    """

    cur.execute(query, (limit,))
    rows = cur.fetchall()

    polygons = []

    for row in rows:

        polygons.append({
            "id": f"P{row[0]}",
            "area": round(float(row[1]) / 1000000.0, 4),
            "centroid": [float(row[2]), float(row[3])]
        })

    cur.close()
    conn.close()

    return polygons