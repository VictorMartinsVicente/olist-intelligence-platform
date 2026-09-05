-- Junta pedidos + atraso + review em um só grão (1 linha por pedido entregue e avaliado)
with delay as (
    select * from {{ ref('int_orders_with_delivery_delay') }}
),

reviews as (
    select order_id, review_score, review_creation_date
    from {{ ref('stg_order_reviews') }}
)

select
    d.*,
    r.review_score,
    r.review_creation_date
from delay d
inner join reviews r on r.order_id = d.order_id
