# Revisora Editorial RCA — protótipo de skill

Este pacote contém instruções executáveis por um agente com acesso ao artigo e à pesquisa web. O agente deve executar uma revisão verificável e retornar um relatório; não pode aprovar sem conferir fontes.

## Como usar

1. Executar a Social com a skill `revisora-editorial-rca` e acesso ao artigo corrente via MCP RCA (`blog_ver`).
2. A Social deve pesquisar/abrir fontes externas e consultar catálogo/serviços internos para claims comerciais.
3. A skill devolve `BLOQUEADO`, `AJUSTES` ou `APROVADO PELA REVISORA`, com fatos e fontes verificáveis.
4. Encaminhar a versão aprovada pela revisora para **Fábio/Fabi**. Só depois da aprovação humana atualizar/publicar no site.

## O que falta para automatizar no GitHub

- Um endpoint no Admin RCA para ler a versão atual do artigo e registrar `versao`, `revisado_em`, `resultado`, `achados` e links de evidência.
- Um executor da revisão com capacidade real de pesquisar e ler fontes externas. GitHub Actions puro consegue lint, links e formatação, mas não garante veracidade jornalística.
- Um workflow disparado na criação/edição de artigos, independente da `revisora.py` (que revê artes).
- Uma trava no Admin impedindo mudança para publicação enquanto não existir aprovação técnica da mesma versão do artigo e, depois, aprovação da diretoria.
- Tratar atualização de artigo como invalidação automática de revisão anterior.
- Nunca incluir tokens, chaves ou acesso autenticado em artefatos públicos.

## Teste piloto

Aplicar ao artigo RCA `#53` sobre phishing e Microsoft. Verificar cronologia, fontes, riscos, distinção Outlook/Exchange/webmail RCA, SEO e CTA. O teste só é concluído quando houver relatório de checagem e revisão humana.

Esta é a primeira versão para avaliação, não um fluxo de GitHub instalado.