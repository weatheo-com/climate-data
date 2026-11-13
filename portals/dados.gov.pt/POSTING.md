# Publicar em dados.gov.pt (lista para o titular)

1. Criar conta em https://dados.gov.pt e confirmar o e-mail.
2. Criar a organização "Weatheo (by CODELIO)" com o texto de ORG.md (aguardar eventual validação do portal). Anotar o id da organização (URL ou API: /api/1/organizations/).
3. Perfil > Chave API: gerar e exportar `export UDATA_API_KEY=...` (nunca no repositório).
4. Os ficheiros do release v1.0.0 têm de estar publicados no GitHub antes.
5. Simulação (nada é enviado), a partir da raiz do repositório:

   python3 scripts/publish_udata.py --base https://dados.gov.pt --meta portals/dados.gov.pt/PT-A.json --org <ORG_ID> --lookup
   python3 scripts/publish_udata.py --base https://dados.gov.pt --meta portals/dados.gov.pt/PT-B.json --org <ORG_ID> --lookup

6. Publicar:

   python3 scripts/publish_udata.py --base https://dados.gov.pt --meta portals/dados.gov.pt/PT-A.json --org <ORG_ID> --apply
   python3 scripts/publish_udata.py --base https://dados.gov.pt --meta portals/dados.gov.pt/PT-B.json --org <ORG_ID> --apply

7. Cobertura espacial: o script envia o campo "spatial" (granularidade "Concelho" (pt:concelho), zona "Portugal" (country:pt)); verificar na página de cada conjunto de dados e, se faltar, defini-la na interface. Verificados na API em 2026-11-13: licença `cc-by`, frequência `irregular`.
8. Sem entrada em "Reutilizações".
