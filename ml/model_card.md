# Model Card — Previsão de Atraso na Entrega

> Antes de ler este documento, veja `analytics/eda.ipynb` — a análise exploratória
> formal que embasa as decisões de feature engineering e modelagem descritas aqui.

## Tarefa
Classificação binária: o pedido vai ser entregue depois da data estimada (`is_delayed = 1`)
ou não (`is_delayed = 0`)?

## Dados de treino
- Fonte: `marts.fct_delivery_performance` (gerado pelo dbt a partir do dataset **real** Olist,
  baixado do Kaggle)
- Apenas pedidos com status `delivered` e data de entrega preenchida (95.137 pedidos)
- **Taxa real de atraso: 8,1%** — dataset bastante desbalanceado, o que exigiu tratamento
  específico (ver seção de achados abaixo)

## Metodologia

**Amostragem**: usamos o dataset completo (95.137 pedidos entregues), sem sub-amostragem —
o volume total já é pequeno o suficiente pra caber em memória e treinar em segundos, então
não há ganho em amostrar. A única amostragem no projeto é para fins de exploração/portfólio:
`analytics/sample_fct_delivery_performance.csv` é uma amostra estratificada (mantendo a
proporção real de atraso), usada pelo `analytics/eda.ipynb` para que qualquer pessoa
consiga rodar a análise exploratória sem precisar subir o banco Postgres.

**Split treino/teste**: 80/20, estratificado pela variável-alvo (`stratify=y` no
`train_test_split`), com `random_state=42` fixo — o mesmo seed é reutilizado em
`ml/monitoring/fairness_check.py` para reconstruir exatamente o mesmo conjunto de teste
sem precisar salvá-lo em disco.

**Validação cruzada**: além do split único treino/teste, rodamos 5-fold
`StratifiedKFold` (`random_state=42`) sobre o conjunto de treino, medindo AUC em cada
fold — isso confirma que a métrica de avaliação não depende de um split
particularmente "sortudo". Resultado (dataset real, 95.137 pedidos):

| Modelo | AUC (teste único) | AUC (média 5-fold CV) | Desvio padrão |
|---|---|---|---|
| Regressão Logística (baseline) | 0.691 | 0.695 | ± 0.006 |
| **Gradient Boosting (escolhido)** | **0.772** | **0.775** | **± 0.004** |

A AUC do teste único e da validação cruzada ficam muito próximas, com desvio padrão
baixo entre os folds — sinal de que o modelo generaliza de forma estável, não é um
resultado de sorte de um split específico.

> A validação cruzada **não roda automaticamente** durante o deploy (build do Docker no
> Render) para não dobrar o tempo de cada deploy — ela é ativada manualmente com
> `RUN_CROSS_VALIDATION=true python ml/train.py` quando for atualizar os números
> desta seção.

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

**Por que não usamos `delay_days` ou `total_delivery_days` como features**: ambas só
existem depois que o pedido já foi entregue — usá-las seria vazamento de dados (data
leakage), já que o objetivo é prever o risco **no momento da compra**. Esse ponto está
documentado com mais detalhe (e visualizado via matriz de correlação) em
`analytics/eda.ipynb`, seção 7.

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

## Fairness / robustez entre estados

Rodamos `ml/monitoring/fairness_check.py`, que reconstrói o mesmo conjunto de teste
usado na avaliação principal e mede recall/precisão segmentados por `customer_state`
(apenas estados com 30+ pedidos no teste, para evitar ruído de amostras pequenas).

**Achado real (não é só uma hipótese qualitativa — foi medido de verdade)**:
- O recall varia bastante entre estados: de **0% no Amazonas** (AM, apenas 40 pedidos
  no teste) e **20% na Paraíba** (PB, 94 pedidos) até **100% em Alagoas e Tocantins**
  (amostras pequenas também, então esse "100%" deve ser visto com cautela)
- **Contra-intuitivo**: São Paulo (SP) — o estado com *mais* dados de treino (8.071
  pedidos no teste) — teve recall de apenas **47,3%**, abaixo da média geral (67%).
  Isso mostra que volume de dados por si só não garante boa performance: o padrão de
  atraso em SP parece ser mais heterogêneo/difícil de prever que em estados com menos
  dados, mas mais consistentes
- 2 estados (AM, PB) ficaram abaixo de 70% do recall global e foram sinalizados
  automaticamente pelo script

**Interpretação**: isso não invalida o modelo, mas é essencial documentar antes de
qualquer uso automatizado — a confiabilidade da previsão **não é uniforme entre
regiões**, e decisões de negócio que dependam desse modelo em estados com poucos dados
(AM, PB, e outros com amostra pequena) devem ter revisão humana extra.

## Limitações conhecidas
- **Recall de 67%**: o modelo ainda deixa passar ~1 em cada 3 atrasos reais sem sinalizar.
  Isso é aceitável para triagem/priorização manual, mas não para decisão totalmente automática.
- **Precisão moderada (F1=0.29)**: parte dos pedidos sinalizados como "risco de atraso" não
  vai de fato atrasar — o custo de uma ação preventiva (ex: contato proativo) deve ser baixo
  o suficiente para compensar esses falsos positivos.
- **Sem dados externos**: o modelo não tem acesso a eventos externos (greves, feriados
  regionais, clima), que na prática afetam bastante prazo de entrega.
- **Viés geográfico confirmado (não só esperado)**: ver seção "Fairness / robustez
  entre estados" acima — performance varia de forma real e mensurável entre estados,
  sem relação direta com volume de dados.
- **Dataset histórico (2016-2018)**: mudanças logísticas recentes não são capturadas;
  requer retreino periódico com dados mais recentes se usado em produção real.

## Uso recomendado
Priorização de pedidos para acompanhamento manual da equipe de logística (ex: contato
proativo com o cliente, troca de transportadora). **Não recomendado** como única base
para decisões automáticas que afetem o cliente sem revisão humana — especialmente em
estados sinalizados pela checagem de fairness.

## Monitoramento
- `ml/monitoring/drift_report.py` — compara a distribuição das features em produção
  contra os dados de referência do treino, usando a biblioteca Evidently
- `ml/monitoring/fairness_check.py` — verifica recall/precisão por estado a cada
  retreino, sinalizando automaticamente grupos com performance desproporcionalmente
  baixa
