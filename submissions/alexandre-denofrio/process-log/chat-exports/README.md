# Evidências de processo — saídas reais de execução

Estes 4 arquivos são saída literal (`stdout`/`stderr` capturados via redirecionamento
de shell, não reconstruídos de memória) de comandos rodados de verdade durante a
sessão de trabalho neste desafio. Cada um corresponde a uma etapa específica do
Process Log descrito em `README.md` (raiz desta submissão).

| Arquivo | O que é | Corresponde a |
|---|---|---|
| `01-saida-analise.py.txt` | Saída completa de `solution/analise.py` — os 10 blocos de métricas cruas (visão geral, reason codes, teste das alegações do CEO, suporte, segmentação, valor em risco, upgrade/downgrade, tenure, série temporal, features) que sustentam cada número citado no `README.md` | Workflow, passos 3-4 |
| `02-saida-ia-consulta-self-test.txt` | Saída de `python solution/ia_consulta.py --self-test` — as 7 perguntas de exemplo cobrindo os 5 domínios da IA de consulta + 2 casos de recusa de escopo, com a resposta completa de cada uma (incluindo citação de fonte e nota de auditoria quando aplicável) | Workflow, passo 10 |
| `03-saida-teste-auditor.txt` | Teste unitário isolado do 5º agente (Auditor de Contexto Limpo): confirma que ele bloqueia linguagem de causa direta, aprova resposta bem formulada, e isenta domínios de baixo risco da auditoria (economia de custo real) | Workflow, passo 10; arquitetura-ia-consulta.md, seção "Custo vs. benefício" |
| `04-saida-harness-seguranca-pii-apos-fix.txt` | Saída de `python harness-mestre-dados.py` (arquivo na raiz do repo, material trazido via NotebookLM) **depois** da correção do bug de mascaramento de PII — confirma 5/5 testes passando, incluindo o `TC-003` (segurança LGPD) que falhava antes do fix | Workflow, passo 9; "Onde a IA errou e como corrigi" |

## Por que estas evidências e não outras

O `submission-guide.md` do repositório aceita várias formas de evidência
(screenshots, screen recording, chat export, narrativa escrita, git history, notebook
comentado). Escolhi **saída de execução real** como forma principal porque é a mais
verificável objetivamente: qualquer avaliador pode rodar os mesmos comandos
(`python solution/analise.py`, `python solution/ia_consulta.py --self-test`,
`python harness-mestre-dados.py` na raiz do repo) e obter a mesma saída — não depende
de confiar numa narrativa escrita sobre o que "teria acontecido".

A narrativa completa de *como* cada decisão foi tomada (por que separar em 5 agentes,
por que recusar modelo preditivo, como o bug de PII foi encontrado) já está no
`README.md` desta submissão, seção "Process Log — Como usei IA" — estes arquivos são
o complemento factual que comprova que os passos descritos ali de fato aconteceram,
não uma reconstrução a posteriori.
