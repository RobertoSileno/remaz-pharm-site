# Remaz Pharm - Contexto do Projeto

Atualizado em: 2026-05-24

## Visao geral

Projeto Django 6 para um marketplace/farmacia online chamado Remaz Pharm. O app principal e `core`; as telas ficam em `templates/`; os assets em `static/`; uploads publicos locais em `media/`; receitas protegidas em `media_private/`.

O fluxo atual cobre:

- Cadastro/login de clientes por email ou CPF.
- Dashboard de produtos disponiveis por estoque de farmacias parceiras.
- Carrinho por usuario, vinculado ao estoque de uma farmacia especifica.
- Checkout com agrupamento de pedidos por farmacia.
- Enderecos salvos do cliente com preenchimento de CEP no perfil e checkout.
- Upload de receita em PDF para medicamentos de tarja preta.
- Download protegido de receitas por cliente ou farmacia responsavel.
- Area da farmacia para gerenciar estoque, promocoes, pedidos e receitas.
- Cadastro de farmacia por usuario logado com CNPJ, telefone e endereco.
- Cadastro/login separado de farmacia, com CNPJ normalizado e logomarca enviada ao Supabase.
- Cadastro de novos medicamentos/produtos diretamente pela area de estoque da farmacia, com upload de imagem para Supabase.
- Historico de status de pedidos.
- Transacao Pix via Mercado Pago quando `MERCADO_PAGO_ACCESS_TOKEN` esta configurado.
- Admin Django com upload de imagens de medicamentos para Supabase Storage.
- API mobile exclusiva para clientes: autenticacao, catalogo, carrinho, enderecos, checkout e pedidos.
- Catalogo mobile sincronizado ao layout novo do site, com filtros de categoria/tarja e logomarca da farmacia.

## Stack e configuracao

- Python/Django: `Django==6.0.4`.
- Banco configurado por variaveis em `.env` via `python-dotenv`.
- `load_dotenv(..., override=True)` permite que o `.env` local prevaleca durante desenvolvimento.
- Supabase Storage usado em `core/services/supabase_storage.py`.
- Mercado Pago Pix configuravel em `core/services/mercado_pago.py` via `MERCADO_PAGO_ACCESS_TOKEN`.
- CSS principal do dashboard/fluxos novos: `static/css/dashboard.css`.
- CSS especifico do perfil: `static/css/profile.css`.

## Modelos principais

- `UserProfile`: perfil do usuario com CPF, apelido e metadados legados de pagamento sem armazenamento de numero/CVV.
- `Address`: enderecos salvos por cliente.
- `Category`: categoria de medicamento/produto.
- `Medicine`: produto base, preco, imagem URL, categoria e tarja.
- `Pharmacy`: farmacia parceira, dono responsavel e logomarca.
- `PharmacyInventory`: preco/estoque por farmacia e medicamento, incluindo promocoes.
- `Cart` e `CartItem`: carrinho do usuario, com item vinculado ao estoque.
- `Order` e `OrderItem`: pedido finalizado, dados de entrega, pagamento, farmacia, status, itens e revisao de receita.
- `OrderStatusHistory`: historico de transicoes de status do pedido.
- `PaymentTransaction`: transacao de pagamento, incluindo Pix Mercado Pago e pagamentos manuais.
- `MobileAuthToken`: token revogavel do aplicativo, persistido apenas como hash.

## Rotas importantes

- `/dashboard/`: catalogo com busca e filtros.
- `/carrinho/`: carrinho.
- `/receita-digital/`: upload de receita.
- `/receitas/<order_id>/arquivo/`: download protegido da receita.
- `/concluir-pedido/`: checkout.
- `/pedidos/`: pedidos do cliente.
- `/perfil/`: perfil e enderecos salvos.
- `/api/health/`: verificacao de conectividade da API com o banco configurado.
- `/api/auth/*`, `/api/catalog/`, `/api/cart/`, `/api/addresses/`, `/api/checkout/` e `/api/orders/`: jornada do cliente mobile.
- `/farmacia/`: area da farmacia.
- `/farmacia/cadastro/`: cadastro de farmacia.
- `/farmacia/<id>/estoque/`: gestao de estoque.
- Em `/farmacia/<id>/estoque/`, a farmacia pode adicionar produto existente ao estoque ou cadastrar um produto novo e ja criar seu estoque.
- O cadastro/edicao de produto pela farmacia usa upload multipart com campo `image_file` e `upload_image()` para enviar PNG/JPEG/WebP ao bucket Supabase e salvar a URL em `Medicine.image`.
- `/farmacia/<id>/pedidos/`: gestao de pedidos da farmacia.
- `/farmacia/<id>/receitas/`: aprovacao/recusa de receitas.

## Regras importantes

- A loja mostra apenas estoque de farmacias ativas com dono responsavel vinculado.
- A farmacia padrao legada `Remaz Pharm` sem dono foi desativada pela migracao `0011` para evitar estoque fantasma.
- Se o estoque chega a zero, `PharmacyInventory.save()` bloqueia automaticamente o item.
- O checkout reduz estoque dentro de transacao atomica e usa `select_for_update()` ao debitar.
- Campos de cartao estao ocultos/desabilitados ate haver gateway tokenizado.
- O app mobile nao recebe credenciais Supabase; ele usa token Bearer revogavel para acessar o Django.
- A API valida PDF de receita no backend, limita tentativas de login e repete as regras de estoque elegivel do site.
- Contas de farmacia nao autenticam na API cliente do aplicativo.
- Pix e dinheiro sao os unicos pagamentos aceitos no checkout ate haver gateway tokenizado para cartoes.
- `media_private/` e ignorado pelo Git; receitas protegidas nao devem entrar no repositorio.

## Verificacoes executadas

- `.venv\Scripts\python.exe manage.py check`: sem issues.
- `.venv\Scripts\python.exe manage.py makemigrations --check --dry-run`: sem mudancas pendentes.
- `$env:DJANGO_TEST_SQLITE='True'; .venv\Scripts\python.exe manage.py test core`: 13 testes aprovados em SQLite isolado.
- `.venv\Scripts\python.exe manage.py migrate core`: ambas as migracoes `0012` e a juncao `0013` aplicadas no banco Supabase configurado.
- Servidor local validado com Supabase: `/api/health/` retornou banco conectado e `/static/css/dashboard.css` retornou HTTP 200.
- Runserver local nao esta ativo na porta 8000.
- Mobile: TypeScript/lint aprovados, `expo-doctor` aprovado em 18/18 checks e bundle Android Hermes gerado apos sincronizacao visual.

## Estado git observado

- O pull de `origin/main` trouxe o novo layout/fluxo de farmacia e foi conciliado localmente com a API mobile.
- O conflito em `core/views.py` foi resolvido preservando seguranca, checkout e recursos recebidos.
- A resolucao fica pronta para commit de merge apos revisao do usuario; nao criar commits com receitas privadas.
- O app mobile possui ajustes locais em catalogo/filtros/logomarca para acompanhar o site atualizado.

## Pontos de atencao

- Em producao, configurar `ALLOWED_HOSTS`, chave secreta forte e flags HTTPS/cookies/HSTS no `.env`.
- Pix Mercado Pago cria transacao, mas ainda falta webhook para confirmar pagamento automaticamente.
- Receitas ja usam rota protegida e foram removidas do versionamento local; arquivos ja publicados em historico remoto devem ser tratados como possivel exposicao e exigem decisao de limpeza/LGPD.
- A logica de checkout ainda deve ganhar testes adicionais de concorrencia simultanea e permissoes operacionais da farmacia.
- Placeholders quebrados que apontavam para assets ausentes foram substituidos por icones vetoriais do estilo existente.

## Sugestoes priorizadas

### Curto prazo

- Expandir testes para concorrencia, webhook e permissoes da farmacia.
- Criar webhook Mercado Pago para atualizar `PaymentTransaction` e `Order`.
- Corrigir/adicionar assets faltantes.
- Validar formularios com forms Django nos fluxos que ainda usam `request.POST` direto.

### Medio prazo

- Calcular frete/prazo por farmacia e metodo de entrega.
- Implementar notificacoes por email/WhatsApp para status do pedido.
- Melhorar dashboard da farmacia com graficos de vendas e alertas de estoque baixo.
- Criar tela de detalhes do pedido para cliente e farmacia.

### Longo prazo

- Evoluir gateway de pagamento com webhooks, conciliacao, cancelamento e reembolso.
- Geolocalizar farmacias e mostrar disponibilidade por proximidade.
- Criar sistema de cupons/promocoes.
- Implementar auditoria LGPD para dados pessoais e receitas.
