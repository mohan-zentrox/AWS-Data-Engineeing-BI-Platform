-- Singular test: revenue aggregates in mart_sales_daily should never be
-- negative for this source (no returns/refunds modeled in the vertical
-- slice yet). Passes when zero rows are returned.

select *
from {{ ref('mart_sales_daily') }}
where total_revenue < 0
   or completed_revenue < 0
