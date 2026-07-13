-- Singular test: mart_sales_daily's grain is (order_date, region).
-- A dbt test passes when the query returns zero rows, so we select the
-- duplicate keys, if any.
--
-- Hand-rolled instead of dbt_utils.unique_combination_of_columns so this
-- repo has no package-manager dependency (dbt deps / packages.yml) for CI
-- to run offline.

select
    order_date,
    region,
    count(*) as row_count
from {{ ref('mart_sales_daily') }}
group by order_date, region
having count(*) > 1
