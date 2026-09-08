# Dashboard alternativo em Power BI

Este projeto já tem um dashboard ao vivo em Streamlit (veja o README principal), mas
o Power BI é a ferramenta de BI mais pedida no mercado brasileiro — então aqui vai o
guia completo pra conectar o Power BI Desktop direto nos mesmos marts do dbt, sem
duplicar nenhuma lógica de negócio.

## Por que conectar no mart, não no banco raw

O Power BI deve ler dos marts do dbt (schema `marts`), nunca das tabelas `raw`.
Isso garante que os números batem exatamente com os do dashboard Streamlit e com o
`model_card.md` — a lógica de atraso, joins e agregações já foi resolvida uma vez só,
no dbt, e todo o resto (Power BI incluso) só consome o resultado.

## Pré-requisitos

- Power BI Desktop instalado (gratuito): https://powerbi.microsoft.com/desktop/
- O banco Neon já criado e com `dbt run` executado (ver README principal)
- Windows (Power BI Desktop não roda em Mac/Linux nativamente — use uma VM se precisar)

## Passo a passo

### 1. Conectar no banco

1. Abra o Power BI Desktop
2. **Obter Dados** → **Mais...** → categoria **Banco de dados** → **Banco de dados PostgreSQL**
3. Na primeira vez, o Power BI vai pedir pra instalar o driver **Npgsql** — aceite e reinicie o Power BI se solicitado
4. Preencha:
   - **Servidor**: o host do seu Neon (ex: `ep-muddy-violet-ay8fgett-pooler.c-5.us-east-2.aws.neon.tech:5432`)
   - **Banco de dados**: `neondb`
5. Modo de conectividade de dados:
   - **Import** (recomendado): mais rápido de usar, precisa clicar em "Atualizar" pra pegar dados novos
   - **DirectQuery**: sempre atualizado, mas cada interação no relatório dispara uma query no Neon
6. Usuário: `neondb_owner` — Senha: a senha do seu banco Neon (veja no console do Neon, em Connect)

### 2. Selecionar as tabelas

No Navegador, dentro do schema **marts**, marque:
- `fct_delivery_performance` (fato principal — atraso, review, valor do pedido)
- `fct_seller_performance` (receita e volume por vendedor)
- `dim_customers`
- `dim_sellers`

Clique em **Transformar Dados** (não em Carregar direto) pra revisar tipos de coluna
no Power Query antes de importar.

### 3. Criar o relacionamento

No modo **Modelo** (ícone de tabelas conectadas na barra lateral esquerda):
- Relacione `fct_delivery_performance.customer_id` → `dim_customers.customer_id`
- Relacione `fct_seller_performance.seller_id` → `dim_sellers.seller_id`

### 4. Medidas DAX sugeridas

Crie estas medidas (botão direito na tabela `fct_delivery_performance` → Nova Medida):

```dax
Taxa de Atraso =
DIVIDE(
    SUM(fct_delivery_performance[is_delayed]),
    COUNTROWS(fct_delivery_performance)
)

Nota Média de Review =
AVERAGE(fct_delivery_performance[review_score])

Total de Pedidos =
COUNTROWS(fct_delivery_performance)

Impacto do Atraso na Nota =
CALCULATE([Nota Média de Review], fct_delivery_performance[is_delayed] = 0)
    - CALCULATE([Nota Média de Review], fct_delivery_performance[is_delayed] = 1)
```

### 5. Visuais sugeridos (replicando o dashboard Streamlit)

| Visual | Campos |
|---|---|
| Cartão | Total de Pedidos, Taxa de Atraso, Nota Média de Review |
| Gráfico de colunas | Eixo: `delay_bucket` — Valor: Nota Média de Review |
| Gráfico de colunas | Eixo: `customer_state` — Valor: Taxa de Atraso |
| Gráfico de barras | Eixo: `seller_name` (top 10 por receita) — de `fct_seller_performance` |
| Mapa (opcional) | `customer_state` com Taxa de Atraso — requer a tabela `olist_geolocation_dataset`, não usada por padrão neste projeto |

### 6. Filtros interativos (cross-filtering e slicers)

Diferente do dashboard Streamlit (que é estático — cada gráfico é independente), o
Power BI tem **cross-filtering nativo**: clicar numa barra de qualquer gráfico filtra
automaticamente todos os outros visuais da mesma página, sem escrever código.

Pra tornar isso ainda mais explícito pro usuário do relatório:

1. **Inserir → Segmentação de Dados** (slicer) pra `customer_state` — vira um filtro
   visível tipo lista ou dropdown que controla a página inteira
2. Adicione outro slicer pra `delay_bucket` ou `primary_product_category`
3. Teste clicando direto numa barra do gráfico de "Taxa de Atraso por Estado" — repare
   que o gráfico de "Nota Média por Situação da Entrega" se atualiza sozinho, mostrando
   só os pedidos daquele estado
4. Pra desfazer o filtro por clique, clique de novo na mesma barra (ou no botão de
   "Limpar seleção" no canto do visual)

Essa interatividade nativa é um dos motivos pra usar Power BI em vez de (ou além de)
Streamlit num contexto corporativo — quem consome o relatório explora os dados sozinho,
sem pedir uma nova versão pro analista toda vez que precisa cortar por outro recorte.

### 7. Publicar (opcional, gratuito com limitação)

- **Power BI Service** (conta gratuita): Publicar → escolha um workspace → o relatório
  fica visível só pra quem tem acesso à sua organização/conta
- **Publicar na Web** (Arquivo → Publicar → Publicar na Web): gera um link público,
  sem necessidade de login — mas **os dados ficam visíveis pra qualquer pessoa com o
  link**, então só use se estiver confortável com os dados sintéticos/de portfólio
  ficando públicos dessa forma

## Diferença esperada em relação ao Streamlit

Como o Power BI (modo Import) só atualiza quando você clica em "Atualizar" ou agenda
uma atualização, os números podem ficar defasados em relação ao Streamlit (que
consulta o Neon a cada carregamento, com cache de 10 minutos). Isso é normal e vale
mencionar em entrevista: é exatamente o trade-off entre *import* e *live query* que
todo analista de BI precisa saber explicar.
