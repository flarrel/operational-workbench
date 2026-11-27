CREATE TABLE raw_daily (
    id INTEGER PRIMARY KEY,
    day TEXT NOT NULL,
    site TEXT NOT NULL,
    sales INTEGER NOT NULL,
    book_stock INTEGER NOT NULL,
    counted_stock INTEGER NOT NULL,
    sensor REAL
);

CREATE VIEW daily AS
SELECT raw.*
FROM raw_daily AS raw
JOIN (
    SELECT MIN(id) AS id
    FROM raw_daily
    GROUP BY site, day
) AS first_record USING (id);

CREATE VIEW quality AS
SELECT site, day, 'duplicate' AS issue
FROM raw_daily
GROUP BY site, day
HAVING COUNT(*) > 1
UNION ALL
SELECT site, day, 'missing_sensor'
FROM daily
WHERE sensor IS NULL;

CREATE VIEW sales_reference AS
SELECT *,
       AVG(sales) OVER (
           PARTITION BY site, strftime('%w', day)
           ORDER BY day ROWS BETWEEN 4 PRECEDING AND 1 PRECEDING
       ) AS baseline,
       COUNT(*) OVER (
           PARTITION BY site, strftime('%w', day)
           ORDER BY day ROWS BETWEEN 4 PRECEDING AND 1 PRECEDING
       ) AS reference_days
FROM daily;

CREATE VIEW signals AS
SELECT id, day, site, 'sales_spike' AS kind,
       sales AS actual, ROUND(baseline, 1) AS reference
FROM sales_reference
WHERE reference_days = 4 AND sales >= baseline * 1.6
UNION ALL
SELECT id, day, site, 'stock_gap', counted_stock, book_stock
FROM daily
WHERE ABS(counted_stock - book_stock) >= 25
UNION ALL
SELECT id, day, site, 'sensor_exception', sensor, 49.0
FROM daily
WHERE sensor > 49.0;
