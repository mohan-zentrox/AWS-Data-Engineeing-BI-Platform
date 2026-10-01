-- Staging model: customer entity extracted from raw.sales_orders.
--
-- The vertical slice has a single source (sales_orders), so the customer
-- dimension is derived rather than sourced from a dedicated CRM feed
-- (that lands here once connectors/salesforce is implemented). Exists so
-- the mart layer has a real dimension to enforce a `relationships` test
-- against (see intermediate/schema.yml).
--
-- Grain: exactly one row per customer_id. This must be enforced here, not
-- assumed: `select distinct customer_id, customer_name` would emit one row
-- per *name spelling* per customer, so a single customer_id arriving with
-- two spellings (a rename, a trailing space, a casing change) would both
-- fail the `unique` test below and fan out the left join in
-- int_sales_orders_enriched, double-counting that customer's revenue in
-- mart_sales_daily. Picking the name from the customer's most recent order
-- keeps the grain at one row regardless of source spelling drift.

with source as (

    select * from {{ source('raw', 'sales_orders') }}
    where customer_id is not null

),

ranked as (

    select
        customer_id,
        customer_name,
        row_number() over (
            partition by customer_id
            order by order_date desc nulls last, order_id desc
        )                                           as recency_rank

    from source

),

customers as (

    select
        customer_id,
        customer_name

    from ranked
    where recency_rank = 1

)

select * from customers
