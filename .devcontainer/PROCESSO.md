# Processo de Ciência de Dados deste Projeto

Este projeto não segue um framework único de forma rígida — na prática, poucos times
seguem. Mas as etapas percorridas mapeiam de forma consistente para os principais
frameworks da área, o que é uma boa forma de comunicar o processo em entrevistas.
Este documento existe pra deixar esse mapeamento explícito, em vez de implícito.

## Resumo

| Framework | Cobertura | Onde no repositório |
|---|---|---|
| **CRISP-DM** | Completo (6/6 fases) | Ver tabela abaixo |
| **CRISP-ML(Q)** | Completo, incluindo qualidade | CRISP-DM + testes dbt + monitoramento |
| **KDD** | Completo (é o que mais se encaixa naturalmente) | Ver tabela abaixo |
| **SEMMA** | Completo | Ver tabela abaixo |
| **TDSP** | Completo, exceto "Customer Acceptance" (não aplicável a projeto solo) | Ver tabela abaixo |

## CRISP-DM (Cross Industry Standard Process for Data Mining)

| Fase | Onde está | Evidência |
|---|---|---|
| 1. Entendimento do negócio | `README.md`, seção "O problema de negócio" | Pergunta de negócio explícita: atraso → nota de review |
| 2. Entendimento dos dados | `analytics/eda.ipynb` | Distribuições, valores ausentes, correlações, outliers |
| 3. Preparação dos dados | `transformation/models/` (dbt) | staging → intermediate → marts, com testes de qualidade |
| 4. Modelagem | `ml/train.py` | Comparação baseline vs. Gradient Boosting |
| 5. Avaliação | `ml/model_card.md` | AUC/F1/Recall, validação cruzada 5-fold, fairness por estado |
| 6. Implantação | `api/`, `dashboard/`, `.github/workflows/`, Render, Streamlit Cloud | API + dashboard em produção, CI/CD |

## CRISP-ML(Q) (estende o CRISP-DM com garantia de qualidade)

Cobre as 6 fases do CRISP-DM acima, **mais** as etapas de qualidade que ele adiciona:

| Adição do CRISP-ML(Q) | Onde está |
|---|---|
| Requisitos de qualidade de dados | `transformation/models/*/schema.yml` — testes `not_null`, `unique`, `relationships`, `accepted_values` em cada camada do dbt |
| Avaliação de robustez do modelo | `ml/monitoring/fairness_check.py` — recall/precisão segmentados por estado, com alerta automático |
| Monitoramento em produção | `ml/monitoring/drift_report.py` — comparação de distribuição via Evidently |
| Ciclo de retreino | `api/Dockerfile` treina o modelo a cada deploy, contra os dados mais recentes do Neon |

## KDD (Knowledge Discovery in Databases)

Esse é o framework que mais naturalmente bate com a estrutura de pastas do projeto:

| Etapa do KDD | Onde está |
|---|---|
| Selection | Escolha do dataset Olist + filtro `order_status = 'delivered'` (`stg_orders.sql`) |
| Preprocessing | `transformation/models/staging/` — limpeza e padronização de tipos |
| Transformation | `transformation/models/intermediate/` e `marts/` — cálculo de atraso, agregações |
| Data Mining | `ml/train.py` |
| Interpretation/Evaluation | Achados de negócio no `README.md` + `ml/model_card.md` |

## SEMMA (Sample, Explore, Modify, Model, Assess)

| Etapa | Onde está |
|---|---|
| Sample | `ml/model_card.md`, seção "Metodologia" — dataset completo (95k pedidos, pequeno o suficiente pra não precisar amostrar); amostra estratificada pequena só para `analytics/eda.ipynb` |
| Explore | `analytics/eda.ipynb` — distribuições, correlações, outliers |
| Modify | `transformation/` (dbt) + feature engineering em `ml/train.py` |
| Model | `ml/train.py` — baseline vs. Gradient Boosting |
| Assess | `ml/model_card.md` — métricas, validação cruzada, fairness check |

## TDSP (Team Data Science Process, Microsoft)

| Fase | Onde está |
|---|---|
| Entendimento do negócio | `README.md` |
| Aquisição e entendimento dos dados | `analytics/eda.ipynb` + `ingestion/` |
| Modelagem | `ml/train.py`, `ml/model_card.md` |
| Implantação | `api/`, `dashboard/`, CI/CD |
| Aceite do cliente | **Não aplicável** — projeto solo de portfólio, sem cliente real validando entregas |
| Infraestrutura/reprodutibilidade (ênfase forte do TDSP) | Git, Docker, `requirements.txt` com versões fixas, GitHub Actions |

## Por que isso importa pra entrevista

Ninguém espera que um candidato júnior/pleno siga um processo à risca — mas saber
**nomear** o que foi feito ("essa parte é a fase de Data Understanding do CRISP-DM",
"isso é uma checagem de fairness que o CRISP-ML(Q) formaliza e o CRISP-DM clássico
não cobre") demonstra que as decisões foram tomadas de forma consciente, não
aleatória. Esse documento existe pra deixar esse vocabulário à mão na hora da
conversa.
