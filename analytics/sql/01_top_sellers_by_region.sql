-- Top 5 vendedores por receita dentro de cada estado (window function: RANK + PARTITION BY)
-- Roda em cima do mart marts.fct_seller_performance
with seller_revenue as (
    select
        seller_id,
        seller_state,
        total_revenue,
        total_orders
    from marts.fct_seller_performance
)

select
    seller_id,
    seller_state,
    total_revenue,
    total_orders,
    rank() over (partition by seller_state order by total_revenue desc) as rank_in_state,
    round(
        total_revenue / nullif(sum(total_revenue) over (partition by seller_state), 0) * 100,
        2
    ) as pct_of_state_revenue
from seller_revenue
qualify rank_in_state <= 5
order by seller_state, rank_in_state;

-- Nota: QUALIFY é suportado no BigQuery/Snowflake/DuckDB. Em Postgres puro, substitua por:
-- select * from (
--     select seller_id, seller_state, total_revenue, total_orders,
--            rank() over (partition by seller_state order by total_revenue desc) as rank_in_state
--     from seller_revenue
-- ) ranked
-- where rank_in_state <= 5
-- order by seller_state, rank_in_state;
