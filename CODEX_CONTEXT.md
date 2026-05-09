# Remaz Pharm - Contexto do Projeto

Atualizado em: 2026-05-09

## Visao geral

Projeto Django 6 para um marketplace/farmacia online chamado Remaz Pharm. O app principal e `core`; as telas ficam em `templates/`; os assets em `static/`; uploads locais em `media/`.

O fluxo atual cobre:

- Cadastro/login de clientes por email ou CPF.
- Dashboard de produtos disponiveis por estoque de farmacias parceiras.
- Carrinho por usuario.
- Checkout com agrupamento de pedidos por farmacia.
- Upload de receita em PDF para medicamentos de tarja preta.
- Area da farmacia para gerenciar estoque e atualizar pedidos.
- Area administrativa de farmacia/admins com indicadores por farmacia, atalhos de estoque, pedidos e receitas.
- Controle de promocoes por item de estoque da farmacia.
- Analise de receitas com aprovacao ou recusa motivada.
- Admin Django com upload de imagens de medicamentos para Supabase Storage.

## Stack e configuracao

- Python/Django: `Django==6.0.4`.
- Banco configurado por variaveis em `.env` via `python-dotenv`.
- Supabase Storage usado em `core/services/supabase_storage.py`.
- CSS principal do dashboard/fluxos novos: `static/css/dashboard.css`.
- O arquivo `.env` existe, mas nao foi lido durante esta analise para evitar expor segredos.

## Modelos principais

- `UserProfile`: perfil do usuario com CPF e apelido.
- `Category`: categoria de medicamento/produto.
- `Medicine`: produto base, preco, imagem URL, categoria e tarja.
- `Pharmacy`: farmacia parceira e dono responsavel.
- `PharmacyInventory`: preco/estoque por farmacia e medicamento.
- `PharmacyInventory` tambem guarda promocao ativa, titulo, descricao e preco promocional. Se o estoque chega a zero, o item fica indisponivel automaticamente no `save()`.
- `Cart` e `CartItem`: carrinho do usuario, com item vinculado ao estoque de uma farmacia.
- `Order` e `OrderItem`: pedido finalizado, dados de entrega, pagamento, farmacia, status, itens e revisao de receita.

## Rotas importantes

- `/dashboard/`: catalogo com busca e filtros.
- `/carrinho/`: carrinho.
- `/receita-digital/`: upload de receita.
- `/concluir-pedido/`: checkout.
- `/pedidos/`: pedidos do cliente.
- `/farmacia/`: area da farmacia.
- `/farmacia/<id>/estoque/`: gestao de estoque.
- `/farmacia/<id>/pedidos/`: gestao de pedidos da farmacia.
- `/farmacia/<id>/receitas/`: aprovacao/recusa de receitas com motivo.

## Verificacoes executadas

- `python manage.py check`: sem issues.
- `python manage.py test`: 0 testes encontrados.
- `python manage.py makemigrations --check --dry-run`: sem mudancas pendentes.
- `python manage.py check` apos alteracoes de farmacia/receitas/promocoes: sem issues.
- `python manage.py test` apos alteracoes: 0 testes encontrados.

## Estado git observado

Ha alteracoes nao commitadas em:

- `core/admin.py`
- `core/models.py`
- `core/urls.py`
- `core/views.py`
- `static/css/dashboard.css`
- `templates/dashboard.html`

E arquivos novos nao rastreados:

- migracoes `0005` e `0006`
- telas de carrinho, checkout, pedidos, area da farmacia, estoque, pedidos da farmacia e receita digital

## Pontos de atencao

- `ALLOWED_HOSTS = ['*']` quando `DEBUG=False`; restringir antes de producao.
- Fallback de `SECRET_KEY` em settings; em producao deve falhar se a variavel estiver ausente.
- `LANGUAGE_CODE` e `TIME_ZONE` ainda estao em `en-us`/`UTC`; para o produto brasileiro, usar `pt-br` e fuso local adequado.
- O carrinho aumenta quantidade de itens com estoque vinculado pela rota `add_inventory_to_cart(inventory_id)`, preservando a farmacia selecionada.
- Checkout captura campos de cartao no HTML, mas a view nao processa esses dados; evitar coletar dados sensiveis sem gateway PCI/compliance.
- Upload de receita e salvo localmente em `media/prescriptions`; pensar em acesso protegido e armazenamento privado.
- A logica de checkout reduz estoque, mas vale adicionar validações/testes para concorrencia e estoque negativo.
- O projeto nao tem testes automatizados ainda.

## Sugestoes priorizadas

### Curto prazo

- Expandir testes automatizados para o incremento do carrinho por farmacia/estoque.
- Remover ou ocultar campos de cartao ate integrar um gateway real.
- Criar forms Django para cadastro, login, estoque e checkout em vez de ler `request.POST` diretamente.
- Adicionar testes para carrinho, checkout, receita obrigatoria e permissao da area da farmacia.
- Ajustar settings de localizacao para Brasil.

### Medio prazo

- Adicionar enderecos salvos do cliente.
- Calcular frete/prazo por farmacia e metodo de entrega.
- Criar historico de status do pedido.
- Implementar notificacoes por email/WhatsApp para status do pedido.
- Fluxo de aprovacao/recusa de receita com motivo estruturado criado em `/farmacia/<id>/receitas/`.
- Melhorar dashboard da farmacia com graficos de vendas e alertas de estoque baixo.

### Longo prazo

- Integrar gateway de pagamento.
- Geolocalizar farmacias e mostrar disponibilidade por proximidade.
- Criar sistema de cupons/promocoes.
- Adicionar API REST para app mobile ou integrações.
- Implementar auditoria LGPD para dados pessoais e receitas.
