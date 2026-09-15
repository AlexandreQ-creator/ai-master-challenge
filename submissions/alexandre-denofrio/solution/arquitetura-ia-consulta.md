# Arquitetura — IA de Consulta RavenStack (Diferencial adicional, Challenge 001)

## Objetivo e escopo

Uma IA de consulta que qualquer pessoa da RavenStack (CS — *Customer Success* —, CEO, Financeiro) usa para
perguntar sobre o diagnóstico de churn em linguagem natural — "quais contas de
DevTools estão em risco?", "qual o MRR da Company_4?", "por que o churn está
acelerando?" — e recebe uma resposta ancorada nos dados reais, não uma alucinação.

**Escopo deliberadamente limitado:** esta IA responde perguntas sobre o que **já foi
analisado e verificado** por `analise.py`/`gerar_excel.py` nesta submissão — não gera
análise nova sob demanda (ex.: "e se eu filtrar só contas Enterprise?" fica fora de
escopo v1). Essa é uma escolha de design, não uma limitação técnica esquecida: gerar
consulta nova on-the-fly abre risco real de alucinação de número em cima de dados
sensíveis de negócio, e o critério de qualidade do challenge ("os insights são
verificáveis?") fica mais difícil de garantir quando a resposta não vem de um cálculo
já auditado. Se a v1 se provar útil, "consulta nova sob demanda" é a extensão natural
de v2 — não construída agora.

**Implementado e testado em `solution/ia_consulta.py`**, sem dependência de chave de
API (roteamento determinístico por palavras-chave em PT-BR, não LLM externo; decisão
deliberada para manter a mesma dependência mínima já usada no resto da submissão e
garantir que qualquer avaliador rode sem configurar credencial). Dois pontos de
entrada para a mesma classe `IAConsultaRavenStack`:

- **Terminal** — `python ia_consulta.py` (chat interativo), `python ia_consulta.py
  "pergunta"` (modo não-interativo), `python ia_consulta.py --self-test` (roda 7
  perguntas de exemplo cobrindo os 5 domínios originais + 2 recusas de escopo).
- **Navegador, embutido no `dashboard.html`** — uma caixa de chat que fala com a IA
  via `POST /api/perguntar` em `solution/servidor_dashboard.py`. Este é o ponto de
  entrada que de fato atende o critério "o CEO não-técnico consegue ler e agir": um
  terminal não é acessível para esse público, e a IA de consulta ficaria construída
  mas inutilizável por quem ela foi desenhada para atender sem essa integração. A
  instância da IA é criada uma vez (`_get_ia_consulta()`, lazy) e reaproveitada entre
  perguntas, para não recalcular `compute_metrics()` a cada mensagem do chat.

---

## Por que agentes/subagentes, e não um único prompt

Um único prompt gigante ("aqui estão os 5 CSVs, responda perguntas sobre churn") é
exatamente o "baseline" que o brief do G4 avisa para não repetir — resposta genérica,
sem cruzamento real entre tabelas, sem garantia de que o número citado veio de fato do
dado. A separação em agentes existe para impor, estruturalmente, as mesmas garantias
que já seguimos manualmente nesta sessão: schema real (não presumido), números
conferidos contra a fonte antes de virar texto, e distinção clara entre o que é fato
verificável e o que é interpretação.

---

## Os agentes

### 1. Agente Roteador (`Query Router`)

**Papel:** primeiro a receber a pergunta do usuário. Decide qual subagente(s) de
domínio deve responder, e se a pergunta está dentro do escopo desta IA.

**Responsabilidades:**
- Classificar a pergunta em uma (ou mais) das 5 categorias que o brief do challenge já
  define como eixos de achado: *causa raiz*, *segmento de risco*, *conta específica*,
  *recomendação/ação*, *metodologia/limitação*.
- Recusar educadamente perguntas fora do grounding disponível (ex.: "qual vai ser o
  churn em 2027?" — não há dado nem modelo preditivo nesta submissão; ver Limitações
  do `README.md`) em vez de deixar um subagente tentar adivinhar.
- Recusar perguntas que pedem análise nova não coberta (escopo v1, ver seção acima) e
  informar isso explicitamente ao usuário, em vez de fingir que respondeu.

**Não faz:** não calcula nada, não acessa os CSVs diretamente. É só triagem.

### 2. Agente de Grounding (`Data Grounding Agent`)

**Papel:** a única porta de entrada aos dados reais. Nenhum outro agente lê CSV ou
inventa número — todos pedem a este agente.

**Responsabilidades:**
- Serve como wrapper fino sobre a mesma função `compute_metrics()` já construída em
  `solution/gerar_excel.py` (reaproveitar, não duplicar — mesma decisão de design que
  já vale entre o `.xlsx` e o `.md` gerados por aquele script).
- Responde só com os números/achados que já existem no dicionário retornado por
  `compute_metrics()` mais a lista de achados textuais do `README.md` (achados 1-6).
  Se a pergunta pedir algo fora desse conjunto (ex.: um cruzamento novo), devolve
  "não calculado nesta versão" para o Roteador decidir a recusa.
- Nunca gera texto solto — devolve dado estruturado (número, linha de tabela, trecho
  de achado com sua fonte) para o próximo agente formatar.

**Lição aplicada aqui:** este é o mesmo princípio de "grounding estrito" que a Agent
Skill do Gemini (`skill-mestre-analise-dados.md`) já declarava como guardrail, mas
que a v1 do `skill-g4-ai-master-churn.md` não conseguia cumprir de fato — porque seu
contrato de dados não batia com o schema real. Aqui a garantia é estrutural: o agente
literalmente não tem acesso a nada além do que `compute_metrics()` calculou e
verificou.

### 3. Agentes de Domínio (subagentes especialistas)

Cada um cobre um dos eixos de pergunta que o Roteador identifica, e só pode falar
depois de receber dado do Agente de Grounding — nunca calcula por conta própria.

| Subagente | Responde perguntas tipo | Fonte de dado |
|---|---|---|
| **Causa Raiz** | "por que o churn está subindo?", "é o suporte?", "é o produto?" | Achados 1, 2, 3, 6 do README — inclui explicitamente separar correlação de causa (ex.: recusar afirmar que suporte é causa, já que o achado 6 mostra que não é) |
| **Segmentos de Risco** | "quais indústrias/canais têm mais risco?", "e trial vs. pago?" | Achado 4 + tabela de segmentação (`seg_rows` em `compute_metrics()`) |
| **Contas Específicas** | "qual o MRR da Company_4?", "quais as top 10 contas em risco?" | Tabela `churned_mrr` em `compute_metrics()` |
| **Recomendações** | "o que a gente deveria fazer?", "qual a prioridade?" | As 5 recomendações priorizadas do README, com o número de impacto estimado já calculado |
| **Metodologia/Limitações** | "como vocês chegaram nisso?", "dá pra confiar nesse número?" | Seção Limitações + Process Log do README — inclui admitir abertamente o que não foi verificado (ex. dicionário de dados das features anônimas) |
| **Auditoria/Conformidade** | "essa submissão está pronta pro PR?", "passou nos critérios do brief?" | `process-log/auditoria-final.json`, gerado por `harness_auditoria_submissao.py` — nunca re-roda o harness, só lê o resultado já extraído (mesma disciplina de `compute_metrics()`) |

**Por que separar por eixo em vez de um agente de domínio único:** cada eixo tem um
modo de falha diferente que o brief do challenge testa explicitamente. "Causa Raiz"
precisa recusar respostas que confundem correlação com causa (critério de qualidade
nº4 do brief). "Contas Específicas" precisa nunca arredondar ou aproximar um MRR
(critério nº2, "mostre os números"). Um agente genérico tende a misturar esses modos
de disciplina; agentes especializados tornam cada guardrail explícito e testável
isoladamente — o mesmo raciocínio por trás de ter dividido `analise.py` em seções
numeradas por pergunta, em vez de uma função monolítica.

### 4. Agente de Resposta Executiva (`Executive Response Agent`)

**Papel:** o agente que escreve a frase mostrada ao usuário — mas não é
necessariamente a última etapa da cadeia (ver Agente Auditor, item 5 abaixo, que pode
devolver a resposta para reformulação). Recebe o dado estruturado do subagente de
domínio e o transforma em linguagem executiva — não-técnica, direto ao ponto, como o
critério "o CEO consegue ler e agir?" exige.

**Responsabilidades:**
- Nunca inventa número — só reformula o que já veio pronto do subagente de domínio.
- Cita a fonte de cada número (ex.: "segundo `analise.py`, seção 6" ou referência à
  linha do README) — rastreabilidade, não caixa-preta.
- Aplica o mesmo padrão de registro formal e siglas expandidas na primeira ocorrência
  que já seguimos no README (regra deste projeto sobre material de candidatura).

### 5. Agente Auditor de Contexto Limpo (`Clean-Context Auditor`)

**Papel:** revisa a resposta final do Agente de Resposta Executiva **sem ter
participado da geração dela** — não vê a pergunta original nem o raciocínio dos
subagentes de domínio, só recebe a resposta pronta e os dados brutos do Agente de
Grounding para conferir de forma independente.

**Por que este agente existe — prática já validada neste projeto, não hipótese:**
uma auditoria anterior (`indices-e-backups/auditoria-metodo-notebooklm.md`) mediu um
viés real e recorrente no processo de redação de material de candidatura deste mesmo
projeto: o **"mascaramento por justaposição"** — quando o texto usa vocabulário
adjacente ou ordem de palavras que cria a impressão de algo que a fonte não sustenta
de fato, sem nunca afirmar algo literalmente falso. Esse viés passa despercebido por
uma revisão que só checa terminologia/consistência, porque o erro não está em nenhuma
frase isolada — só aparece na leitura corrida, ou quando alguém sem o contexto do
processo de escrita lê o resultado do zero. O próprio NotebookLM, de forma
independente, nomeou o mesmo risco ao auditar seu método
(`indices-e-backups/handoff_sessao_2026-09-14.md`) — confirmação cruzada real entre
dois métodos de geração diferentes, não uma preocupação teórica de um só lado.

Aplicado a esta IA de consulta, o risco equivalente é: uma resposta sobre churn que
tecnicamente cita números corretos, mas os ordena/enfatiza de um jeito que sugere uma
causa diferente da que os dados sustentam (ex.: mencionar `reason_code=support` logo
antes de uma recomendação sobre suporte, mesmo o achado 6 do README já tendo
descartado suporte como causa operacional real). Um agente que participou da geração
não pega esse tipo de erro — ele já "concorda" com o próprio raciocínio. É preciso um
agente que não viu o processo.

**Responsabilidades:**
- Recebe só: (a) a resposta final formatada, (b) o dado bruto que o Agente de
  Grounding devolveu para aquela pergunta. Não recebe o raciocínio intermediário dos
  subagentes de domínio.
- Confere se cada afirmação da resposta é sustentada literalmente pelo dado bruto —
  não se é plausível, se soa correto, ou se "faz sentido" no contexto.
- Sinaliza especificamente: números arredondados sem indicar isso, causa e correlação
  apresentadas na mesma frase sem distinção clara, ênfase/ordem que sugere conclusão
  não sustentada pelos achados 1-6 do README.
- Pode aprovar, aprovar com ressalva anexada à resposta, ou bloquear e devolver ao
  Agente de Resposta Executiva para reformular — nunca reescreve a resposta ele
  mesmo (evitaria a mesma armadilha: um agente que edita já está "dentro" do texto).

**Custo vs. benefício, já avaliado:** rodar um quinto agente em toda pergunta tem
custo real (mais uma chamada, mais latência) — mas o próprio princípio "qualidade como
piso, custo como critério de desempate" (regra deste projeto) já resolve essa tensão:
para perguntas sobre causa raiz e recomendações (onde o risco de mascaramento por
justaposição é maior), a auditoria é obrigatória; para perguntas puramente factuais
sem risco de interpretação (ex.: "qual o MRR da Company_4?", resposta é um único
número direto da tabela), o Roteador pode marcar a pergunta como isenta de auditoria
— o subagente **Contas Específicas** tem esse risco mais baixo que **Causa Raiz** ou
**Recomendações**, e a arquitetura deve refletir essa diferença em vez de tratar toda
pergunta com o mesmo custo.

---

## Segurança da informação e privacidade de dados

Esta seção nasce diretamente de um bug real encontrado e corrigido nesta mesma sessão
— não é checklist genérico de compliance copiado de outro lugar.

### O que já foi validado (e por quê importa)

Ao revisar `mestre_dados_engine.py` (material trazido pelo Gemini, função
`mask_pii()`), foi encontrado um bug de mascaramento de PII (*Personally Identifiable Information*, dado pessoal identificável): a checagem
`if masked_df[col].dtype == 'object':` nunca era verdadeira no pandas 3.0 (que mudou o
dtype padrão de string de `object` para `str` nativo) — então o bloco de mascaramento
**nunca executava**, e e-mail/CPF saíam em texto puro, sem nenhuma transformação. O
próprio harness de 5 testes do Gemini reportava "Bateria Concluída com Sucesso!"
mesmo com o teste de vazamento de PII (`TC-003`) falhando de fato. Corrigido nesta
sessão (removida a checagem de dtype frágil; `.astype(str)` já garante a conversão
antes de mascarar) e reconfirmado com dado real de e-mail/CPF depois do fix.

A lição não é "pandas tem um bug" — é: **uma guarda de segurança que nunca é
exercitada por um teste automatizado que falha de verdade quando a guarda falha não é
uma guarda, é decoração.** O harness existia, tinha o cenário certo (TC-003), e ainda
assim o bug ficou invisível até alguém rodar o teste de propósito e ler o resultado —
porque o "veredito" final do harness era uma mensagem fixa, não condicionada ao
resultado real dos testes.

### Como isso se aplica à IA de consulta

Esta submissão usa dados de exemplo do Kaggle (`account_name` = `Company_0`,
`Company_1`...) — não há PII real neste dataset específico, e a IA de consulta como
especificada aqui nunca precisa mascarar nada para responder às perguntas do brief.
Mas a arquitetura é desenhada assumindo que, em produção real na RavenStack, as
mesmas tabelas teriam nome de empresa/contato real, e por isso os guardrails abaixo
fazem parte da especificação, não são adicionados depois:

1. **Nenhum agente desta arquitetura tem acesso de escrita a nada.** Todos os 5
   agentes (Roteador, Grounding, subagentes de Domínio, Resposta Executiva, Auditor)
   são consumidores read-only de `compute_metrics()` — nenhum grava em CSV, banco, ou
   qualquer armazenamento. Elimina uma classe inteira de risco (alteração acidental
   de dado real de pipeline) sem precisar de permissão granular por agente.
2. **Qualquer guarda de segurança (mascaramento, filtro de campo sensível) precisa de
   teste automatizado que falha de verdade quando a guarda falha** — não checagem de
   tipo "otimista" como a que quebrou no `mestre_dados_engine.py`. Antes de qualquer
   implementação real desta arquitetura, o equivalente ao harness de 5 cenários
   (`harness-mestre-dados.py`, já corrigido e rodando 5/5 nesta sessão) deve cobrir:
   dado limpo (golden dataset), dado com PII simulado, e confirmação ativa de que o
   PII não aparece na saída — não só "não crashou".
3. **O Agente de Grounding é o único ponto de acesso aos dados brutos** (mesmo
   princípio da seção "Os agentes" acima) — isso também é a superfície mínima onde um
   filtro de PII precisaria existir em produção real, em vez de espalhar a
   responsabilidade de mascaramento por múltiplos agentes (que é exatamente o tipo de
   duplicação que aumenta a chance de um deles esquecer o filtro).
4. **Recusa é o comportamento seguro por padrão.** Consistente com o guardrail "recusa
   explícita é preferível a resposta aproximada" já listado acima: se o Agente de
   Grounding não consegue confirmar que um campo está livre de PII (em um cenário de
   produção real com dado sensível), a resposta correta é recusar/mascarar por
   padrão, nunca vazar por otimismo — o oposto exato do que o bug do `dtype` causou.

---

## Fluxo ponta a ponta

```
Usuário pergunta
      │
      ▼
┌─────────────────────┐
│  Agente Roteador     │  classifica a pergunta, ou recusa (fora de escopo/grounding)
└──────────┬───────────┘
           │ dentro do escopo
           ▼
┌─────────────────────┐
│ Agente de Grounding  │  busca em compute_metrics() + achados do README
│ (compute_metrics())  │  nunca inventa, devolve "não calculado" se faltar
└──────────┬───────────┘
           │ dado estruturado
           ▼
┌─────────────────────┐
│ Subagente de Domínio │  Causa Raiz | Segmentos | Contas | Recomendações | Metodologia
│  (1 dos 5 acima)     │  aplica o guardrail específico do seu eixo
└──────────┬───────────┘
           │ dado + guardrail aplicado
           ▼
┌─────────────────────┐
│ Agente de Resposta   │  formata em linguagem executiva, cita a fonte
│ Executiva             │
└──────────┬───────────┘
           │
           ▼
┌─────────────────────┐
│ Auditor de Contexto  │  não viu o processo de geração; confere resposta
│ Limpo                 │  final contra o dado bruto, sem reescrever
│ (obrigatório para     │  aprova | aprova com ressalva | bloqueia e devolve
│  Causa Raiz/Recomen-  │
│  dações; opcional     │
│  para perguntas       │
│  puramente factuais)  │
└──────────┬───────────┘
           │
           ▼
     Resposta ao usuário
```

---

## Guardrails aplicados em toda a cadeia (herdados do que já validamos nesta sessão)

1. **Fonte única de cálculo** — nenhum agente recalcula nada; tudo passa por
   `compute_metrics()`, já testado e com números conferidos contra os CSVs. Mesmo
   padrão que já garante que `.xlsx` e `.md` gerados por `gerar_excel.py` nunca
   divergem entre si.
2. **Checagem de tipo explícita e testada, não presumida** — lição direta do bug
   encontrado no `mestre_dados_engine.py` desta sessão (a checagem `dtype == 'object'`
   quebrou silenciosamente entre versões do pandas). Qualquer validação de tipo nesta
   arquitetura deve ter teste automatizado equivalente ao harness de 5 cenários já
   usado ali, antes de ser considerada confiável.
3. **Recusa explícita é preferível a resposta aproximada** — se o Agente de Grounding
   não tem o dado, a cadeia inteira deve devolver "não calculado nesta versão", nunca
   uma estimativa não verificada. Isso é o oposto do risco identificado no bug da v12
   do backup NotebookLM (`memory/feedback_consolidar_backup_notebooklm_apos_arquivar.md`)
   — dado ausente/errado que passa despercebido por parecer plausível.
4. **Toda resposta cita sua fonte** — rastreável até a linha do `README.md` ou seção
   de `analise.py`, nunca uma afirmação solta.
5. **Um agente não audita o próprio raciocínio** — o Auditor de Contexto Limpo (seção
   5 acima) só recebe resposta final + dado bruto, nunca o histórico de geração; essa
   separação é o que torna a auditoria capaz de pegar "mascaramento por justaposição",
   igual já validado no processo de redação de CV deste projeto.

Ver também a seção dedicada **"Segurança da informação e privacidade de dados"**
acima — trata especificamente do que a arquitetura garante sobre PII/dado sensível,
com o bug real de mascaramento encontrado e corrigido nesta sessão como caso concreto.

---

## Harness de auditoria final — a própria submissão auditada contra o brief oficial

Além dos 6 agentes de consulta, dois harnesses fecham o loop, cobrindo dois tipos de
risco diferentes — conteúdo e consistência:

### `harness_auditoria_submissao.py` — o conteúdo cobre o brief oficial?

Audita a submissão inteira contra o brief **oficial**, lido direto do commit do
repositório (`challenges/data-001-churn/README.md`), não de memória ou paráfrase.
Mesmo padrão do `harness-mestre-dados.py` já corrigido nesta sessão — 13 testes
programáticos (os 5 critérios de qualidade + as 6 dicas do brief + 2 obrigatoriedades
do `submission-guide.md`), cada um com assert real contra os artefatos reais
(`README.md`, `analise.py`, a estrutura de pasta), veredito condicionado ao resultado
real, não uma mensagem fixa.

**Achado real da primeira rodada:** o harness reportou 12/13 — não porque a
submissão estava incompleta, mas porque o teste da dica "uso cresceu para todos os
segmentos?" procurava a string literal `"H1-2023"`, e o README usa a forma por
extenso "primeiro semestre de 2023". Corrigido o teste (não a submissão, que já
estava correta), confirmado 13/13 — evidência de que o harness testa de verdade, não
finge passar. Saída completa em `process-log/chat-exports/05-saida-harness-auditoria-final.txt`.

### `harness_consistencia_artefatos.py` — o mesmo número bate em todos os formatos?

Diferente do harness acima (que testa se o *texto* do README cobre o brief), este
testa se o *mesmo número* aparece igual em `compute_metrics()` (fonte única), no
`.xlsx`, no `dashboard.html`, e na resposta real da IA de consulta (via subprocess,
não import direto — testando o comportamento real de linha de comando). 7 testes:
MRR da Company_4, taxa de churn geral, % de churn em <90 dias, e o segmento de maior
risco, cada um extraído por múltiplos caminhos independentes e comparado.

**Achado real da primeira rodada:** 6/7 — o teste `CONS-2` (MRR no dashboard) não
encontrava a linha da Company_4. Investigação mostrou que era o regex do teste
procurando `US\$` quando a tabela de "Contas em Risco" do dashboard formata só com
`$` (sem "US" antes) — diferente de outras seções do mesmo HTML que usam "US$".
Corrigido o teste depois de ler o HTML real, não assumir o formato; confirmado 7/7.
Mesmo padrão de disciplina do harness de auditoria acima: nunca aceitar "falhou" nem
"passou" sem investigar a causa raiz primeiro. Saída completa em
`process-log/chat-exports/07-saida-harness-consistencia-artefatos.txt`.

Os dois resultados são salvos (`process-log/auditoria-final.json`,
`process-log/consistencia-artefatos.json`) — dados já extraídos, consultáveis pelo 6º
subagente (Auditoria/Conformidade) sem re-rodar nenhum harness a cada pergunta, mesma
disciplina de "calcular uma vez, consumir depois" já aplicada em `compute_metrics()`.

### `guard_entrada_dados.py` — a base carregada é a certa?

Um terceiro tipo de checagem, complementar aos dois harnesses acima: não audita o que
já foi gerado, valida o que está prestes a ser processado. Roda automaticamente no
início de `analise.py` e de `compute_metrics()` (então também protege
`gerar_excel.py`, `gerar_dashboard.py` e `ia_consulta.py`, que dependem dela), e pega
três classes de erro que um usuário real pode cometer ao trocar a base de dados:

1. **Base diferente/incompatível** — coluna obrigatória faltando ou extra indica CSV
   de outra fonte, não o dataset RavenStack esperado.
2. **Valor traduzido/idioma errado** — o dataset é inteiramente em inglês
   (`plan_tier=Basic/Pro/Enterprise`, `referral_source=ads/event/organic/...`); um
   valor como "Básico" sinaliza mistura com uma versão traduzida da base.
3. **Terminologia do domínio incorreta** — colunas de vocabulário fechado
   (`reason_code`, `priority`) comparadas contra o conjunto de valores válidos real,
   extraído dos CSVs antes de escrever qualquer regra (não presumido).

Testado com `harness_guard_entrada.py` — 4 cenários (os 3 erros acima, simulados numa
cópia temporária isolada dos dados reais, mais um controle de dado correto).

**Achado real ao formalizar este teste:** os 4 testes internos passavam, mas o script
terminava com exit code 1 — a função `run()` chamava `relatorio_final()` sem
`return`, então sempre devolvia `None`. Corrigido, e a checagem revelou o mesmo bug
nos outros dois harnesses desta submissão (`harness_auditoria_submissao.py`,
`harness_consistencia_artefatos.py`) — mascarado até então porque a verificação
manual olhava só o texto impresso, nunca o exit code isoladamente. Os três foram
corrigidos. Relevante porque um exit code sempre 1 quebraria qualquer hook de
pre-commit ou CI que dependesse desses harnesses, mesmo com 100% dos testes
passando — a mesma classe de falha silenciosa do bug de dtype no `mestre_dados_engine.py`
(seção "Segurança da informação" acima): a guarda existia, o teste certo existia, e
ainda assim o problema só apareceu quando alguém checou o sinal certo, não só a saída
de texto.

---

## O que fica fora desta v1 (registrado, não esquecido)

- Geração de análise nova sob demanda (filtros/cruzamentos não pré-calculados) —
  decisão explícita de escopo, ver seção "Objetivo e escopo" acima.
- Modelo preditivo de churn — já descartado no `README.md` da submissão, mesma
  justificativa se aplica aqui (causa raiz é estrutural, não comportamental).
- Interface de chat real (terminal, web, ou outra) — implementação intencionalmente
  não decidida ainda; este documento é a especificação a validar antes de escolher
  ambiente de execução.
