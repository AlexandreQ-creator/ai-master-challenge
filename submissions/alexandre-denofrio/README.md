# Submissão — Alexandre Denófrio — Challenge 001 (Diagnóstico de Churn)

## Sobre mim

- **Nome:** Alexandre Wilson Faria Denófrio
- **LinkedIn:** [linkedin.com/in/alexandrewilsondenofrio](https://www.linkedin.com/in/alexandrewilsondenofrio)
- **Challenge escolhido:** 001 — Diagnóstico de Churn (RavenStack)

---

## Executive Summary

O churn da RavenStack não é um problema de uso nem de satisfação — os dois times (CS e Produto) estão olhando para métricas que, cruzadas com as outras quatro tabelas, não se sustentam como indicadores confiáveis: o "uso cresceu" é verdade só em volume agregado (mais contas = mais uso total), mas o uso **por assinatura** está estagnado desde janeiro de 2023, e a nota de satisfação só existe para 58,8% dos tickets, com taxa de resposta oscilando entre 41% e 88% mês a mês — não dá para confiar nela como termômetro. O sinal real está em outro lugar: **67,9% das contas que cancelam o fazem nos primeiros 90 dias de assinatura**, o volume de eventos de churn mais que decuplicou entre janeiro/2023 (1 evento) e dezembro/2024 (117 eventos) num ritmo muito mais rápido que o crescimento da base de contas, e o risco está fortemente concentrado em um cruzamento específico de segmento — contas de **DevTools adquiridas via `event`/`ads`** cancelam a 38-43%, contra 5-10% em Cybersecurity/EdTech adquiridas via `partner`/`organic`. A recomendação central é redirecionar o diagnóstico de "por que quem já é cliente está insatisfeito" para "por que estamos trazendo clientes que não se encaixam e os perdendo antes dos 90 dias" — um problema de onboarding e qualificação de aquisição, não de produto ou suporte.

Além do relatório, a entrega inclui dois artefatos pensados para uso recorrente pelo time da RavenStack **sem depender de mim nem de IA depois da entrega** — ver seção "Diferencial" abaixo: um dashboard visual (`dashboard.html`) e um extrator automático para Excel (`gerar-relatorio.bat`).

---

## Solução

### Abordagem

Antes de abrir qualquer ferramenta de IA, li o brief do challenge duas vezes e separei o que o CEO está afirmando em três alegações verificáveis, porque a pergunta dele já contém a pista: *"os números mostram que o churn subiu, mas CS diz que satisfação está ok, produto diz que uso cresceu — algo não bate."* Isso é literalmente um convite para achar onde a média mente. Um relatório que aceitasse "satisfação ok" e "uso cresceu" pelo valor de face, e fosse procurar a causa do churn em outro lugar, teria perdido o ponto do desafio.

Decompus o trabalho em três fases:

1. **Carga e integridade dos dados** — escrevi um script Python (`solution/analise.py`) que carrega as 5 tabelas, faz os cruzamentos por `account_id`/`subscription_id`, e imprime métricas cruas, sem interpretação. Isso é trabalho mecânico e determinístico (juntar tabelas, calcular médias, agrupar por segmento), então não faz sentido gastar raciocínio de IA nisso — um script comum resolve mais rápido e sem risco de erro de cálculo.
2. **Teste das duas alegações do CEO** — usei os números do script para checar especificamente "uso cresceu" (agregado vs. por assinatura) e "satisfação está ok" (cobertura da nota, taxa de resposta por mês, comparação churned vs. ativas) antes de olhar qualquer outra coisa.
3. **Causa raiz e segmentação** — com as duas alegações desmontadas, procurei o que de fato diverge entre quem cancela e quem fica: tenure até o churn, aceleração no tempo, e segmentação cruzada (indústria × canal de aquisição, não cada um isolado).

### Resultados / Findings

Todos os números abaixo saem de `solution/analise.py`, rodado sobre os 5 CSVs em `solution/data/` (dataset Kaggle "SaaS Subscription & Churn Analytics", licença MIT). Nenhum número foi digitado de memória.

**1. "Uso cresceu" é verdade em volume total, falso por assinatura — e não cai antes do churn.**
Uso total mensal (soma de `usage_count`) fica estável entre ~9.500 e ~11.400 ao longo de 24 meses — mas o número de assinaturas ativas também cresce nesse período (de ~870 para ~970+), então o uso **por assinatura** está achatado em ~11,0-11,3 unidades/mês desde janeiro de 2023, sem tendência de alta. O time de produto está lendo crescimento em uma métrica agregada que, na verdade, só reflete a base de contas crescendo — não engajamento crescente por cliente. Cruzando `feature_usage` diretamente com a data real de cada evento em `churn_events.csv` (não só o flag binário de `subscriptions`): o uso médio por evento nos 30 dias imediatamente antes do cancelamento (9,84) é praticamente igual ao uso no período de 31-90 dias antes (10,04) — não há um "sinal de alerta" de queda de uso pouco antes de cancelar. Se houvesse, seria um gatilho operacional óbvio para CS agir; como não há, reforça que a causa não está no comportamento de uso em si. A estagnação também não é um efeito de um segmento específico escondendo crescimento em outro: comparando uso por assinatura do primeiro semestre de 2023 contra o segundo semestre de 2024, todas as 5 indústrias oscilam entre -3,8% e +3,8% — dentro de ruído, sem nenhuma com crescimento real. "Uso cresceu" não é verdade para nenhum segmento, não só para a média.

**2. "Satisfação está ok" não é um dado confiável — é um dado ausente na maior parte do tempo.**
Apenas 1.175 de 2.000 tickets (58,8%) têm `satisfaction_score` preenchido, e a taxa de resposta oscila violentamente mês a mês (de 41% a 88% para contas que depois cancelaram). Mesmo assim, a nota média entre quem cancelou (4,01) é estatisticamente indistinguível da nota entre quem ficou (3,97) — ou seja: mesmo com o viés de não-resposta, satisfação simplesmente não discrimina quem vai cancelar. CS está certo ao dizer "a nota está ok", mas errado ao inferir daí que o cliente está seguro — a nota não é preditiva de nada aqui.

**3. O verdadeiro sinal: contas cancelam cedo, e o ritmo de cancelamento está acelerando.**
67,9% das assinaturas que cancelam o fazem em menos de 90 dias de vida (tenure mediano até o churn: 42 dias). Isso não é rotatividade natural de uma base madura — é falha de encaixe logo na entrada. Ao mesmo tempo, o volume mensal de eventos de churn sobe de 1 (jan/2023) para 117 (dez/2024), um crescimento muito mais acentuado que o crescimento da base de contas (que sobe de forma quase linear, ~20-30 contas novas/mês o tempo todo). O churn não está só acontecendo — está acelerando desproporcionalmente à base.

**4. O segmento de risco real é um cruzamento, não uma dimensão isolada.**
Olhando plano, indústria, canal e trial isoladamente, nenhum salta como "o" problema (todas as taxas de churn por plano ficam em ~22%, por exemplo — não é questão de tier). Mas cruzando indústria × canal de aquisição, aparece uma divergência real: **DevTools adquirida via `event` (43,5%) ou `ads` (38,5%)** cancela de 4 a 8 vezes mais que **Cybersecurity via `partner` (5,0%)** ou **EdTech via `ads` (0,0%, n=15)**. Contas de DevTools trazidas por canais pagos/eventos parecem ser um encaixe ruim de ICP (ideal customer profile) que a aquisição não está filtrando.

**5. O dinheiro em risco está concentrado, não distribuído.**
O MRR (receita recorrente mensal, *Monthly Recurring Revenue*) total em contas já canceladas soma US$ 255.442/mês (~US$ 3,07M/ano em ARR — receita recorrente anual — equivalente). Mas 62,1% desse valor vem de apenas 22 contas (top 20% das contas canceladas por MRR) — lideradas por Company_4 (Enterprise, US$ 21.691/mês) e outras 14 contas listadas em `solution/analise.py`, seção 6. Perder uma conta de US$ 50/mês e uma de US$ 21K/mês não são o mesmo evento, e o diagnóstico não deveria tratá-los como equivalentes.

**6. Pistas que pareciam promissoras e não se sustentaram (para não confundir correlação com causa):**
- Taxa de erro em features é levemente maior entre quem cancela (5,60% vs. 5,85% no agregado — na verdade *menor*; a diferença por feature individual no item 10 do script é de no máximo +2,1pp, ruído dentro do esperado para amostras desse tamanho).
- Tempo de primeira resposta e tempo de resolução de tickets são praticamente idênticos entre churned e ativos (84,8min vs. 89,5min; 35,7h vs. 35,9h) — suporte operacionalmente não é o vilão, apesar de "support" aparecer como `reason_code` em 17,3% dos eventos de churn (a causa declarada pelo cliente no formulário de cancelamento não é a mesma coisa que a causa operacional real).
- `reason_code` está distribuído quase uniformemente entre features/support/budget/unknown/competitor/pricing (15-19% cada) — não há uma "razão declarada" dominante, o que reforça que a causa raiz não é algo que o próprio cliente sabe nomear ao cancelar. É um problema estrutural de fit, não um evento pontual que o cliente consegue apontar.

### Recomendações

Priorizadas por impacto estimado e velocidade de implementação:

1. **Redesenhar o onboarding dos primeiros 90 dias, com checkpoint ativo nos dias 14/30/60.** Como 67,9% do churn acontece nessa janela, é onde a intervenção tem mais alavancagem. Impacto estimado: se reduzir o churn early-stage em 25%, isso preserva ~19 contas/trimestre no ritmo atual — a maior alavanca única disponível nos dados.
2. **Qualificar o ICP antes de comprar mídia para DevTools via `event`/`ads`.** Esses dois canais, para essa indústria especificamente, trazem contas que cancelam 4-8x mais que a média. Isso não significa cortar os canais — significa adicionar um filtro de qualificação (tamanho de empresa, stack, caso de uso) antes de fechar essas contas, ou ajustar o pitch/CS dedicado para esse segmento nos primeiros 90 dias.
3. **Criar um "cofre" de retenção branca-luva para as ~22 contas de maior MRR em risco.** Isso é 62% do valor perdido concentrado em um grupo pequeno e identificável (lista completa em `solution/analise.py`, seção 6) — dá para ter um plano de conta nomeado para cada uma, em vez de um programa genérico de retenção.
4. **Parar de usar `satisfaction_score` como sinal de risco isolado**, e em vez disso investir em aumentar a taxa de resposta do CSAT (*Customer Satisfaction Score*, a pesquisa de satisfação por ticket — hoje 58,8% de cobertura, com viés de não-resposta) — ou substituí-lo por um sinal comportamental mais confiável (ex.: uso por assinatura normalizado, que aqui mostrou mais sinal que a nota de satisfação).
5. **Investigar por que `reason_code` não converge em uma causa dominante.** A distribuição quase uniforme (15-19% cada) sugere que o formulário de cancelamento está capturando racionalizações pós-hoc do cliente, não a causa raiz real — vale revisar o texto do formulário/entrevista de saída à luz do achado de onboarding acima.

### Diferencial — pensado para escalar sem depender de IA ou de mim depois da entrega

O brief pede para "nos surpreender" com algo além do relatório — um dashboard, uma automação que o time pudesse usar amanhã, ou uma análise que muda a conversa. Decidi não ir pelo caminho de modelo preditivo (ver justificativa em Limitações) e ir por **escalabilidade operacional**: qualquer pessoa da RavenStack, mesmo sem saber programar ou usar IA, precisa conseguir reproduzir esta análise sozinha sempre que quiser — não só ler um relatório estático uma vez.

1. **`dashboard.html`** — visualização standalone dos achados-chave (KPIs, paradoxo do CEO, aceleração do churn, tenure, segmentação, contas em risco). Abre com duplo-clique em qualquer navegador, sem servidor, sem instalar nada. Pensado para o critério "o CEO (não-técnico) consegue ler e agir?" — é a camada visual que o Markdown puro não entrega.
2. **`gerar-relatorio.bat` + `solution/gerar_excel.py`** — o item mais alinhado ao espírito "automação que o time poderia usar amanhã": um arquivo que a pessoa da RavenStack clica duas vezes (sem terminal, sem saber Python) e recebe dois arquivos prontos, gerados do mesmo cálculo:
   - `RavenStack_Diagnostico_Churn.xlsx` — planilha navegável com 5 abas (Resumo Executivo, Teste das alegações do CEO, Contas em Risco por MRR, Segmentação de Risco, Dados Brutos para filtro/pivot próprio) — pensada para quem vai manipular os números no Excel ou plugar como fonte num Power BI.
   - `RavenStack_Diagnostico_Churn.md` — o mesmo conteúdo em Markdown, para quem prefere ler direto ou colar em Notion/Slack/e-mail sem abrir planilha.

   Único pré-requisito é ter Python instalado — o `.bat` verifica isso, instala a única dependência (`openpyxl`) sozinho na primeira vez, e gera os dois arquivos. A ideia por trás disso: a entrega não deveria ser "eu analisei uma vez e aqui está o PDF" — deveria ser algo que o time reroda sozinho quando os dados mudarem, sem precisar de outro ciclo de análise por IA.
3. **`solution/ia_consulta.py`** — uma IA de consulta em linguagem natural sobre o diagnóstico ("por que o churn está subindo?", "qual o MRR da Company_4?"), implementada como uma arquitetura de agentes especializados em vez de um prompt único (especificação completa em `solution/arquitetura-ia-consulta.md`): um Roteador que classifica a pergunta ou recusa o que está fora de escopo, um Agente de Grounding que é a única porta de entrada aos dados reais (`compute_metrics()`, a mesma fonte do Excel/dashboard), 6 subagentes especialistas por eixo (Causa Raiz, Segmentos, Contas Específicas, Recomendações, Metodologia, e Auditoria/Conformidade), um Agente de Resposta Executiva, e um **Auditor de Contexto Limpo** — que audita a resposta final sem ter participado da geração dela, para pegar o tipo de viés que uma auto-revisão não pega (ver próximo parágrafo). Roda em terminal, sem chave de API — roteamento determinístico, não LLM externo, para não depender de credencial que o avaliador talvez não tenha.
4. **`solution/harness_auditoria_submissao.py`** — fecha o loop: audita esta submissão inteira contra o brief **oficial** do desafio, lido direto do commit do repositório (não de memória), com 13 testes programáticos (os 5 critérios de qualidade + as 6 dicas do brief + 2 obrigatoriedades do submission-guide) e veredito condicionado ao resultado real. O resultado alimenta o novo subagente Auditoria/Conformidade da IA de consulta acima (`process-log/auditoria-final.json`, dados já extraídos, sem re-rodar o harness a cada pergunta).

O Auditor de Contexto Limpo não é um componente genérico de "boas práticas de IA" — nasce de um achado real deste mesmo projeto de carreira: uma auditoria anterior sobre o processo de redação de CV mediu um viés chamado **"mascaramento por justaposição"** (usar vocabulário adjacente que sugere domínio que a fonte não sustenta, sem afirmar nada literalmente falso) — e esse viés só é pego por um revisor que não participou da escrita, porque uma auto-revisão já "concorda" com o próprio raciocínio. O NotebookLM, auditando seu próprio método de forma independente, nomeou o mesmo risco — confirmação cruzada real entre dois métodos diferentes. A arquitetura aplica essa mesma disciplina à IA de consulta: o Auditor só recebe a resposta pronta e o dado bruto, nunca o histórico de geração.

Segurança da informação também foi tratada como parte do design, não como item avulso: ao revisar um material de terceiro (Agent Skill trazida via NotebookLM, com uma função de mascaramento de PII/LGPD), encontrei um bug real — a checagem de tipo que decidia se uma coluna devia ser mascarada nunca disparava na versão atual do pandas, então e-mail/CPF saíam em texto puro mesmo com o "guardrail" presente no código, e o próprio harness de teste reportava sucesso apesar do teste de vazamento estar falhando. Corrigi o bug e usei o caso como base da seção "Segurança da informação" em `arquitetura-ia-consulta.md`: nenhum agente tem acesso de escrita, toda guarda de mascaramento precisa de teste que falha de verdade (não checagem otimista), e recusa é o comportamento padrão quando não há certeza.

Os cinco scripts (`analise.py`, `gerar_dashboard.py`, `gerar_excel.py`, `ia_consulta.py`, `harness_auditoria_submissao.py`) reaproveitam a mesma lógica de carga e cruzamento das 5 tabelas — a IA de consulta, o Excel e o Markdown gerado automaticamente vêm todos da mesma função de cálculo (`compute_metrics()`), então nenhum dos formatos pode divergir dos outros. Os seis artefatos da entrega (relatório em Markdown, dashboard, planilha, `.md` gerado automaticamente, a IA de consulta, e o harness de auditoria) contam a mesma história a partir da mesma fonte.

### Limitações

- A análise usa `churn_flag` no nível de conta e de assinatura, que nem sempre coincidem 1:1 (500 contas, mas 600 eventos de churn e 175 contas com mais de um evento — há churn seguido de reativação e novo churn). Tratei "conta churned" como `accounts.churn_flag=True`, que é a visão mais estável para segmentação, mas uma conta com múltiplos ciclos de churn/reativação carrega mais complexidade do que esse relatório captura.
- Não tive acesso a um dicionário de dados oficial do dataset Kaggle além do que está documentado no README do challenge — os nomes de `feature_1`...`feature_40` são anônimos, então não consegui amarrar o achado de erro de feature (item 10 do script) a uma funcionalidade real do produto; o diferencial ali é fraco (+2,1pp no pior caso) e não recomendo agir sobre ele sem mais dados.
- A "aceleração" do volume de eventos de churn (seção 9) é year-over-year dentro do próprio dataset sintético — não tenho como confirmar se isso reflete sazonalidade real de SaaS B2B (ex. fim de ano fiscal) ou é um artefato da geração dos dados; sinalizo isso como hipótese a validar com o time de dados da RavenStack antes de comunicar "o churn está acelerando" ao board sem qualificação.
- Não construí um modelo preditivo (diferencial opcional do challenge) — com ~500 contas e uma causa raiz mais estrutural (onboarding/fit) do que comportamental, um classificador teria alto risco de overfitting e baixo valor incremental sobre a regra simples "monitorar os primeiros 90 dias por segmento de risco"; preferi aprofundar o diagnóstico causal a produzir um modelo de valor duvidoso só para ter "diferencial".

---

## Process Log — Como usei IA

### Ferramentas usadas

| Ferramenta | Para que usou |
|------------|--------------|
| Claude Code | Leitura dos 5 CSVs, escrita do script de análise (`solution/analise.py`), execução e interpretação dos resultados, verificação de hipóteses adicionais via scripts Python ad-hoc, redação deste relatório, escrita/teste dos artefatos de diferencial (`gerar_dashboard.py`, `gerar_excel.py`, `gerar-relatorio.bat`), e design + implementação da arquitetura de 5 agentes da IA de consulta (`arquitetura-ia-consulta.md`, `ia_consulta.py`) |

### Workflow

1. Li o README do challenge e o submission-guide.md duas vezes antes de tocar em qualquer dado, para separar o que precisa ser verificado (as duas alegações do CEO) do que é só contexto.
2. Pedi ao Claude Code para inspecionar o schema real das 5 tabelas (cabeçalho + contagem de linhas) antes de escrever qualquer lógica de análise — evitando presumir uma estrutura simplificada.
3. Pedi para o Claude Code escrever um script Python determinístico que carregasse e cruzasse as 5 tabelas, com uma seção numerada por pergunta que eu queria responder (visão geral, reason codes, teste das duas alegações do CEO, suporte, segmentação, valor em risco, upgrade/downgrade, tenure, série temporal, features). Optei por script em vez de pedir "a IA analise e me diga a causa" porque juntar tabelas e calcular médias é trabalho mecânico — quero que a IA gaste esforço na interpretação, não no cálculo.
4. Rodei o script e revisei a saída linha por linha comigo mesmo antes de aceitar qualquer número como fato — a saída bruta não vira insight sozinha.
5. A partir da saída, formulei hipóteses adicionais que o script original não cobria (crescimento da base de contas por mês, uso normalizado por assinatura ao longo do tempo, taxa de resposta do CSAT por mês, taxa de churn por coorte de cadastro, segmentação cruzada indústria×canal) e pedi consultas Python pontuais para cada uma — cada consulta testando uma hipótese específica, não uma exploração aberta.
6. Com os números validados, escrevi a narrativa do relatório eu mesmo, decidindo qual achado é a causa raiz (early churn + fit de aquisição) vs. o que é ruído (erro de feature, tempo de resposta de suporte) — essa é a parte que o script não faz sozinho.
7. Para o diferencial, direcionei explicitamente a IA para **não** ir pelo caminho óbvio (modelo preditivo, que já tínhamos descartado) — pedi um artefato que qualquer pessoa da RavenStack, sem saber programar ou usar IA, conseguisse rodar sozinha para reproduzir a extração sempre que quiser. Isso virou dois scripts que reaproveitam a mesma lógica de carga/cruzamento de `analise.py`: `solution/gerar_dashboard.py` (visualização HTML standalone) e `solution/gerar_excel.py` + `gerar-relatorio.bat` (planilha `.xlsx` com um clique). Testei os dois de ponta a ponta (rodei o `.bat` do zero, abri o `dashboard.html` no navegador) antes de considerar prontos.
8. Pedi uma segunda camada de diferencial: uma IA de consulta em linguagem natural sobre os dados já analisados. Antes de escrever qualquer código, pedi a especificação por escrito primeiro (`arquitetura-ia-consulta.md`) — decisão deliberada de não pular direto pra implementação, porque "agentes de IA" é fácil de virar buzzword sem estrutura real por trás. Fechei o escopo com perguntas específicas: a IA responde só sobre o que já foi analisado (não gera consulta nova on-the-fly, risco de alucinação em dado de negócio) e roda sem chave de API (roteamento determinístico, não LLM externo — decisão pra qualquer avaliador conseguir rodar sem configurar credencial).
9. Ao revisar um material de terceiro trazido para o projeto (uma Agent Skill de governança de dados, com função de mascaramento de PII/LGPD), testei o código de verdade em vez de confiar na leitura — e encontrei um bug real: o mascaramento nunca executava por causa de uma checagem de tipo que quebrou silenciosamente entre versões do pandas, e o próprio harness de teste reportava "sucesso" com o teste de vazamento de PII falhando. Corrigi o bug, revalidei com dado real de e-mail/CPF, e usei esse caso concreto (não uma boa prática genérica) como base da seção "Segurança da informação" da arquitetura de agentes.
10. Implementei os agentes (`ia_consulta.py`) e testei de verdade antes de considerar pronto: rodei uma suíte de 7 perguntas cobrindo os 5 domínios originais + 2 casos de recusa de escopo, testei o Auditor de Contexto Limpo isoladamente (3 casos: bloqueia linguagem de causa direta, aprova resposta bem formulada, isenta domínios de baixo risco), e testei casos de borda (conta inexistente, pergunta não classificável) — confirmando que a IA recusa/admite não saber em vez de inventar.
11. Pedi uma auditoria final do processo como um todo, aplicando a mesma arquitetura já construída (agentes/subagentes/harness) — mas agora guiada pelo brief **oficial** do desafio, lido direto do commit do GitHub, não de memória. Construí `harness_auditoria_submissao.py`: 13 testes programáticos, um por critério/dica do brief. Rodei e a primeira execução deu 12/13 — investiguei antes de aceitar o resultado, e descobri que era falso-positivo do próprio teste (procurava a string "H1-2023", o README usa "primeiro semestre de 2023" por extenso), não uma lacuna real da submissão. Corrigi o teste, não o conteúdo, e reconfirmei 13/13. Esse cuidado — não aceitar "falhou" nem "passou" sem investigar a causa — é a mesma disciplina já aplicada ao longo de toda a sessão para número e achado.
12. Conectei o resultado da auditoria à IA de consulta como um 6º subagente (Auditoria/Conformidade), que lê `process-log/auditoria-final.json` (dado já extraído) em vez de re-rodar o harness a cada pergunta — a mesma lógica de "calcular uma vez, consumir depois" que já vale para `compute_metrics()`.

### Onde a IA errou e como corrigi

A primeira leitura da saída do script (seção 1, visão geral) poderia ter sido interpretada erroneamente como "600 contas cancelaram", quando na verdade são 600 **eventos** de churn distribuídos em apenas 352 contas distintas (175 contas com mais de um evento — ciclos de churn→reativação→churn). Se eu tivesse aceitado a leitura ingênua, o relatório teria inflado o problema. Corrigi rodando uma contagem específica de `len(churn_by_account)` vs. `len(churn)` antes de escrever qualquer frase sobre "quantas contas cancelaram", e documentei essa distinção explicitamente na seção de Limitações.

Também descartei uma leitura inicial tentadora da série temporal de churn (seção 9 do script): à primeira vista, "117 eventos em dezembro/2024 contra 1 em janeiro/2023" parece um sinal alarmante isolado. Antes de usar esse número na narrativa, rodei uma consulta separada para checar o crescimento da base de contas no mesmo período — se a base também tivesse decuplicado, o aumento de eventos seria só proporcional, não um sinal real. Só depois de confirmar que a base cresce de forma quase linear (~20-30 contas/mês) enquanto os eventos de churn crescem de forma claramente não-linear é que tratei isso como achado real no relatório.

### O que eu adicionei que a IA sozinha não faria

O ponto de partida de toda a análise — tratar a fala do CEO ("satisfação ok" + "uso cresceu" + "churn subiu") como três alegações a testar, não como contexto a aceitar — foi uma escolha minha antes de qualquer prompt. Um uso ingênuo de IA teria pedido "analise esses 5 CSVs e me diga por que o churn está alto" e aceitado a primeira resposta plausível (provavelmente puxando para `reason_code` ou tempo de resposta de suporte, que são os dados mais óbvios de se olhar primeiro e que este relatório mostra explicitamente que **não** discriminam quem cancela).

A decisão de normalizar uso por assinatura (em vez de olhar só o total agregado) veio da minha experiência com dados de operação — uma métrica agregada crescendo enquanto o denominador também cresce é o erro clássico de "achar que o negócio está indo bem porque o número absoluto sobe", e é exatamente o tipo de armadilha que o brief avisa para não cair ("cuidado com conclusões apressadas"). Da mesma forma, decidir cruzar indústria × canal de aquisição (em vez de olhar cada dimensão isolada, que não mostra nada de interessante) veio de reconhecer que problemas de fit de produto raramente aparecem numa dimensão só — é um padrão que já vi em análise de causa raiz (RCA/5 Whys) aplicada a operações reais.

Por fim, a decisão de **não** construir um modelo preditivo, apesar de ser um diferencial sugerido no brief, foi julgamento deliberado: com uma causa raiz estrutural (onboarding e fit de aquisição, não comportamento individual imprevisível) e uma base de ~500 contas, um modelo teria mais chance de impressionar tecnicamente do que de ajudar a RavenStack a agir — e o critério de qualidade do challenge é explícito sobre isso ("as recomendações são acionáveis?"), não "tem modelo?".

No lugar do modelo, escolhi um diferencial orientado a **escalabilidade operacional**: em vez de só demonstrar que sei pedir a análise para uma IA, o objetivo foi entregar algo que continua gerando valor depois que eu não estiver mais envolvido — qualquer pessoa do time, mesmo sem saber programar, consegue reproduzir a extração e o diagnóstico sozinha (`gerar-relatorio.bat` → Excel) sempre que os dados mudarem, sem depender de um novo ciclo de análise por IA a cada atualização. Essa é a diferença entre "entregar um relatório" e "entregar uma capacidade" — e é o tipo de julgamento de produto/operação que não vem de pedir "faça um diferencial" para a IA, vem de entender para quem a entrega é.

---

## Evidências

- [x] Chat export — não só a narrativa do Process Log acima, mas 6 arquivos de saída real de execução em `process-log/chat-exports/` (índice explicando cada um em `process-log/chat-exports/README.md`): saída completa de `analise.py`, self-test da IA de consulta, teste unitário do Auditor de Contexto Limpo, o harness de segurança PII rodando 5/5 depois do fix, e o harness de auditoria final (13/13 contra o brief oficial do GitHub) + a IA de consulta respondendo sobre o próprio resultado dessa auditoria
- [ ] Screenshots das conversas com IA
- [ ] Screen recording do workflow
- [ ] Git history (branch `submission/alexandre-denofrio` criada; commit/push ainda pendentes — ver checklist final antes do PR)
- [ ] Outro: _____________

---

_Submissão enviada em: 2026-09-14_
