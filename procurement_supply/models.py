import uuid
from decimal import Decimal

from django.conf import settings
from django.contrib.auth.models import AbstractUser, UserManager
from django.core.validators import MinValueValidator
from django.db import models


USER_TYPE_CHOICES = (
    ("purchaser", "закупщик"),
    ("supplier", "поставщик"),
    ("admin", "админ"),
)

ORDER_CHOICES = (
    ("saved", "сохранен"),
    ("cancelled", "отменен"),
)


class User(AbstractUser):
    """
    Class to describe custom user
    """

    email = models.EmailField()
    first_name = models.CharField(max_length=150)
    last_name = models.CharField(max_length=150)
    company = models.CharField(max_length=50)
    position = models.CharField(max_length=50)
    type = models.CharField(
        max_length=10, choices=USER_TYPE_CHOICES, default="purchaser"
    )

    objects = UserManager()

    REQUIRED_FIELDS = ["email", "first_name", "last_name", "company", "position"]

    def __str__(self):
        return f"{self.first_name} {self.last_name}"

    class Meta:
        verbose_name = "Пользователь"
        verbose_name_plural = "Список пользователей"
        ordering = ("id",)


class Supplier(models.Model):
    """
    Class to describe products suppliers
    """

    user = models.OneToOneField(User, on_delete=models.CASCADE)
    name = models.CharField(max_length=50, unique=True)
    address = models.CharField(max_length=100, null=True, blank=True)
    order_status = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Поставщик"
        verbose_name_plural = "Список поставщиков"
        ordering = ("-order_status", "name")

    def __str__(self):
        return self.name


class Category(models.Model):
    """
    Class to describe products categories
    """

    name = models.CharField(max_length=30, unique=True)
    suppliers = models.ManyToManyField(Supplier, related_name="categories", blank=True)

    class Meta:
        verbose_name = "Категория"
        verbose_name_plural = "Список категорий"
        ordering = ("name",)

    def __str__(self):
        return self.name


class Product(models.Model):
    """
    Class to describe products
    """

    name = models.CharField(max_length=50)
    category = models.ForeignKey(
        Category, on_delete=models.CASCADE, related_name="products"
    )

    class Meta:
        verbose_name = "Продукт"
        verbose_name_plural = "Список продуктов"
        ordering = ("name",)

    def __str__(self):
        return self.name


class Stock(models.Model):
    """
    Class to describe stock of certain product on warehouse of certain supplier
    """

    description = models.TextField(null=True, blank=True)
    sku = models.CharField(max_length=30)
    model = models.CharField(max_length=50, null=True, blank=True)
    product = models.ForeignKey(
        Product, on_delete=models.CASCADE, related_name="stocks"
    )
    supplier = models.ForeignKey(
        Supplier, on_delete=models.CASCADE, related_name="stocks"
    )
    price = models.DecimalField(
        decimal_places=2, max_digits=16, validators=[MinValueValidator(0.01)]
    )
    price_rrc = models.DecimalField(
        decimal_places=2, max_digits=16, validators=[MinValueValidator(0.01)]
    )
    quantity = models.PositiveIntegerField()

    class Meta:
        verbose_name = "Запас продукта"
        verbose_name_plural = "Список запасов продукта"
        constraints = [
            models.UniqueConstraint(
                fields=["sku", "product", "supplier"], name="unique_stock"
            ),
        ]
        ordering = ("product", "price")

    def __str__(self):
        return f"Запас {self.product.name} у {self.supplier.name}"


class Characteristic(models.Model):
    """
    Class to describe products characteristics
    """

    name = models.CharField(max_length=50, unique=True)

    class Meta:
        verbose_name = "Характеристика"
        verbose_name_plural = "Список характеристик"
        ordering = ("name",)

    def __str__(self):
        return self.name


class ProductCharacteristic(models.Model):
    """
    Class to describe certain characteristic of certain stock of products
    """

    stock = models.ForeignKey(
        Stock, on_delete=models.CASCADE, related_name="product_characteristics"
    )
    characteristic = models.ForeignKey(
        Characteristic, on_delete=models.CASCADE, related_name="product_characteristics"
    )
    value = models.CharField(max_length=30)

    class Meta:
        verbose_name = "Характеристика запаса продукта"
        verbose_name_plural = "Список характеристик запаса продукта"
        constraints = [
            models.UniqueConstraint(
                fields=["stock", "characteristic"], name="unique_product_characteristic"
            ),
        ]
        ordering = ("stock", "value")

    def __str__(self):
        return self.value


class Purchaser(models.Model):
    """
    Class to describe products purchaser
    """

    user = models.OneToOneField(User, on_delete=models.CASCADE)
    name = models.CharField(max_length=50)
    address = models.CharField(max_length=100, null=True, blank=True)

    class Meta:
        verbose_name = "Закупщик"
        verbose_name_plural = "Список закупщиков"
        ordering = ("name",)

    def __str__(self):
        return self.name


class ChainStore(models.Model):
    """
    Class to describe chain store
    """

    purchaser = models.ForeignKey(
        Purchaser, on_delete=models.CASCADE, related_name="chain_stores"
    )
    name = models.CharField(max_length=30)
    address = models.CharField(max_length=150)
    phone = models.CharField(max_length=50)

    class Meta:
        verbose_name = "Розничный магазин"
        verbose_name_plural = "Список розничных магазинов"
        ordering = ("name",)

    def __str__(self):
        return f"{self.name} {self.address}"


class ShoppingCart(models.Model):
    """
    Class to describe purchasers shopping cart
    """

    purchaser = models.OneToOneField(
        Purchaser, on_delete=models.CASCADE, related_name="shopping_cart"
    )

    def calculate_total_quantity(self):
        """
        Calculates total quantity of items in shopping cart
        :return: total quantity of items
        """
        return sum([position.quantity for position in self.cart_positions.all()])

    @property
    def total_quantity(self) -> int:
        """
        Sets total_quantity field of shopping cart instance
        :return: total quantity of items
        """
        return self.calculate_total_quantity()

    def calculate_total_amount(self):
        """
        Calculates total amount of shopping cart
        :return: total amount for items
        """
        return sum([position.amount for position in self.cart_positions.all()])

    @property
    def total_amount(self) -> Decimal:
        """
        Sets total_amount field of shopping cart instance
        :return: total amount of cart
        """
        return self.calculate_total_amount()

    class Meta:
        verbose_name = "Корзина"
        verbose_name_plural = "Список корзин"
        ordering = ("id",)

    def __str__(self):
        return f"Корзина {self.purchaser.name}"


class CartPosition(models.Model):
    """
    Class to describe products positions in purchasers cart
    """

    shopping_cart = models.ForeignKey(
        ShoppingCart, on_delete=models.CASCADE, related_name="cart_positions"
    )
    stock = models.ForeignKey(
        Stock, on_delete=models.CASCADE, related_name="cart_positions"
    )
    quantity = models.PositiveIntegerField(validators=[MinValueValidator(0)])
    price = models.DecimalField(
        decimal_places=2, max_digits=16, validators=[MinValueValidator(0.01)], default=0
    )

    @property
    def amount(self) -> Decimal:
        """
        Calculates and setts amount field of cart position instance
        :return:
        """
        return self.quantity * self.price

    class Meta:
        verbose_name = "Позиция корзины"
        verbose_name_plural = "Список позиций корзин"
        constraints = [
            models.UniqueConstraint(
                fields=["shopping_cart", "stock"], name="unique_shopping_cart_stock"
            ),
        ]
        ordering = ("shopping_cart",)


class Order(models.Model):
    """
    Class to describe order
    """

    purchaser = models.ForeignKey(
        Purchaser, on_delete=models.CASCADE, related_name="orders"
    )
    date = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=15, choices=ORDER_CHOICES, default="saved")
    chain_store = models.ForeignKey(
        ChainStore, on_delete=models.CASCADE, related_name="orders"
    )

    def check_confirmed(self):
        """
        Checks whether all order positions are confirmed
        :return: True if all positions are confirmed, otherwise False
        """
        for position in self.order_positions.all():
            if not position.confirmed:
                return False
        return True

    @property
    def confirmed(self) -> bool:
        """
        Sets confirmed field of order instance
        :return: True if all positions are confirmed, otherwise False
        """
        return self.check_confirmed()

    def check_delivered(self):
        """
        Checks whether all order positions are delivered
        :return: True if all positions are delivered, otherwise False
        """
        for position in self.order_positions.all():
            if not position.delivered:
                return False
        return True

    @property
    def delivered(self) -> bool:
        """
        Sets delivered field of order instance
        :return: True if all positions are delivered, otherwise False
        """
        return self.check_delivered()

    def calculate_total_quantity(self):
        """
        Calculates total quantity of items in order
        :return: total quantity of items
        """
        return sum([position.quantity for position in self.order_positions.all()])

    @property
    def total_quantity(self) -> int:
        """
        Sets total_quantity field of order instance
        :return: total quantity of items
        """
        return self.calculate_total_quantity()

    def calculate_total_amount(self):
        """
        Calculates total amount for items in order.
        If order contains positions from more than one supplier, amount will be multiplied using
        COMBINED_ORDER_MULTIPLIER from project settings
        :return: total amount of order
        """
        amount = 0
        suppliers = set()
        for position in self.order_positions.all():
            amount += position.amount
            suppliers.add(position.stock.supplier)
        if len(suppliers) > 1:
            amount = Decimal(settings.COMBINED_ORDER_MULTIPLIER) * Decimal(amount)
        return amount

    @property
    def total_amount(self) -> Decimal:
        """
        Sets total_amount field of order instance
        :return: total amount of order
        """
        return self.calculate_total_amount()

    class Meta:
        verbose_name = "Заказ"
        verbose_name_plural = "Список заказов"
        ordering = ("-date", "purchaser")

    def __str__(self):
        return f"{self.purchaser.name} {self.date}"


class OrderPosition(models.Model):
    """
    Class to describe certain product position of certain order
    """

    order = models.ForeignKey(
        Order, on_delete=models.CASCADE, related_name="order_positions"
    )
    stock = models.ForeignKey(
        Stock, on_delete=models.CASCADE, related_name="order_positions"
    )
    quantity = models.PositiveIntegerField(validators=[MinValueValidator(0)])
    price = models.DecimalField(
        decimal_places=2, max_digits=16, validators=[MinValueValidator(0.01)], default=0
    )
    confirmed = models.BooleanField(default=False)
    delivered = models.BooleanField(default=False)

    @property
    def amount(self) -> Decimal:
        """
        Calculates and setts amount field of order position instance
        :return:
        """
        return self.quantity * self.price

    class Meta:
        verbose_name = "Позиция заказа"
        verbose_name_plural = "Список позиций заказов"
        constraints = [
            models.UniqueConstraint(
                fields=["order", "stock"], name="unique_order_stock"
            ),
        ]
        ordering = ("order", "price")


class PasswordResetToken(models.Model):
    """
    Class to describe password reset token
    """

    user = models.OneToOneField(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    token = models.UUIDField(default=uuid.uuid4)

    class Meta:
        verbose_name = "Токен сброса пароля"
        verbose_name_plural = "Токены сброса пароля"

    def __str__(self):
        return f"Password reset token for user {self.user}"
