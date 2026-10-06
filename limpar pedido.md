# Limpar pedidos (e vendas) de um tenant

Instruções para zerar o painel de vendas de um cliente white label **sem** apagar configurações, catálogo, produtos, categorias etc.

## Escopo

### Apagar (só vendas do tenant)

- pedidos + filhos (`order_items`, options, components, status history, payments)
- clientes + endereços
- opcional: `message_dispatches` e `merchant_alerts` (histórico de avisos de pedido)

### Manter

- empresa, settings, tema, horários
- catálogo (produtos, categorias, opções)
- funcionários, papéis
- conexões/templates de comunicação (config)

## No servidor (produção)

```bash
ssh -i ~/.ssh/id_ed25519_hostinger root@IP_DA_VPS
cd /opt/foodservice/vendas_backend

COMPOSE="docker compose -f deploy/docker-compose.prod.yml --env-file .env.production"
$COMPOSE exec api python manage.py shell
```

Dentro do shell:

```python
from apps.companies.models import Company
from apps.orders.models import Order
from apps.customers.models import Customer
from apps.communications.models import MessageDispatch, MerchantAlert

tenant = Company.objects.get(subdomain="jequipizza")  # confere o subdomain!

# preview
print("orders", Order.objects.filter(tenant=tenant).count())
print("customers", Customer.objects.filter(tenant=tenant).count())

# limpa vendas (filhos do pedido vão no CASCADE)
Order.objects.filter(tenant=tenant).delete()
Customer.objects.filter(tenant=tenant).delete()  # endereços vão no CASCADE

# opcional: histórico de mensagens/alertas
MessageDispatch.objects.filter(tenant=tenant).delete()
MerchantAlert.objects.filter(tenant=tenant).delete()

print("ok — orders", Order.objects.filter(tenant=tenant).count(),
      "customers", Customer.objects.filter(tenant=tenant).count())
```

Troque `jequipizza` se for outro subdomain. Confira os counts do preview antes do `delete`.

## Observações

- O filtro por `tenant` isola o cliente do resto da plataforma.
- Pedidos usam `CASCADE` nos filhos — não precisa apagar `order_items` etc. na mão.
- Clientes usam soft delete no model; se ainda aparecerem no painel, use hard delete:

```python
Customer.all_objects.filter(tenant=tenant).delete()
```
