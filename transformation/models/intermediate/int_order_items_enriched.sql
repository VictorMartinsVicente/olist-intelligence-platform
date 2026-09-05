-- Enriquece itens de pedido com informação de vendedor e produto, e calcula receita total do item
with items as (
    select * from {{ ref('stg_order_items') }}
),

sellers as (
    select seller_id, seller_state, seller_city from {{ ref('stg_sellers') }}
),

products as (
    select product_id, product_category_name from {{ ref('stg_products') }}
)

select
    i.order_id,
    i.order_item_id,
    i.product_id,
    p.product_category_name,
    i.seller_id,
    s.seller_state,
    s.seller_city,
    i.price,
    i.freight_value,
    (i.price + i.freight_value) as item_total_value
from items i
left join sellers s on s.seller_id = i.seller_id
left join products p on p.product_id = i.product_id
