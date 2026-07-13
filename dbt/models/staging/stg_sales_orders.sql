-- Staging model: typed/renamed pass-through of raw.sales_orders.
--
-- One row per sales order line item. Column names and types here define the
-- contract the intermediate/mart layers build on; upstream schema drift
-- should be caught here first (see schema.yml tests).

with source as (

    select * from {{ source('raw', 'sales_orders') }}

),

renamed as (

    select
        order_id,
        customer_id,
        customer_name,
        cast(order_date as date)                  as order_date,
        product_sku,
        product_name,
        cast(quantity as integer)                  as quantity,
        cast(unit_price as numeric(12, 2))          as unit_price,
        cast(order_amount as numeric(12, 2))        as order_amount,
        upper(order_status)                         as order_status,
        upper(region)                                as region,
        loaded_at

    from source
    where order_id is not null

)

select * from renamed
