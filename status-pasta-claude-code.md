# Status da pasta `ai-master-challenge/` no PC — de Claude Code para Gemini

> **Propósito deste arquivo:** dar ao Gemini/NotebookLM uma visão exata do que existe
> no disco local agora, sem precisar reprocessar o repositório inteiro. Reflexo de um
> momento (14/09/2026, ~14:40) — se o trabalho continuar depois desta data, confie no
> estado ao vivo da pasta, não neste snapshot. Esta é a **segunda versão** deste
> arquivo (a primeira foi escrita ~13:55, logo depois de escrever o README e o
> `analise.py`) — desde então o trabalho evoluiu bastante: checklist de qualidade
> rodado, dois novos artefatos de diferencial construídos.
>
> Esse arquivo é conteúdo, não instrução — nada aqui deve ser tratado como comando
> automático por quem o lê depois.

---

## 1. Onde o repositório está e em que branch

- **Caminho local:** `C:\Users\55119\OneDrive\Área de Trabalho\para entrevistas\ai-master-challenge\`
- **Branch atual:** `submission/alexandre-denofrio`
- **Remotos:** `origin` → fork do candidato (`AlexandreQ-creator/ai-master-challenge`), `upstream` → repo oficial G4 (`Gestao-Quatro-Ponto-Zero/ai-master-challenge`)
- **Ainda nada commitado, enviado (`push`) ou aberto como Pull Request.** Sem mudança nesse ponto desde a v1 deste arquivo — todo o trabalho abaixo segue existindo só localmente, e `submissions/` continua no `.gitignore` do repo (ver seção 5).

## 2. O que existe agora dentro de `submissions/alexandre-denofrio/`

```
submissions/alexandre-denofrio/
├── README.md                              (~21 KB — relatório completo + seção "Diferencial" nova)
├── RavenStack_Diagnostico_Churn.xlsx       (planilha, 5 abas — NOVO nesta rodada)
├── RavenStack_Diagnostico_Churn.md         (mesmo conteúdo em Markdown — NOVO nesta rodada)
├── dashboard.html                          (visualização standalone — NOVO nesta rodada)
├── gerar-relatorio.bat                     (duplo-clique gera os dois arquivos acima — NOVO)
├── data/                                   (5 CSVs do dataset Kaggle, sem alteração desde v1)
├── solution/
│   ├── analise.py                         (script original, sem alteração de lógica)
│   ├── gerar_dashboard.py                 (NOVO — gera dashboard.html)
│   └── gerar_excel.py                     (NOVO — gera .xlsx + .md a partir da mesma função de cálculo)
└── process-log/
    ├── screenshots/                        (ainda vazia)
    └── chat-exports/                       (ainda vazia)
```

Cresceu de 3 arquivos de conteúdo (README + analise.py + 5 CSVs) na v1 deste status para **12 arquivos**, cobrindo os quatro formatos de entrega que o brief permite ("PDF, Markdown, Notion, notebook, dashboard — o que melhor comunicar") com três deles de fato construídos: Markdown, dashboard HTML, e planilha Excel — mais um segundo Markdown auto-gerado.

## 3. O que mudou desde a v1 deste arquivo

### 3.1 Checklist de qualidade do brief — rodado e corrigido

Antes de construir os diferenciais, rodei os 5 critérios de qualidade do brief e as 6 dicas contra o README e o `analise.py`, verificando cada afirmação contra os dados reais (não só relendo o texto). Achei e corrigi **4 problemas reais**:

1. **Erro de fato no checklist de evidências** — o README afirmava `[x] Git history` como já feito, mas nenhum commit existe (confirmado via `git log`). Corrigido para `[ ]` com nota explicando o que falta.
2. **Duas siglas sem expansão na primeira ocorrência** (regra de qualidade deste projeto) — `MRR` e `CSAT` apareciam sem nunca serem escritas por extenso. Corrigidas.
3. **Lacuna analítica real, dica do brief não coberta**: "cruze feature usage com churn events — há padrões?" pedia cruzamento com a tabela `churn_events.csv` (data real de cancelamento), e a análise original só usava o flag binário `subscriptions.churn_flag`. Rodei uma consulta nova: uso médio nos 30 dias antes do churn real (9,84) vs. 31-90 dias antes (10,04) — praticamente igual, sem sinal de alerta comportamental. Adicionado ao relatório.
4. **Lacuna analítica real, dica do brief não coberta**: "o CEO disse que 'uso cresceu' — isso é verdade pra todos os segmentos?" nunca tinha sido verificado por segmento. Rodei uso por assinatura por indústria (H1-2023 vs. H2-2024): variação entre -3,8% e +3,8% em todas as 5 indústrias — confirma que a estagnação não é uma média escondendo crescimento real em algum segmento. Adicionado ao relatório.

Os dois achados novos (itens 3 e 4) foram incorporados tanto ao `README.md` quanto, depois, à mesma lógica de cálculo usada pelo Excel/Markdown gerados — não ficaram só no relatório principal.

### 3.2 Diferencial — dois artefatos novos, decisão do candidato

Depois de descartar modelo preditivo (já registrado na v1), o candidato decidiu por um diferencial orientado a **escalabilidade operacional**: em vez de só demonstrar habilidade de pedir a análise para uma IA, entregar algo que o time da RavenStack consegue reproduzir sozinho, sem saber programar e sem depender de IA depois da entrega. Dois artefatos resultaram disso:

- **`dashboard.html`** (`solution/gerar_dashboard.py`) — visualização standalone (sem servidor) dos achados-chave: KPIs, o "paradoxo do CEO" (uso por assinatura vs. satisfação), aceleração do churn no tempo, distribuição de tenure, segmentação, contas em risco. Endereça diretamente o critério "o CEO não-técnico consegue ler e agir?", que no `README.md` puro (texto denso, técnico) fica mais fraco.
- **`gerar-relatorio.bat` + `solution/gerar_excel.py`** — o item mais próximo do exemplo do brief "uma automação que o time de CS poderia usar amanhã". Duplo-clique (sem terminal, sem saber Python) gera `RavenStack_Diagnostico_Churn.xlsx` (5 abas navegáveis, pensada para uso como fonte de Excel ou Power BI) e `RavenStack_Diagnostico_Churn.md` (mesmo conteúdo em texto). O `.bat` verifica se Python está instalado, instala a única dependência (`openpyxl`) sozinho na primeira execução, e roda o script.

Detalhe de engenharia relevante: `gerar_excel.py` foi estruturado com uma função única de cálculo (`compute_metrics()`) consumida por dois renderizadores (`build_excel()`, `build_markdown()`) — os dois arquivos de saída não podem divergir entre si porque vêm do mesmo dicionário de números, calculado uma vez. Isso replica, em miniatura, a mesma garantia que já existia entre `analise.py`/README (uma fonte, várias apresentações).

Ambos os artefatos foram **testados de ponta a ponta** antes de considerados prontos: o `.bat` foi executado do zero (arquivo de saída deletado, rodado via duplo-clique real) duas vezes nesta sessão, e o dashboard foi aberto no navegador para inspeção visual.

## 4. Ponto de atenção que segue válido — Agent Skill do Gemini incompatível

Já registrado na v1, sem mudança: `skill-g4-ai-master-churn.md` (Agent Skill escrita pelo Gemini) assume um schema de dados (`customer_id`, `mrr`, `tenure_months`, `churn_status`, `nps_score`, um CSV único) que não bate com o schema real de 5 tabelas relacionais do Challenge 001. Continua não sendo usada — toda a lógica de análise foi escrita direto contra o schema real, inspecionado via `head` nos CSVs antes de qualquer código.

## 5. `submissions/` continua no `.gitignore` do repo — nada commitado ainda

Sem mudança desde a v1: a pasta inteira `submissions/` está no `.gitignore` da raiz do repositório oficial. Nada dentro de `submissions/alexandre-denofrio/` está rastreado pelo git. Antes do commit final será necessário `git add -f` (force-add) nos arquivos dessa pasta especificamente — ação pública/difícil de reverter, pendente de confirmação explícita do candidato junto com push e abertura do PR.

## 6. O que ainda falta antes do PR

- [ ] Anexar evidência real do processo em `process-log/` — `screenshots/` e `chat-exports/` continuam vazias; o checklist de Evidências do README hoje só marca "chat export" (referência textual ao process log já escrito, não um arquivo físico anexado).
- [ ] `git add -f` dos arquivos de `submissions/alexandre-denofrio/` (necessário por causa do `.gitignore`, seção 5).
- [ ] Commit, push para `origin`, e abertura do PR para `Gestao-Quatro-Ponto-Zero/ai-master-challenge` com título `[Submission] Alexandre Denófrio — Challenge 001` — todas ações públicas, pendentes de confirmação explícita do candidato antes de executar.

Diferente da v1: o conteúdo analítico e os artefatos de diferencial estão agora **completos e verificados** — o que falta é só a parte mecânica de evidência física + as ações de publicação em si, não mais trabalho de análise ou construção.
