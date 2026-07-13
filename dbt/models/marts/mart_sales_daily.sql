-- Mart: daily sales summary. Grain: one row per (order_date, region).
-- Serves BI (QuickSight/Superset) daily revenue/order-volume dashboards.
--
-- Uses CASE WHEN instead of the SQL FILTER clause for aggregates that need
-- it, since the serving target is Amazon Redshift (see
-- dbt/profiles.yml.example) which historically lacks FILTER support —
-- keeping this portable across the postgres (dev) and redshift targets.

with enriched as (

    select * from {{ ref('int_sales_orders_enriched') }}

),

daily as (

    select
        order_date,
        region,
        count(*)                                                        as total_orders,
        sum(case when is_completed then 1 else 0 end)                   as completed_orders,
        sum(case when is_cancelled then 1 else 0 end)                   as cancelled_orders,
        count(distinct customer_id)                                     as unique_customers,
        sum(order_amount)                                               as total_revenue,
        sum(case when is_completed then order_amount else 0 end)        as completed_revenue,
        sum(quantity)                                                   as total_units

    from enriched
    group by order_date, region

)

select * from daily
