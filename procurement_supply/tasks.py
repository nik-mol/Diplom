import requests
import yaml
from celery import shared_task
from django.core.mail import send_mail
from django.conf import settings
from django.core.exceptions import MultipleObjectsReturned, ValidationError
from django.core.validators import URLValidator
from django.db.utils import IntegrityError

from procurement_supply.models import Supplier, Category, Stock, Product, ProductCharacteristic, Characteristic


@shared_task()
def send_email(title, message, address):
    """
    Sends email with indicated title and message to indicated user
    """
    send_mail(title, message, settings.EMAIL_HOST_USER, [address], fail_silently=False)


@shared_task()
def do_import(url, user_id=None):
    """
    Performs import of stocks from file with determinated structure
    """

    url_validator = URLValidator()
    try:
        url_validator(url)
    except ValidationError:
        return {'status': 'fail', "detail": 'Enter a valid URL.'}

    import_file = requests.get(url).content
    data = yaml.load(import_file, Loader=yaml.FullLoader)

    try:
        if user_id:
            supplier, created = Supplier.objects.get_or_create(
                user__id=user_id, name=data["shop"]
            )
        else:
            if not Supplier.objects.filter(name=data["shop"]).exists():
                return {'status': 'fail', "detail": "Indicted supplier does not exist"}
            supplier = Supplier.objects.get(name=data["shop"])
    except IntegrityError:
        return {'status': 'fail', "detail": "Request user already refers to another supplier instance"}

    for category in data["categories"]:
        try:
            category_instance, created = Category.objects.get_or_create(
                id=category["id"], name=category["name"]
            )
            category_instance.suppliers.add(supplier.id)
            category_instance.save()
        except IntegrityError:
            return {'status': 'fail', "detail": "Category with id from your file already exists with another name"}

    for db_stock in Stock.objects.filter(supplier=supplier.id):
        db_stock.quantity = 0
        db_stock.save()

    for import_stock in data["goods"]:
        try:
            product, created = Product.objects.get_or_create(
                name=import_stock["name"],
                category=Category.objects.get(id=import_stock["category"]),
            )

        except MultipleObjectsReturned:
            product = Product.objects.filter(
                name=import_stock["name"], category__id=import_stock["category"]
            ).first()
        if Stock.objects.filter(
            sku=import_stock["id"], product=product.id, supplier=supplier.id
        ).exists():
            stock = Stock.objects.get(
                sku=import_stock["id"], product=product.id, supplier=supplier.id
            )
            stock.model = import_stock["model"]
            stock.price = import_stock["price"]
            stock.price_rrc = import_stock["price_rrc"]
            stock.quantity = import_stock["quantity"]
            stock.save()
            ProductCharacteristic.objects.filter(stock=stock.id).delete()
        else:
            stock = Stock.objects.create(
                sku=import_stock["id"],
                model=import_stock.get("model"),
                product=product,
                supplier=supplier,
                price=import_stock["price"],
                price_rrc=import_stock["price_rrc"],
                quantity=import_stock["quantity"],
            )
        for name, value in import_stock["parameters"].items():
            characteristic, created = Characteristic.objects.get_or_create(
                name=name
            )
            ProductCharacteristic.objects.create(
                characteristic=characteristic, stock=stock, value=value
            )

    return {'status': "success", 'detail': "Import or update performed successfully"}
