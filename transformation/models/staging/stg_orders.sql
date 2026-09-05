-- Limpa e padroniza a tabela raw de pedidos.
-- Esta é a tabela mais importante do projeto: dela derivamos o atraso de entrega.
with source as (
    select * from {{ source('raw', 'olist_orders_dataset') }}
)

select
    order_id,
    customer_id,
    lower(trim(order_status)) as order_status,
    order_purchase_timestamp::timestamp as order_purchase_timestamp,
    order_approved_at::timestamp as order_approved_at,
    order_delivered_carrier_date::timestamp as order_delivered_carrier_date,
    order_delivered_customer_date::timestamp as order_delivered_customer_date,
    order_estimated_delivery_date::timestamp as order_estimated_delivery_date
from source
