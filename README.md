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

## Finalização do pedido

O cliente pode avançar do carrinho para a tela de checkout sem criar uma conta.
Nela, informa os dados de contato e escolhe entre receber no endereço ou retirar
com a Iara. O sistema cria o pedido e seus itens como “aguardando pagamento”.
O cálculo do frete e a cobrança serão integrados nas próximas etapas.

Landing Page desenvolvida em Django para divulgação de cursos presenciais de Pet Realista em Crochê.

## Tecnologias

- Python
- Django
- Bootstrap 5
- HTML5
- CSS3
- JavaScript

Projeto desenvolvido para estudo e uso comercial.
