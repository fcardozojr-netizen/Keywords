# Keyword Master — Odonto Master

Aplicação web privada para descoberta e organização de palavras-chave com Google Ads API.

## O que já está implementado

- Login de administrador com sessão assinada.
- Geração de ideias a partir de palavras-chave, URL ou combinação de ambos.
- Segmentação por localização e idioma.
- Métricas históricas: buscas médias mensais, concorrência, índice e estimativas de lances/CPC.
- Ordenação, filtros e indicadores de resumo.
- Agrupamento inicial por intenção e sugestões de negativas (heurísticas revisáveis).
- Exportação CSV compatível com Excel.
- Dockerfile e Blueprint para deploy no Render.

## Requisitos Google Ads

A conta Google Ads existente não é suficiente, sozinha, para autenticar a API. É necessário configurar:
1. Projeto no Google Cloud e OAuth Client ID/Secret.
2. Developer Token com nível de acesso que permita Keyword Planning.
3. Refresh Token OAuth com escopo `https://www.googleapis.com/auth/adwords`.
4. Customer ID da conta Google Ads (10 dígitos, sem hífen).
5. Se a conta for acessada por uma conta de administrador (MCC), informar `GOOGLE_ADS_LOGIN_CUSTOMER_ID`.

A API usa o `KeywordPlanIdeaService.GenerateKeywordIdeas`. Os IDs iniciais no formulário são Brasil `2076` e idioma português `1014`; valide os alvos geográficos/idiomas conforme o mercado pretendido antes de campanhas regionais.

## Rodar localmente

```bash
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate
pip install -r requirements.txt
copy .env.example .env  # Windows; no macOS/Linux: cp .env.example .env
```

Preencha `.env` e carregue as variáveis no terminal. No Windows PowerShell, pode usar `$env:NOME="valor"` para cada variável.

```bash
uvicorn app.main:app --reload
```

Abra `http://127.0.0.1:8000`.

## Publicar no GitHub e Render

1. Crie um repositório privado no GitHub.
2. Envie o conteúdo desta pasta (não envie `.env`).
3. No Render, selecione **New > Blueprint** e conecte o repositório.
4. Revise o serviço e preencha todos os campos `sync: false`.
5. Faça o deploy. O Render disponibilizará uma URL `onrender.com`.

O plano `starter` no `render.yaml` é uma configuração inicial paga. Para testar, pode trocar para `free` se estiver disponível para o tipo de serviço e aceitar as limitações de disponibilidade do plano gratuito.

## Segurança

- Nunca coloque tokens, senhas ou `.env` no GitHub.
- Restrinja o repositório e o painel Render à sua conta.
- Use uma senha administrativa forte.
- Ative MFA no Google e GitHub.
- Rotacione credenciais se forem expostas.

## Limitações / próxima evolução

- A análise de intenção e negativas nesta primeira versão é heurística e deve ser revisada antes de usar em campanhas.
- O campo OpenAI está reservado para uma etapa futura de classificação semântica; não há chamada de IA ativa nesta versão.
- O CSV exporta as palavras-chave. A próxima iteração pode adicionar XLSX com todas as métricas, histórico de consultas, páginas de campanha, previsões e agrupamento semântico.
- A API do Google pode retornar poucos resultados ou erro conforme permissões, faturamento, limites, segmentação e elegibilidade da conta.

## Verificação

Acesse `/api/health` para conferir se a aplicação está ativa e se as credenciais Google Ads foram detectadas (sem revelar valores).
