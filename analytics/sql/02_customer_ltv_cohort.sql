-- Análise de cohort: agrupa clientes pelo mês da primeira compra e mede
-- receita acumulada nos meses seguintes (LTV por cohort)
-- Usa CTE recursiva-like (window functions encadeadas) + agregação por cohort

with customer_orders as (
    select
        customer_id,
        order_id,
        order_purchase_timestamp,
        order_total_value
    from marts.fct_delivery_performance
),

first_purchase as (
    select
        customer_id,
        date_trunc('month', min(order_purchase_timestamp)) as cohort_month
    from customer_orders
    group by customer_id
),

orders_with_cohort as (
    select
        co.customer_id,
        fp.cohort_month,
        date_trunc('month', co.order_purchase_timestamp) as order_month,
        co.order_total_value
    from customer_orders co
    join first_purchase fp on fp.customer_id = co.customer_id
),

cohort_monthly_revenue as (
    select
        cohort_month,
        order_month,
        -- diferença em meses entre a compra e o mês de entrada na cohort
        (extract(year from order_month) - extract(year from cohort_month)) * 12
            + (extract(month from order_month) - extract(month from cohort_month)) as month_number,
        sum(order_total_value) as revenue,
        count(distinct customer_id) as active_customers
    from orders_with_cohort
    group by cohort_month, order_month
)

select
    cohort_month,
    month_number,
    active_customers,
    revenue,
    sum(revenue) over (
        partition by cohort_month order by month_number
        rows between unbounded preceding and current row
    ) as cumulative_revenue
from cohort_monthly_revenue
order by cohort_month, month_number;
