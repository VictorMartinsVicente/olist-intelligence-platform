# Model Card — Previsão de Atraso na Entrega

## Tarefa
Classificação binária: o pedido vai ser entregue depois da data estimada (`is_delayed = 1`)
ou não (`is_delayed = 0`)?

## Dados de treino
- Fonte: `marts.fct_delivery_performance` (gerado pelo dbt a partir do dataset **real** Olist,
  baixado do Kaggle)
- Apenas pedidos com status `delivered` e data de entrega preenchida (95.137 pedidos)
- Split: 80/20 treino/teste, estratificado pela variável alvo
- **Taxa real de atraso: 8,1%** — dataset bastante desbalanceado, o que exigiu tratamento
  específico (ver seção de achados abaixo)

## Features usadas
| Feature | Tipo | Descrição |
|---|---|---|
| `estimated_delivery_days` | numérica | Prazo estimado em dias no momento da compra |
| `order_total_value` | numérica | Valor total do pedido (produtos + frete) |
| `avg_freight_value` | numérica | Valor médio do frete dos itens do pedido |
| `n_items` | numérica | Número de itens no pedido |
| `payment_installments` | numérica | Número de parcelas do pagamento |
| `purchase_month` | numérica | Mês da compra (sazonalidade) |
| `purchase_day_of_week` | numérica | Dia da semana da compra |
| `customer_state` | categórica | Estado do cliente |
| `primary_seller_state` | categórica | Estado do principal vendedor do pedido |
| `primary_product_category` | categórica | Categoria principal do produto |
| `payment_type` | categórica | Forma de pagamento |

## Modelos avaliados (dataset real do Kaggle, 95.137 pedidos)
| Modelo | AUC | F1 | Recall |
|---|---|---|---|
| Regressão Logística (baseline) | 0.691 | 0.219 | 0.624 |
| **Gradient Boosting (escolhido)** | **0.772** | **0.293** | **0.670** |

## ⚠️ Achado importante: por que a seleção do modelo NÃO usa apenas AUC

Na primeira rodada de treino, o Gradient Boosting teve a maior AUC (0.77) mas um
**recall de apenas 0.01** — ou seja, ele quase nunca previa atraso, simplesmente
"apostando" na classe majoritária (não atrasado) e ainda assim conseguindo uma AUC
enganosa. Isso acontece porque **apenas 8,1% dos pedidos atrasam**: um classificador
que sempre prevê "não vai atrasar" já acerta ~92% das vezes, e métricas agregadas
como acurácia ou até AUC podem mascarar isso.

**Correção aplicada**: usamos `sample_weight` balanceado (`compute_sample_weight`)
no treino de ambos os modelos, e trocamos o **critério de seleção do melhor modelo
de AUC para F1** — métrica que penaliza um modelo que ignora a classe minoritária.
Depois da correção, o Gradient Boosting balanceado manteve a melhor AUC *e* passou
a ter recall de 0.67, se tornando genuinamente o melhor modelo, não só o mais
"impressionante no papel".

Esse é o tipo de armadilha que aparece com frequência em datasets de negócio reais
(fraude, churn, atraso, inadimplência) — todos tipicamente desbalanceados — e vale
mais a documentação dessa decisão do que qualquer métrica isolada.

## Limitações conhecidas
- **Recall de 67%**: o modelo ainda deixa passar ~1 em cada 3 atrasos reais sem sinalizar.
  Isso é aceitável para triagem/priorização manual, mas não para decisão totalmente automática.
- **Precisão moderada (F1=0.29)**: parte dos pedidos sinalizados como "risco de atraso" não
  vai de fato atrasar — o custo de uma ação preventiva (ex: contato proativo) deve ser baixo
  o suficiente para compensar esses falsos positivos.
- **Sem dados externos**: o modelo não tem acesso a eventos externos (greves, feriados
  regionais, clima), que na prática afetam bastante prazo de entrega.
- **Viés geográfico esperado**: regiões com menor volume de pedidos (Norte/Nordeste) tendem
  a ter menos dados de treino por estado, o que pode reduzir a confiabilidade da previsão
  nessas regiões — vale monitorar performance segmentada por `customer_state`.
- **Dataset histórico (2016-2018)**: mudanças logísticas recentes não são capturadas;
  requer retreino periódico com dados mais recentes se usado em produção real.

## Uso recomendado
Priorização de pedidos para acompanhamento manual da equipe de logística (ex: contato
proativo com o cliente, troca de transportadora). **Não recomendado** como única base
para decisões automáticas que afetem o cliente sem revisão humana.

## Monitoramento
Ver `ml/monitoring/drift_report.py` — compara a distribuição das features em produção
contra os dados de referência do treino, usando a biblioteca Evidently.
