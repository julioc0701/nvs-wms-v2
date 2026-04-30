# LAUDO TÉCNICO — NVS AGENT
## Agente de Diagnóstico e Otimização de Anúncios no Mercado Livre

**Versão:** 1.0  
**Data:** Abril 2026  
**Projeto:** NØR Group / Novaes  
**Status:** MVP Funcional — Pipeline Completo Validado

---

## 1. O QUE É ESTE PROJETO

O NVS Agent é um sistema de inteligência artificial que analisa anúncios do Mercado Livre de forma automatizada, profunda e estruturada, entregando um diagnóstico completo com plano de ação prioritário e conteúdo otimizado pronto para uso.

Em termos simples: você passa o ID de um anúncio (ex: `MLB3661846735`) e o agente entrega, em minutos, tudo o que precisa ser feito para melhorar aquele anúncio — com exemplos reais dos compradores, prioridades definidas e textos prontos para aplicar.

O projeto nasce de uma necessidade real da operação Novaes/NØR: avaliar e otimizar dezenas de anúncios no Mercado Livre de forma escalável, com critérios objetivos e acionáveis, sem depender de análise manual subjetiva.

---

## 2. O PROBLEMA QUE ELE RESOLVE

### O cenário atual (sem o agente)

Quando um vendedor quer melhorar um anúncio no Mercado Livre, precisa:

1. Verificar manualmente o health score e descobrir o que está baixando a nota
2. Abrir cada foto individualmente para avaliar qualidade
3. Ler centenas de reviews para identificar padrões de reclamação
4. Ler todas as perguntas dos compradores para entender dúvidas frequentes
5. Comparar com anúncios concorrentes para identificar lacunas
6. Reescrever título respeitando regras do ML (sem PI_FAKES, limite de caracteres etc.)
7. Reescrever descrição de forma persuasiva cobrindo todas as objeções
8. Criar briefs para fotógrafo e editor de vídeo
9. Fazer tudo isso de novo para o próximo anúncio

**Para um catálogo de 50 produtos, isso levaria semanas de trabalho manual.**

### A hipótese central do projeto

> As perguntas dos anúncios são o ouro — elas revelam as dúvidas reais que impedem a compra, antes de ela acontecer. Reviews mostram o que deu errado depois. Ambos precisam ser tratados, mas as perguntas têm peso maior porque representam objeções ativas no momento de decisão.

Essa hipótese orientou toda a arquitetura do sistema.

---

## 3. O QUE O AGENTE FAZ — VISÃO GERAL

O agente executa um pipeline sequencial em 5 etapas:

```
[1] COLETA          →  API Mercado Livre (item, fotos, ficha, reviews, perguntas)
[2] ANÁLISE         →  4 trilhas especializadas rodando sobre os dados coletados
[3] SCORECARD       →  Nota 0-100% em 4 eixos replicando a lógica interna do ML
[4] GERAÇÃO LLM     →  Claude Sonnet produz título, descrição, 8 prompts foto, 5 prompts vídeo
[5] RELATÓRIO       →  7 blocos estruturados com diagnóstico + plano de ação
```

**Tempo total por anúncio:** ~60-90 segundos (coleta API + geração LLM)

---

## 4. ARQUITETURA — AS 4 TRILHAS DE ANÁLISE

### Por que 4 trilhas?

Um anúncio no Mercado Livre tem 4 dimensões críticas que influenciam diretamente a conversão e o rankeamento:

1. **O texto** (título + descrição) — comunica o produto e atende às regras do ML
2. **As fotos** — determinam a Nota PQT (Padrão de Qualidade de Thumbnail), fator direto de rankeamento
3. **A voz do comprador** (reviews + perguntas) — revela objeções reais que impedem a venda
4. **O mercado** (concorrentes) — mostra o que os anúncios que vendem mais fazem diferente

Cada trilha tem seu próprio módulo, sua própria lógica e entrega um resultado estruturado que alimenta o scorecard e o relatório final.

---

### TRILHA A — Análise de Descrição e Título

**Arquivo:** `src/trilhas/descricao/analyzer.py`

**O que analisa:**
- Título do anúncio (até 60 caracteres no ML)
- Descrição completa
- Ficha técnica (atributos preenchidos vs. obrigatórios/relevantes)

**Lógica de verificação do título:**

O título passa por uma série de regras baseadas nas políticas reais do Mercado Livre:

| Regra | O que verifica | Severidade |
|---|---|---|
| PI_FAKES | Marca de terceiro no título sem "para" ou "compatível com" antes | Crítica |
| Comprimento | Acima de 60 caracteres | Alta |
| Caixa alta | Título inteiro em maiúsculas | Média |
| Palavra proibida | "Grátis", "Frete grátis", etc. no título | Alta |
| Ausência de modelo | Produto de moto sem modelo/ano no título | Média |

**Regra PI_FAKES — o ponto mais crítico:**

O Mercado Livre penaliza anúncios de peças de reposição que usam marcas de montadoras (Honda, Yamaha, Suzuki, Fiat, etc.) no título sem indicar que é uma peça *compatível com* aquela marca, não *fabricada* por ela. Isso evita que o comprador confunda uma peça genérica com a peça original da montadora.

Exemplo:
- ❌ `Escapamento Honda CG 160` → sugere que é fabricado pela Honda
- ✅ `Escapamento para Honda CG 160` → deixa claro que é compatível com
- ✅ `Escapamento compatível com CG 160` → idem

**Lógica da ficha técnica:**

O ML classifica atributos em 4 camadas:
1. **Obrigatórios** — sem eles o anúncio não publica
2. **Relevantes (catalog_required)** — afetam rankeamento no catálogo
3. **Comuns** — informações adicionais que melhoram a conversão
4. **Ocultos** — usados internamente pelo ML para categorização

O agente calcula a taxa de preenchimento de cada camada e identifica os atributos faltando, priorizando os obrigatórios e relevantes.

---

### TRILHA B — Análise de Fotos

**Arquivo:** `src/trilhas/fotos/analyzer.py`

**O que analisa:**
- Qualidade técnica de cada foto (NIMA score via IA, quando disponível)
- Fundo branco na capa (exigência PQT do ML)
- Resolução mínima (500px, ideal 1200x1200)
- Ocupação do produto no frame
- Cobertura do funil de imagens (8 slots recomendados)

**O conceito do Funil de Imagens:**

O agente espera que o conjunto de fotos de um anúncio cubra 8 "slots" funcionais no processo de decisão do comprador:

```
Slot 1: Capa Premium (produto centralizado, fundo branco, alta qualidade)
Slot 2: Detalhe do Material (close-up mostrando textura, acabamento, construção)
Slot 3: Benefício Principal (produto em contexto de uso)
Slot 4: Ajuste/Funcionalidade (como se instala ou usa)
Slot 5: Encaixe/Instalação (produto montado no local correto)
Slot 6: Estrutura/Construção (visão construtiva, ângulo técnico)
Slot 7: Lifestyle (usuário real com o produto)
Slot 8: Kit Completo (flatlay de todos os itens da embalagem)
```

Se o anúncio tem menos de 8 fotos, os slots não cobertos são listados como "lacunas no funil" — oportunidades de melhoria claras.

**O PQT (Padrão de Qualidade de Thumbnail):**

O ML avalia cada foto com uma tag de qualidade interna:
- `good_quality_picture` → 1.0 (excelente)
- `good_quality_thumbnail` → 0.9 (bom)
- `unknown_quality_picture` → 0.5 (desconhecido)
- `poor_quality_picture` → 0.1 (ruim)

A média ponderada dessas tags é o `images_pct` no scorecard, com penalidade de -20% se a capa não tiver fundo branco.

**NIMA Score:**

Quando a biblioteca `pyiqa` está instalada, o agente calcula o NIMA (Neural Image Assessment) — um modelo de IA treinado para avaliar qualidade estética de imagens em uma escala de 0 a 10, replicando a percepção humana. Score abaixo de 4.5 aciona recomendação de substituição.

---

### TRILHA C — Análise de Objeções (Reviews + Perguntas)

**Arquivo:** `src/trilhas/objecoes/analyzer.py`

**Esta é a trilha mais estratégica do sistema.** Ela transforma dados brutos de compradores em inteligência de negócio acionável.

**A distinção fundamental:**

| Fonte | Momento | Natureza | Peso |
|---|---|---|---|
| Reviews | Após a compra | Avaliação de experiência | 1x |
| Perguntas do anúncio | Antes da compra | Objeção ativa de decisão | **2x** |

As perguntas têm peso 2x porque representam um comprador *prestes a comprar* que encontrou uma dúvida que pode impedir a conversão. Resolver essa dúvida na descrição ou no título remove uma barreira real no funil de vendas.

**Estrutura de detecção de temas:**

O agente classifica cada texto (review ou pergunta) em 8 temas de objeção:

```
1. compatibilidade  → serve, encaixa, qual modelo, qual ano, qual moto...
2. qualidade        → frágil, quebrou, material, durável, resistente...
3. instalacao       → instalar, difícil, ferramenta, mecânico, parafuso...
4. conteudo_kit     → vem, acompanha, inclui, par, esquerdo, direito...
5. prazo_entrega    → demorou, rápido, entrega, correios, frete...
6. embalagem        → amassado, danificado, caixa, proteção...
7. preco_custo      → vale a pena, caro, preço, economico...
8. garantia_suporte → garantia, defeito, troca, atendimento...
```

**Pipeline de processamento:**

```
1. Normaliza texto (acentos, pontuação, caixa baixa)
2. Detecta quais temas aparecem em cada texto
3. Para reviews: adiciona 1x ao cluster do tema
4. Para perguntas: verifica se é objeção de compra; se sim, adiciona 2x
5. Calcula frequência de cada tema como % do total de sinais
6. Classifica intensidade: leve / moderada / forte
7. Classifica cluster como OBJEÇÃO ou PONTO FORTE
8. Para cada objeção: gera tratativa por canal (descrição, resposta padrão, foto sugerida, título)
```

**Critério de classificação como objeção:**

Um tema vira "objeção mapeada" se:
- Mais de 25% dos sinais daquele tema têm sentimento negativo, OU
- Pelo menos 2 perguntas únicas perguntam sobre aquele tema

Esse segundo critério é chave — 2 compradores diferentes fazendo a mesma pergunta antes de comprar é sinal claro de lacuna informacional no anúncio.

**Tratativas por canal:**

Para cada objeção identificada, o sistema gera orientações específicas para 3 canais:

1. **Descrição:** o que adicionar ao texto (ex: seção COMPATIBILIDADE com lista ✔/✗ por modelo e ano)
2. **Resposta padrão:** texto pronto para responder a pergunta do comprador (personalizado por tema)
3. **Título:** se o tema deve gerar mudança no título
4. **Foto sugerida:** qual slot do funil de imagens resolve visualmente aquela dúvida

**NPS Estimado:**

Calculado com base na distribuição global de estrelas (`rating_levels` da API do ML):
```
NPS = (reviews 4★ + 5★ - reviews 1★ + 2★) / total_reviews * 100
```

Para o anúncio MLB3661846735: 726 reviews 5★ + 37 reviews 4★ - 15 reviews 1★ - 4 reviews 2★ = **NPS 94%** — coerente com média 4.8/5.

---

### TRILHA D — Análise de Concorrentes

**Arquivo:** `src/trilhas/concorrentes/analyzer.py`

**O que analisa:**
- Anúncios concorrentes na mesma categoria
- Keywords usadas pelos top sellers que não estão no anúncio analisado
- Lacunas de posicionamento

**Entrega:**
- Lista de keywords faltando (para SEO interno do ML)
- Recomendações de posicionamento comparativo

---

## 5. O SCORECARD 4 EIXOS

**Arquivo:** `src/scoring/scorecard.py`

O scorecard replica a lógica de avaliação interna do Mercado Livre, transformando dados brutos em notas percentuais por eixo e uma nota geral.

### Os 4 eixos

| Eixo | O que mede | Fonte dos dados | Fórmula |
|---|---|---|---|
| **Saúde ML** | Conformidade geral com regras do ML | Campo `health` do item | Direta (0-1 → %) |
| **Imagens (PQT)** | Qualidade das fotos para thumbnail | Tags de qualidade por foto | Média ponderada das tags + penalidade fundo branco |
| **Ficha Técnica** | Completude dos atributos | Contagem de atributos preenchidos | (obrigatórios×1.0 + relevantes×0.7 + comuns×0.3) / max_possível |
| **Reviews** | Satisfação dos compradores | rating_average + volume | (media/5) × log(total+1)/log(1000+1) × 100 |

### Fórmula da nota geral

```
GERAL = média dos eixos que têm dados disponíveis
```

O eixo Reviews só entra no cálculo se o anúncio tiver pelo menos 5 reviews — isso evita que produtos novos sejam penalizados por ausência de histórico.

### O eixo Experience

O `experience_pct` é calculado separadamente (experiência do comprador: prazo de entrega, reclamações abertas, etc.) e **não entra na nota geral** — ele é informativo. Essa decisão replica o comportamento da planilha NVS Diagnóstico de referência.

### Conformidade

Além do scorecard, o sistema calcula uma métrica de **Conformidade** que desconta pontos por violações de guideline detectadas nas Trilhas A e B:

```
Conformidade = 100% - soma de penalidades por violação
  critica: -20%
  alta:    -10%
  media:    -5%
  baixa:    -2%
```

---

## 6. GERAÇÃO DE CONTEÚDO VIA LLM

**Arquivos:** `src/llm/client.py`, `src/llm/gerador.py`

### Modelos utilizados

O sistema usa dois modelos Claude com papéis distintos:

| Modelo | Velocidade | Uso |
|---|---|---|
| **Claude Haiku** | Rápido, econômico | Classificações, validações, tarefas estruturadas |
| **Claude Sonnet** | Mais capaz, criativo | Geração de conteúdo (título, descrição, prompts) |

### O que é gerado

**1. Título Otimizado**

O prompt recebe:
- Título atual
- Lista de violações detectadas na Trilha A
- Informações do produto (nome, compatibilidade, material)

O LLM reescreve o título corrigindo todas as violações (PI_FAKES, comprimento, formatação) sem perder as palavras-chave principais.

**2. Descrição Otimizada (5 seções)**

O prompt recebe:
- Informações do produto
- Lista de objeções mapeadas com exemplos reais dos compradores
- Pontos fortes identificados nos reviews

A descrição é estruturada em 5 blocos funcionais:
1. **Lead persuasivo** — primeira frase que prende o comprador e menciona a objeção principal
2. **Compatibilidade** — lista ✔/✗ por modelo/ano (se produto de moto)
3. **Especificações Técnicas** — material, dimensões, normas
4. **Conteúdo do Kit** — o que vem na caixa
5. **Garantia e Suporte** — texto de segurança que reduz fricção para comprar

**3. 8 Prompts de Imagem**

Um prompt de geração de imagem (para Midjourney, Stable Diffusion, DALL-E ou briefing para fotógrafo) para cada slot do funil. Cada prompt inclui:
- Descrição visual do produto + contexto
- Instruções de iluminação e ângulo
- Formato (retrato 3:4, sem texto, realista)
- "Chips" de palavras-chave para ajuste rápido

**4. 5 Prompts de Vídeo**

Prompts para os 5 tipos de vídeo mais eficientes para anúncios de produtos:
1. Movimento do Produto (câmera explorando o produto)
2. Uso Real (produto em contexto autêntico)
3. Ajuste/Funcionalidade (instalação passo a passo)
4. Detalhe Premium (macro com luz revelando qualidade)
5. Reveal Final (câmera orbital, efeito cinematográfico)

---

## 7. O RELATÓRIO DE SAÍDA — 7 BLOCOS NOR

O relatório final é estruturado em 7 blocos, cada um com um propósito específico:

### Bloco 1 — Scorecard
```
Saude ML         87.0%  [OK]
Imagens (PQT)    50.0%  [ATENCAO]
Ficha Tecnica    87.0%  [OK]
Reviews          92.8%  [OK]
--------------------------------
GERAL            79.2%  [BOM]
Experience      100.0%  (fora da media geral)
Conformidade     98.0%
```
→ Diagnóstico em 10 segundos de leitura. Identifica imediatamente o eixo crítico.

### Bloco 2 — Objeções Reais dos Compradores
Mostra cada objeção mapeada com:
- Nome do tema + % dos compradores que mencionam
- Intensidade (leve/moderada/forte)
- Contagem de sinais separada: perguntas (p) + reviews (r)
- Exemplo real transcrito da voz do comprador
- Tratativa por canal (título, descrição, foto)

Este bloco é o coração estratégico do relatório — transforma a "voz do cliente" em ação concreta.

### Bloco 3 — Plano de Ação Prioritizado
Lista ordenada de ações por severidade (crítica → alta → média → baixa):
- Violações de título
- Violações de descrição
- Violações PQT (fotos)
- Recomendações por foto (SUBSTITUIR/MELHORAR)
- Lacunas no funil de imagens
- Objeções sem tratativa
- Ficha técnica incompleta
- Keywords de concorrentes faltando

### Blocos 4-7 — Conteúdo Gerado (via LLM)
- **Bloco 4:** Título atual vs. título otimizado (com contagem de caracteres)
- **Bloco 5:** Descrição completa otimizada (pronta para colar)
- **Bloco 6:** 8 prompts de imagem com headers e chips
- **Bloco 7:** 5 prompts de vídeo com sequência de montagem

---

## 8. O PIPELINE TÉCNICO COMPLETO

```
ENTRADA: MLB3661846735

[COLETA — ml_client.py]
  ├── GET /items/{id}                    → titulo, preco, atributos, saude, imagens
  ├── GET /items/{id}/description        → texto da descrição
  ├── GET /reviews/item/{id}             → reviews (texts, stars, rating_levels)
  ├── GET /questions/search?item={id}    → perguntas dos compradores
  └── GET /users/{seller_id}/items_restrictions → infrações ativas

[ANÁLISE — 4 trilhas em sequência]
  ├── Trilha A: DescricaoAnalyzer.analyze(anuncio_dict)
  ├── Trilha B: FotoAnalyzer.analyze(imagens)  [download + PIL + pyiqa se disponível]
  ├── Trilha C: ObjecoesAnalyzer.analyze(reviews_data, perguntas)
  └── Trilha D: ConcorrentesAnalyzer.analyze(anuncio_dict)

[SCORING — scorecard.py]
  └── Scorecard4Eixos.calculate(anuncio_dict)
      → health_pct, images_pct, specs_pct, reviews_pct, general_pct, tier

[PRODUTO INFO — inferir_produto_info()]
  └── Extrai material, cor, compatibilidade, kit da ficha técnica da API

[GERAÇÃO LLM — gerador.py]
  ├── gerar_titulo(titulo_atual, violacoes, produto_info)    → Sonnet
  ├── gerar_descricao(produto_info, objecoes, pontos_fortes) → Sonnet
  ├── gerar_prompts_imagem(produto_info, trilha_b)           → Sonnet
  └── gerar_prompts_video(produto_info, objecoes)            → Sonnet

[RELATÓRIO — orchestrator.print_relatorio()]
  └── 7 blocos estruturados no terminal (ASCII safe para Windows)

SAÍDA: Relatório completo em ~60-90 segundos
```

---

## 9. DECISÕES DE DESIGN CRÍTICAS

### 9.1 Perguntas valem 2x

**Decisão:** No agregador de objeções, cada pergunta é inserida duas vezes na lista do tema correspondente, e depois desduplicada ao calcular frequência.

**Raciocínio:** Uma pergunta feita antes da compra representa uma objeção ativa no funil de conversão. Se um comprador está digitando uma pergunta, ele está prestes a comprar mas algo o impede. Resolver essa dúvida na descrição pode capturar aquela venda. Uma review após a compra é importante, mas não é mais uma objeção — é feedback retroativo.

### 9.2 Reviews axis é dinâmico

**Decisão:** O eixo Reviews do scorecard é ignorado se o produto tiver menos de 5 reviews.

**Raciocínio:** Um produto novo com 2 reviews ruins não deve ser penalizado no scorecard geral — isso distorceria o diagnóstico. O eixo só é relevante quando há volume suficiente para ser estatisticamente significativo.

### 9.3 NPS usa distribuição global, não amostra

**Problema encontrado:** A API do ML retorna no máximo 5-50 reviews por página, mas o total pode ser 794. Se calcularmos NPS pela amostra e dividirmos pelo total, o resultado é distorcido (794 no denominador, 5 no numerador = NPS artificialmente próximo de zero).

**Decisão:** Usar o campo `rating_levels` da resposta, que contém a distribuição completa de todas as estrelas (all-time), não apenas da página retornada.

### 9.4 Frame occupation é aviso, não erro crítico

**Decisão:** A regra de "produto deve ocupar 95% do frame" é rebaixada para severidade "baixa" quando pyiqa não está disponível.

**Raciocínio:** Produtos longos ou estreitos (escapamentos, cabos, tubulações) naturalmente ocupam poucos pixels mesmo com enquadramento correto. Sem NIMA score para confirmar a qualidade, disparar MELHORAR para 9 fotos baseado só em contagem de pixels não-brancos gera ruído no plano de ação. Regras de enquadramento precisam ser calibradas por categoria.

### 9.5 Geração LLM é opcional

**Decisão:** A geração de conteúdo via Claude só roda se `ANTHROPIC_API_KEY` estiver configurada e `gerar_conteudo=True`.

**Raciocínio:** As 4 trilhas + scorecard têm valor por si sós, mesmo sem LLM. Isso permite usar o agente em contextos sem acesso à API da Anthropic, ou quando se quer apenas o diagnóstico rápido.

### 9.6 ASCII no terminal

**Decisão:** Todos os prints do relatório no terminal usam apenas ASCII. Caracteres Unicode (✔, ✗, ─, emojis) causam `UnicodeEncodeError` no terminal do Windows (cp1252). A saída LLM usa `sys.stdout.reconfigure(encoding="utf-8")`.

---

## 10. O QUE O PROJETO ENTREGA (RESUMO)

Para cada anúncio analisado, o NVS Agent entrega:

### Diagnóstico
- ✅ **Scorecard 4 Eixos** com nota por dimensão e nota geral com tier (excelente/bom/regular/crítico)
- ✅ **Alertas críticos** destacados (eixos abaixo de 60%)
- ✅ **Conformidade** com guidelines do ML (penalidade acumulada de violações)
- ✅ **NPS estimado** baseado na distribuição completa de estrelas

### Inteligência da Voz do Comprador
- ✅ **Objeções mapeadas** por tema, com frequência e intensidade
- ✅ **Fonte identificada** (pergunta pré-compra vs. review pós-compra)
- ✅ **Exemplos reais** transcritos dos compradores
- ✅ **Pontos fortes** confirmados pelos reviews
- ✅ **Tratativa específica** por canal para cada objeção

### Plano de Ação
- ✅ **Priorizado por impacto** (crítico → alto → médio → baixo)
- ✅ **Categorizado por área** (título / descrição / fotos / ficha / SEO / conteúdo)
- ✅ **Acionável imediatamente** — cada item tem problema e ação específicos

### Conteúdo Pronto
- ✅ **Título otimizado** (com contagem de caracteres, PI_FAKES corrigido)
- ✅ **Descrição completa** em 5 seções persuasivas, tratando objeções identificadas
- ✅ **8 prompts de imagem** para fotógrafo ou IA gerativa
- ✅ **5 prompts de vídeo** para editor ou IA generativa

---

## 11. VALIDAÇÃO CONTRA PLANILHA DE REFERÊNCIA

O projeto foi desenvolvido tomando como referência a planilha "NVS Diagnóstico de Anúncios — Mercado Livre" (Google Sheets, doc_id: `1sErL0fYCmYSHYG8gGH_8JZbWBiU8aov-tv4KlIaAblc`), que representa o padrão atual de diagnóstico manual da operação.

**Correspondência validada:**

| Planilha NVS Diagnóstico | NVS Agent |
|---|---|
| IMAGE HEALTH (%) | `scorecard.images_pct` |
| SPECS HEALTH (%) | `scorecard.specs_pct` |
| GENERAL HEALTH (%) | `scorecard.health_pct` |
| GENERAL REVIEWS (%) | `scorecard.reviews_pct` |
| EXPERIENCE | `scorecard.experience_pct` |
| STATUS (Pausado/Ativado) | `infracoes_ativas` |
| FICHA TÉCNICA (Obrig/Relev/Comum/Oculto) | `atributos_faltando` |
| TOTAL IMAGENS (Excelentes/Boas/Medianas/Ruins) | `qualidade_tag` por foto |
| AÇÃO RECOMENDADA | `plano_de_acao` (Bloco 3) |

---

## 12. STACK TÉCNICA

| Componente | Tecnologia | Função |
|---|---|---|
| Linguagem | Python 3.13 | Core do sistema |
| API principal | Mercado Livre API v2 | Coleta de dados do anúncio |
| LLM | Anthropic Claude (Haiku + Sonnet) | Geração de conteúdo |
| Análise de imagem | PIL/Pillow | Resolução, fundo branco, frame |
| Qualidade de foto | pyiqa + NIMA (opcional) | Score estético 0-10 |
| Remoção de fundo | rembg[cpu] (opcional) | Detecção de fundo branco |
| Clustering avançado | BERTopic (roadmap) | Agrupamento semântico de objeções |
| HTTP | requests | Chamadas à API |
| Armazenamento | .env + dataclasses | Config e estrutura de dados |

---

## 13. LIMITAÇÕES ATUAIS E OPORTUNIDADES DE MELHORIA

### Limitações conhecidas

1. **Frame occupation sem calibração por categoria**
   - Produtos longos/estreitos (escapamentos, cabos) têm % de ocupação naturalmente baixa
   - Regra atual é genérica; ideal seria ajustar limiar por categoria de produto

2. **Review texts com volume limitado**
   - A API do ML retorna no máximo 5-50 textos de reviews por chamada
   - A distribuição de estrelas (`rating_levels`) é global, mas os textos são amostrais
   - Análise de sentimento dos reviews fica limitada ao que a API expõe

3. **Detecção de temas por keywords**
   - O sistema atual usa matching por palavras-chave (determinístico)
   - Pode ter falsos positivos (palavra-chave presente em contexto irrelevante)
   - BERTopic (clustering semântico) seria mais preciso mas requer mais setup

4. **Token de acesso ML expira em 6h**
   - OAuth 2.0 do ML tem access_token com validade curta
   - Refresh automático não está implementado — operação manual para renovar
   - Em produção seria necessário job automático de refresh

5. **Análise de concorrentes superficial**
   - Trilha D atual compara apenas keywords no título
   - Análise mais profunda (preço, fotos, reviews) requer mais chamadas à API

6. **Sem exportação .xlsx**
   - O relatório atual é texto no terminal
   - Integração com a planilha NVS Diagnóstico (Google Sheets ou .xlsx) está no roadmap

### Oportunidades de evolução

1. **Interface web** — painel onde o vendedor cola o MLB ID e vê o relatório formatado
2. **Processamento em lote** — analisar catálogo inteiro de uma vez, priorizar os piores
3. **Histórico e trending** — rastrear evolução do scorecard ao longo do tempo
4. **Fine-tuning por categoria** — regras específicas para motos, eletrodomésticos, moda, etc.
5. **Integração com ferramentas de criação** — enviar prompts direto para Midjourney/Sora via API
6. **Resposta automática de perguntas** — usar a resposta_padrao gerada para responder automaticamente perguntas dos compradores via API ML
7. **Alertas proativos** — monitorar scorecard e notificar quando algum eixo cair abaixo do limite

---

## 14. COMO RODAR

### Pré-requisitos
```bash
pip install requests Pillow anthropic
# Opcional (análise avançada de fotos):
pip install torch torchvision  # CPU only
pip install pyiqa rembg[cpu]
```

### Configurar credenciais
```
# .env na raiz do projeto
ANTHROPIC_API_KEY=sk-ant-api03-...
ML_ACCESS_TOKEN=APP_USR-...
```

### Executar
```bash
python -m src.main MLB3661846735
```

### Apenas diagnóstico (sem geração LLM)
```python
orchestrator = NVSOrchestrator(access_token=token)
result = orchestrator.run(mlb_id, gerar_conteudo=False)
orchestrator.print_relatorio(result)
```

---

## 15. RESULTADO DO TESTE DE VALIDAÇÃO

**Anúncio testado:** MLB3661846735 — Escapamento Polimet Estralador CG 160

| Métrica | Resultado |
|---|---|
| Scorecard Geral | 79.2% [BOM] |
| Saúde ML | 87% |
| Reviews | 92.8% (NPS 94%) |
| Imagens PQT | 50% ⚠️ |
| Objeção #1 | COMPATIBILIDADE — 20% dos buyers, 10 perguntas pré-compra |
| Objeção #2 | CONTEUDO_KIT — 4% dos buyers, 2 perguntas pré-compra |
| Exemplo real | "Bom dia, tenho uma fan 160 2025, esse escape serve perfeitamente ou pega no pedal de freio traseiro?" |
| Plano de ação | 3 itens concretos (2 de conteúdo + 1 de descrição) |
| Tempo de execução | ~75 segundos |

---

*NVS Agent — NØR Group / Novaes*  
*Desenvolvido com Claude Code + Anthropic API*
