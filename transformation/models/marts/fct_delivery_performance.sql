-- Tabela fato principal do projeto: 1 linha por pedido entregue, com atraso e review.
-- Alimenta diretamente o dashboard e o treino do modelo de ML.
with base as (
    select * from {{ ref('int_order_reviews_joined') }}
),

customer_info as (
    select customer_id, customer_state, customer_city from {{ ref('dim_customers') }}
),

order_item_summary as (
    select
        order_id,
        count(*) as n_items,
        sum(item_total_value) as order_total_value,
        avg(freight_value) as avg_freight_value,
        min(seller_state) as primary_seller_state,
        min(product_category_name) as primary_product_category
    from {{ ref('fct_order_items') }}
    group by order_id
),

payment_info as (
    select order_id, payment_type, payment_installments, payment_value
    from {{ ref('stg_order_payments') }}
)

select
    b.order_id,
    b.customer_id,
    c.customer_state,
    c.customer_city,
    b.order_purchase_timestamp,
    b.order_delivered_customer_date,
    b.order_estimated_delivery_date,
    b.delay_days,
    b.is_delayed,
    b.delay_bucket,
    b.total_delivery_days,
    b.estimated_delivery_days,
    b.purchase_month,
    b.purchase_day_of_week,
    b.review_score,
    oi.n_items,
    oi.order_total_value,
    oi.avg_freight_value,
    oi.primary_seller_state,
    oi.primary_product_category,
    p.payment_type,
    p.payment_installments,
    p.payment_value
from base b
left join customer_info c on c.customer_id = b.customer_id
left join order_item_summary oi on oi.order_id = b.order_id
left join payment_info p on p.order_id = b.order_id
