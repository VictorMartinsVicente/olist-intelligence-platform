-- Pergunta de negócio central do projeto: atraso na entrega derruba a nota de review?
-- Compara nota média e distribuição de notas por faixa de atraso.

select
    delay_bucket,
    count(*) as total_orders,
    round(avg(review_score), 2) as avg_review_score,
    round(avg(delay_days), 1) as avg_delay_days,
    round(100.0 * sum(case when review_score <= 2 then 1 else 0 end) / count(*), 1)
        as pct_bad_reviews,
    round(100.0 * sum(case when review_score = 5 then 1 else 0 end) / count(*), 1)
        as pct_five_star
from marts.fct_delivery_performance
group by delay_bucket
order by
    case delay_bucket
        when 'entregue_adiantado' then 1
        when 'no_prazo' then 2
        when 'atraso_leve' then 3
        when 'atraso_grave' then 4
    end;

-- Achado esperado: pct_bad_reviews deve subir consideravelmente em 'atraso_grave'
-- comparado a 'no_prazo' -- esse é o argumento de negócio para investir em previsão de atraso.
