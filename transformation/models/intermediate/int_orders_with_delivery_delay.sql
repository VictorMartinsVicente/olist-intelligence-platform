-- Núcleo da lógica de negócio: calcula se o pedido atrasou e por quantos dias,
-- comparando a data real de entrega com a data estimada.
with orders as (
    select * from {{ ref('stg_orders') }}
    where order_status = 'delivered'
      and order_delivered_customer_date is not null
),

with_delay as (
    select
        order_id,
        customer_id,
        order_purchase_timestamp,
        order_approved_at,
        order_delivered_carrier_date,
        order_delivered_customer_date,
        order_estimated_delivery_date,

        extract(epoch from (order_delivered_customer_date - order_estimated_delivery_date)) / 86400.0
            as delay_days,

        extract(epoch from (order_delivered_customer_date - order_purchase_timestamp)) / 86400.0
            as total_delivery_days,

        extract(epoch from (order_estimated_delivery_date - order_purchase_timestamp)) / 86400.0
            as estimated_delivery_days,

        extract(month from order_purchase_timestamp) as purchase_month,
        extract(dow from order_purchase_timestamp) as purchase_day_of_week

    from orders
)

select
    *,
    case when delay_days > 0 then 1 else 0 end as is_delayed,
    case
        when delay_days > 7 then 'atraso_grave'
        when delay_days > 0 then 'atraso_leve'
        when delay_days > -3 then 'no_prazo'
        else 'entregue_adiantado'
    end as delay_bucket
from with_delay
