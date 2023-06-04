import yaml
from django.core.management.base import BaseCommand
from procurement_supply.models import Category, Stock, Supplier


class Command(BaseCommand):
    """
        Класс для организации управления командой export_goods.
    """
    def add_arguments(self, parser):
        """
        Точка входа для подклассифицированных команд для добавления пользовательских аргументов.
        """
        pass

    def handle(self, *args, **options):
        """
        Метод для описания фактической логики команды export_goods
        """

        result = {'categories': [],
                  'shop': [],
                  'goods': []}
        for category in Category.objects.all():
            result['categories'].append({'id': category.id, 'name': category.name})
        for supplier in Supplier.objects.all():
            result['shop'].append({'id': supplier.id, 'name': supplier.name})

        for stock in Stock.objects.all().\
                prefetch_related('product_characteristics', 'product_characteristics__characteristic').\
                select_related('product', 'product__category', 'supplier'):
            parameters = {}
            for parameter in stock.product_characteristics.all():
                parameters[parameter.characteristic.name] = parameter.value

            result['goods'].append({'id': stock.sku,
                                    'category': stock.product.category.id,
                                    'model': stock.model,
                                    'name': stock.product.name,
                                    'shop': stock.supplier.id,
                                    'price': float('{:.2f}'.format(stock.price)),
                                    'price_rrc': float('{:.2f}'.format(stock.price_rrc)),
                                    'quantity': stock.quantity,
                                    'parameters': parameters})
        with open('export.yml', 'w', encoding='utf8') as outfile:
            yaml.dump(result, outfile, allow_unicode=True, default_flow_style=False)
