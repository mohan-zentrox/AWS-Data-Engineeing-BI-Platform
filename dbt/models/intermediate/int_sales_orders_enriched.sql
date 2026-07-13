-- Intermediate model: sales order line items enriched with derived fields
-- used by one or more marts. Kept 1:1 at the grain of stg_sales_orders
-- (one row per order line item) — no aggregation happens here.

with orders as (

    select * from {{ ref('stg_sales_orders') }}

),

customers as (

    select * from {{ ref('stg_customers') }}

),

enriched as (

    select
        orders.order_id,
        orders.customer_id,
        customers.customer_name,
        orders.order_date,
        date_trunc('month', orders.order_date)      as order_month,
        orders.product_sku,
        orders.product_name,
        orders.quantity,
        orders.unit_price,
        orders.order_amount,
        orders.order_status,
        orders.region,
        (orders.order_status = 'COMPLETED')          as is_completed,
        (orders.order_status = 'CANCELLED')          as is_cancelled

    from orders
    left join customers on orders.customer_id = customers.customer_id

)

select * from enriched
