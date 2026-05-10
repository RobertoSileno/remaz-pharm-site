# Remaz Pharm - Contexto do Projeto

Atualizado em: 2026-05-10

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
- Historico de status de pedidos.
- Transacao Pix via Mercado Pago quando `MERCADO_PAGO_ACCESS_TOKEN` esta configurado.
- Admin Django com upload de imagens de medicamentos para Supabase Storage.

## Stack e configuracao

- Python/Django: `Django==6.0.4`.
- Banco configurado por variaveis em `.env` via `python-dotenv`.
- `load_dotenv(..., override=True)` permite que o `.env` local prevaleca durante desenvolvimento.
- Supabase Storage usado em `core/services/supabase_storage.py`.
- Mercado Pago Pix configuravel em `core/services/mercado_pago.py` via `MERCADO_PAGO_ACCESS_TOKEN`.
- CSS principal do dashboard/fluxos novos: `static/css/dashboard.css`.
- CSS especifico do perfil: `static/css/profile.css`.

## Modelos principais

- `UserProfile`: perfil do usuario com CPF e apelido.
- `Address`: enderecos salvos por cliente.
- `Category`: categoria de medicamento/produto.
- `Medicine`: produto base, preco, imagem URL, categoria e tarja.
- `Pharmacy`: farmacia parceira e dono responsavel.
- `PharmacyInventory`: preco/estoque por farmacia e medicamento, incluindo promocoes.
- `Cart` e `CartItem`: carrinho do usuario, com item vinculado ao estoque.
- `Order` e `OrderItem`: pedido finalizado, dados de entrega, pagamento, farmacia, status, itens e revisao de receita.
- `OrderStatusHistory`: historico de transicoes de status do pedido.
- `PaymentTransaction`: transacao de pagamento, incluindo Pix Mercado Pago e pagamentos manuais.

## Rotas importantes

- `/dashboard/`: catalogo com busca e filtros.
- `/carrinho/`: carrinho.
- `/receita-digital/`: upload de receita.
- `/receitas/<order_id>/arquivo/`: download protegido da receita.
- `/concluir-pedido/`: checkout.
- `/pedidos/`: pedidos do cliente.
- `/perfil/`: perfil e enderecos salvos.
- `/farmacia/`: area da farmacia.
- `/farmacia/cadastro/`: cadastro de farmacia.
- `/farmacia/<id>/estoque/`: gestao de estoque.
- `/farmacia/<id>/pedidos/`: gestao de pedidos da farmacia.
- `/farmacia/<id>/receitas/`: aprovacao/recusa de receitas.

## Regras importantes

- A loja mostra apenas estoque de farmacias ativas com dono responsavel vinculado.
- A farmacia padrao legada `Remaz Pharm` sem dono foi desativada pela migracao `0011` para evitar estoque fantasma.
- Se o estoque chega a zero, `PharmacyInventory.save()` bloqueia automaticamente o item.
- O checkout reduz estoque dentro de transacao atomica e usa `select_for_update()` ao debitar.
- Campos de cartao estao ocultos/desabilitados ate haver gateway tokenizado.

## Verificacoes executadas

- `.venv\Scripts\python.exe manage.py check`: sem issues.
- `.venv\Scripts\python.exe manage.py makemigrations --check --dry-run`: sem mudancas pendentes.
- `.venv\Scripts\python.exe manage.py test`: 0 testes encontrados.
- `.venv\Scripts\python.exe manage.py migrate`: migracoes ate `0011` aplicadas no banco local.
- Runserver local foi encerrado apos os testes.

## Estado git observado

Ha alteracoes nao commitadas em:

- `CODEX_CONTEXT.md`
- `core/admin.py`
- `core/forms.py`
- `core/models.py`
- `core/urls.py`
- `core/views.py`
- `setup/settings.py`
- `static/css/profile.css`
- templates de checkout, pedidos, pagamento, farmacia, receitas e perfil

Arquivos novos nao rastreados:

- `core/migrations/0008_address_orderstatushistory_paymenttransaction.py`
- `core/migrations/0009_pharmacy_cep.py`
- `core/migrations/0010_alter_paymenttransaction_status.py`
- `core/migrations/0011_deactivate_legacy_default_pharmacy.py`
- `core/services/mercado_pago.py`
- `templates/pharmacy_register.html`

## Pontos de atencao

- `ALLOWED_HOSTS = ['*']` quando `DEBUG=False`; restringir antes de producao.
- Fallback de `SECRET_KEY` em settings; em producao deve falhar se a variavel estiver ausente.
- `LANGUAGE_CODE` e `TIME_ZONE` ainda estao em `en-us`/`UTC`; para o produto brasileiro, usar `pt-br` e fuso local adequado.
- Pix Mercado Pago cria transacao, mas ainda falta webhook para confirmar pagamento automaticamente.
- Receitas ja usam rota protegida, mas ainda falta politica de retencao/auditoria LGPD.
- A logica de checkout deve ganhar testes de concorrencia e estoque negativo.
- O projeto ainda nao tem testes automatizados.
- Faltam assets referenciados em templates: `static/img/medicamento.png`, `icon1.png` a `icon4.png`, `benef1.png` a `benef5.png`.

## Sugestoes priorizadas

### Curto prazo

- Criar testes para carrinho, checkout, bloqueio de estoque, receita obrigatoria e permissoes da farmacia.
- Criar webhook Mercado Pago para atualizar `PaymentTransaction` e `Order`.
- Corrigir/adicionar assets faltantes.
- Ajustar settings de localizacao para Brasil.
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
- Adicionar API REST para app mobile ou integracoes.
- Implementar auditoria LGPD para dados pessoais e receitas.
