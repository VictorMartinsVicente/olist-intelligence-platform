-- Limpa e padroniza a tabela raw de itens do pedido
with source as (
    select * from {{ source('raw', 'olist_order_items_dataset') }}
)

select
    order_id,
    order_item_id::int as order_item_id,
    product_id,
    seller_id,
    price::numeric as price,
    freight_value::numeric as freight_value
from source
