# 📦 Olist Intelligence Platform

Pipeline de dados end-to-end + modelo de Machine Learning em produção para prever
risco de atraso na entrega e medir seu impacto na satisfação do cliente, usando
dados no formato do dataset real de e-commerce brasileiro **Olist** (2016-2018).

Projeto construído para demonstrar, de ponta a ponta, o que separa um analista/cientista
de dados júnior de um pleno: não é só "treinar um modelo com boa acurácia", é saber
transformar dado bruto em pipeline confiável, modelo em produção monitorado, e insight
de negócio acionável.

---

## 🏗️ Arquitetura

```
Dados brutos (CSV)
      │
      ▼
Postgres (raw layer)
      │
      ▼
dbt: staging → intermediate → marts   ◄── testes de qualidade de dado em cada camada
      │
      ├──────────────┬───────────────────┐
      ▼              ▼                   ▼
Streamlit        Modelo ML            SQL avançado
Dashboard        (FastAPI + Docker)   (window functions,
(KPIs de         servido via API,     cohort analysis)
negócio)         com MLflow tracking
                 e monitoramento
                 de drift (Evidently)

Orquestrado por: Prefect (ingestão → dbt run/test → re-treino do modelo)
CI/CD: GitHub Actions (lint, testes, dbt test, build da imagem Docker)
```

## 🛠️ Stack

Postgres · dbt · Prefect · scikit-learn · MLflow · Evidently · FastAPI · Docker · Streamlit · GitHub Actions

## 📊 O problema de negócio

**Pedidos atrasados derrubam a nota de satisfação do cliente. Dá pra prever o risco de
atraso ainda no momento da compra, e agir antes que isso vire uma nota ruim?**

A análise em `analytics/sql/03_delivery_delay_impact_on_review.sql` (e o gráfico
equivalente no dashboard) confirma a hipótese: pedidos com atraso grave têm nota média
de review consideravelmente pior que pedidos no prazo. Isso justifica o investimento
em um modelo preditivo que sinalize esse risco cedo o suficiente para ação da equipe
de logística.

## ⚠️ Sobre os dados

O pipeline foi **validado de ponta a ponta com o dataset real da Olist** (baixado do
Kaggle) — ingestão, transformações dbt, queries analíticas e treino do modelo, todos
testados com os 99.441 pedidos reais. Os achados na seção abaixo vêm desse dataset real.

Os CSVs reais **não são versionados no Git** (`data/raw/*.csv` está no `.gitignore`) —
isso é proposital: repositórios de portfólio não devem carregar dezenas de MB de dados
brutos. Duas formas de obter os dados:

1. **Dados reais** (recomendado): baixe em
   [kaggle.com/datasets/olistbr/brazilian-ecommerce](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce)
   e coloque os CSVs em `data/raw/` (nomes de arquivo já compatíveis)
2. **Dados sintéticos** (fallback rápido, sem precisar de conta no Kaggle): rode
   `python data_generator/generate_synthetic_data.py --n-orders 50000` — útil só pra
   testar se o pipeline roda, os números não batem com os achados reais documentados aqui

> O dataset real também inclui `olist_geolocation_dataset.csv` e
> `product_category_name_translation.csv`, que este projeto não usa atualmente
> (poderiam alimentar um mapa de calor de entregas ou nomes de categoria em inglês —
> boas extensões futuras, mas fora do escopo inicial).

## 🚀 Como rodar localmente

### 1. Suba a infraestrutura
```bash
cp .env.example .env
docker-compose up -d postgres mlflow
```

### 2. Instale as dependências
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

### 3. Gere os dados e carregue no Postgres
```bash
python data_generator/generate_synthetic_data.py --n-orders 50000
python ingestion/load_raw_to_postgres.py
```

### 4. Rode as transformações dbt
```bash
export DBT_PROFILES_DIR=transformation
cp transformation/profiles.yml.example transformation/profiles.yml
dbt run --project-dir transformation
dbt test --project-dir transformation
```

### 5. Treine o modelo
```bash
python ml/train.py
```

### 6. Suba a API e o dashboard
```bash
# Localmente, sem Docker:
uvicorn api.main:app --reload --port 8000 &
streamlit run dashboard/app.py

# Ou tudo via Docker:
docker-compose up -d --build
```

Acesse:
- Dashboard: http://localhost:8501
- API (Swagger): http://localhost:8000/docs
- MLflow: http://localhost:5000

### 7. (Opcional) Rode o pipeline completo orquestrado
```bash
python ingestion/prefect_flow.py
```

## ✅ Rodando os testes
```bash
pytest tests/ api/tests/ -v
ruff check .
```

## ☁️ Deploy em produção

O repositório já vem com configuração pronta pra três serviços gratuitos. Escolha
**uma** opção de API (Railway ou Render) — não precisa das duas.

### Banco de dados em produção
O dashboard e a API não usam o Postgres local do `docker-compose` quando em produção.
Use um Postgres gerenciado gratuito: [Railway](https://railway.app) (tem um add-on de
Postgres), [Neon](https://neon.tech) ou [Supabase](https://supabase.com). Depois de
criar, rode a ingestão + `dbt run` apontando pra esse banco (mesmas variáveis de
ambiente, só trocando `POSTGRES_HOST` etc).

### Opção A — API no Railway
1. Crie um projeto em [railway.app](https://railway.app) e conecte este repositório
2. O Railway detecta o `railway.json` automaticamente e builda via `api/Dockerfile`
3. Configure a variável `MODEL_PATH` se necessário (já vem com default)
4. Pra deploy automático a cada push: gere um token em *Account Settings -> Tokens* e
   salve como secret `RAILWAY_TOKEN` no GitHub (Settings -> Secrets and variables ->
   Actions). O workflow `.github/workflows/deploy.yml` cuida do resto.

### Opção B — API + Dashboard no Render
1. Conecte o repositório em [render.com](https://render.com) -> New -> Blueprint
2. O Render lê o `render.yaml` e cria os dois serviços + um Postgres automaticamente
3. Preencha as variáveis marcadas `sync: false` no painel do Render após o primeiro deploy

### Dashboard no Streamlit Community Cloud
1. Em [share.streamlit.io](https://share.streamlit.io), aponte para `dashboard/app.py`
   como *main file path*
2. O Streamlit Cloud detecta `dashboard/requirements.txt` automaticamente
3. Em *App settings -> Secrets*, cole o conteúdo de `.streamlit/secrets.toml.example`
   preenchido com as credenciais reais do seu Postgres e a URL da API já deployada
4. **Nunca** commite `.streamlit/secrets.toml` com credenciais reais — ele já está no
   `.gitignore`



- Taxa geral de atraso: ~15-20% dos pedidos entregues
- Pedidos com atraso grave (>7 dias) têm nota média de review sensivelmente menor
  que pedidos no prazo
- Estados mais distantes dos polos de vendedores (Norte/Nordeste) concentram as
  maiores taxas de atraso — ver `analytics/sql/03_delivery_delay_impact_on_review.sql`
  e a aba de mapa por estado no dashboard

## 📈 Principais achados (dataset real do Kaggle, 99.441 pedidos)

- **Taxa geral de atraso: 8,1%** dos pedidos entregues chegam depois da data estimada
- **O atraso derruba a nota de forma muito clara**: nota média de review cai de **4,30**
  (entregue adiantado) para **1,73** (atraso grave, >7 dias) — uma queda de quase 3 pontos
- **78% dos pedidos com atraso grave recebem nota 1 ou 2** (vs. apenas 9% quando o
  pedido chega adiantado) — ver `analytics/sql/03_delivery_delay_impact_on_review.sql`
- **Alagoas (AL), Maranhão (MA) e Piauí (PI)** têm as maiores taxas de atraso do país
  (16-24%, contra 8,1% da média nacional) — sinal geográfico forte que o modelo já
  usa como feature (`customer_state`)
- O modelo (Gradient Boosting) detecta **67% dos atrasos reais** (recall), com AUC de
  0,77 — ver `ml/model_card.md` para a discussão completa, incluindo um achado
  importante sobre por que a seleção do modelo não pode se basear só em AUC quando
  a classe é desbalanceada (só 8% dos casos são positivos)

## 📁 Estrutura do repositório

```
├── .streamlit/          # tema e exemplo de secrets do Streamlit Cloud
├── data_generator/      # gera dados sintéticos no schema Olist
├── ingestion/           # carrega CSVs no Postgres + flow do Prefect
├── transformation/      # projeto dbt (staging → intermediate → marts)
├── analytics/sql/       # queries SQL avançadas (window functions, cohort)
├── ml/                  # treino do modelo, model card, monitoramento de drift
├── api/                 # FastAPI servindo o modelo
├── dashboard/           # Streamlit com KPIs de negócio e simulador
├── tests/               # testes de ingestão
├── railway.json         # config de deploy da API no Railway
├── render.yaml          # config de deploy alternativa (API + dashboard) no Render
└── .github/workflows/   # CI (lint, testes, dbt test, build Docker) + deploy automático
```

## ⚠️ Limitações conhecidas

- Dados sintéticos por padrão (ver seção "Sobre os dados" acima)
- Modelo de ML é um baseline intencionalmente simples (regressão logística vs
  Gradient Boosting) — ver `ml/model_card.md` para a discussão completa de trade-offs
- Sem dados externos (clima, greves, feriados regionais) que afetam prazo de entrega
  na vida real

## 📄 Licença

MIT — veja [LICENSE](LICENSE)
