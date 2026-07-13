-- Staging model: customer entity extracted from raw.sales_orders.
--
-- The vertical slice has a single source (sales_orders), so the customer
-- dimension is derived rather than sourced from a dedicated CRM feed
-- (that lands here once connectors/salesforce is implemented). Exists so
-- the mart layer has a real dimension to enforce a `relationships` test
-- against (see intermediate/schema.yml).

with source as (

    select * from {{ source('raw', 'sales_orders') }}
    where customer_id is not null

),

customers as (

    select distinct
        customer_id,
        customer_name
    from source

)

select * from customers
