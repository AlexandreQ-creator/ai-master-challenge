# Evidências de processo — saídas reais de execução

Estes arquivos são saída literal (`stdout`/`stderr` capturados via redirecionamento
de shell, não reconstruídos de memória) de comandos rodados de verdade durante a
sessão de trabalho neste desafio. Cada um corresponde a uma etapa específica do
Process Log descrito em `README.md` (raiz desta submissão).

| Arquivo | O que é | Corresponde a |
|---|---|---|
| `01-saida-analise.py.txt` | Saída completa de `solution/analise.py` — os 10 blocos de métricas cruas (visão geral, reason codes, teste das alegações do CEO, suporte, segmentação, valor em risco, upgrade/downgrade, tenure, série temporal, features) que sustentam cada número citado no `README.md` | Workflow, passos 3-4 |
| `02-saida-ia-consulta-self-test.txt` | Saída de `python solution/ia_consulta.py --self-test` — as 7 perguntas de exemplo cobrindo os domínios da IA de consulta + 2 casos de recusa de escopo, com a resposta completa de cada uma (incluindo citação de fonte e nota de auditoria quando aplicável) | Workflow, passo 10 |
| `03-saida-teste-auditor.txt` | Teste unitário isolado do Auditor de Contexto Limpo (agente 5): confirma que ele bloqueia linguagem de causa direta, aprova resposta bem formulada, e isenta domínios de baixo risco da auditoria (economia de custo real) | Workflow, passo 10; arquitetura-ia-consulta.md, seção "Custo vs. benefício" |
| `04-saida-harness-seguranca-pii-apos-fix.txt` | Saída de `python harness-mestre-dados.py` (arquivo na raiz do repo, material trazido via NotebookLM) **depois** da correção do bug de mascaramento de PII — confirma 5/5 testes passando, incluindo o `TC-003` (segurança LGPD) que falhava antes do fix | Workflow, passo 9; "Onde a IA errou e como corrigi" |
| `05-saida-harness-auditoria-final.txt` | Saída de `python solution/harness_auditoria_submissao.py` — 13 testes programáticos que auditam esta submissão contra o brief oficial do desafio (lido do commit do repo, não de memória): os 5 critérios de qualidade + as 6 dicas + 2 obrigatoriedades do submission-guide. 13/13 passou, depois de corrigir um falso-positivo no próprio teste (não na submissão) | Workflow, passo 11 |
| `06-saida-consulta-auditoria.txt` | Saída de `python solution/ia_consulta.py "essa submissão está pronta pro PR?"` — confirma que o subagente Auditoria/Conformidade da IA de consulta responde lendo os dois JSONs de auditoria já extraídos, sem re-rodar nenhum harness | Workflow, passo 12 |
| `07-saida-harness-consistencia-artefatos.txt` | Saída de `python solution/harness_consistencia_artefatos.py` — 7 testes que extraem o mesmo número (MRR de conta específica, taxa de churn, % early churn, segmento de maior risco) de `compute_metrics()`, do `.xlsx`, do `dashboard.html`, e da IA de consulta rodada via subprocess, e comparam. 7/7 depois de corrigir um falso-positivo no teste (não nos artefatos) | Workflow, passo 13 |
| `08-saida-guard-entrada-dados.txt` | Saída de `python solution/guard_entrada_dados.py` sobre os dados reais da submissão — confirma que a base atual passa em todas as checagens (schema, vocabulário, formato de ID) | Workflow, passo 14 |
| `09-saida-harness-guard-entrada.txt` | Saída de `python solution/harness_guard_entrada.py` — 4 testes automatizados (os 3 tipos de erro de usuário simulados em cópia isolada + 1 controle de dado correto) confirmando que o guard pega cada classe de erro sem gerar falso-positivo | Workflow, passos 14-15 |

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
