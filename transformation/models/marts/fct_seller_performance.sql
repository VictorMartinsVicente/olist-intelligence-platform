-- Performance agregada por vendedor: base para o ranking de vendedores no dashboard
select
    seller_id,
    seller_state,
    seller_city,
    count(distinct order_id) as total_orders,
    sum(item_total_value) as total_revenue,
    avg(price) as avg_item_price
from {{ ref('fct_order_items') }}
group by seller_id, seller_state, seller_city
