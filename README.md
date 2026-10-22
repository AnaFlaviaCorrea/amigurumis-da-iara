# Amigurumis da Iara

Site institucional e loja virtual desenvolvidos com Django.

## Executar o projeto

```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

No Linux ou macOS, ative o ambiente com `source venv/bin/activate`.

## Cadastrar produtos

1. Acesse `http://127.0.0.1:8000/admin/`.
2. Cadastre primeiro as categorias da loja.
3. Cadastre os produtos e selecione “Pronta entrega” ou “Sob encomenda”.
4. Para pronta entrega, informe o estoque.
5. Para encomendas, informe o prazo de produção em dias.
6. Use as imagens adicionais para criar a galeria da página do produto.

O catálogo fica disponível em `http://127.0.0.1:8000/loja/`.

## Carrinho

O carrinho funciona por sessão: o visitante pode adicionar produtos, alterar
quantidades e remover itens sem criar uma conta. Para peças à pronta entrega,
o sistema impede quantidades superiores ao estoque cadastrado.

O carrinho fica disponível em `http://127.0.0.1:8000/loja/carrinho/`.

## Importar as imagens do portfólio

Para transformar as imagens de `static/img/portfolio/` em rascunhos de produtos:

```bash
python manage.py import_portfolio_products
```

Antes de importar, é possível conferir o que o comando fará:

```bash
python manage.py import_portfolio_products --dry-run
```

O comando cria as categorias a partir das pastas, copia as imagens para
`media/products/` e cadastra os produtos como inativos e sem preço. Complete
as informações no Admin antes de ativá-los. Imagens já importadas são ignoradas;
arquivos novos são cadastrados; imagens substituídas são atualizadas; e uma
imagem apenas renomeada não gera produto duplicado.

## Finalização e pagamento do pedido

O cliente pode avançar do carrinho para o checkout sem criar uma conta. Depois
de informar os dados de contato e escolher entrega ou retirada, o sistema cria
o pedido e abre o Payment Brick do Mercado Pago dentro da loja.

Pedidos para retirada podem ser pagos imediatamente. Pedidos com entrega ficam
bloqueados até o frete ser calculado, evitando cobrar um total incorreto.

### Configurar o Mercado Pago em modo de teste

1. Crie uma aplicação no painel **Suas integrações** do Mercado Pago.
2. Copie `.env.example` para um novo arquivo chamado `.env`.
3. Preencha no `.env` a Public Key e o Access Token de **teste**.
4. Nunca envie o `.env` para o GitHub; ele já está listado no `.gitignore`.
5. Instale as dependências e aplique as migrações:

```bash
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

O fluxo aceita cartão, Pix e boleto conforme a disponibilidade da conta. Cada
tentativa usa uma chave de idempotência própria para evitar cobrança duplicada.
O Webhook deverá apontar para `/loja/webhooks/mercado-pago/` quando o site tiver
um endereço HTTPS público. Em ambiente local, essa URL não é acessível pelo
Mercado Pago.

Landing Page desenvolvida em Django para divulgação de cursos presenciais de Pet Realista em Crochê.

## Tecnologias

- Python
- Django
- Bootstrap 5
- HTML5
- CSS3
- JavaScript

Projeto desenvolvido para estudo e uso comercial.
