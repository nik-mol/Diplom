from rest_framework import serializers

from procurement_supply.models import (CartPosition, Category, ChainStore,
                                       Characteristic, Order, OrderPosition,
                                       Product, ProductCharacteristic,
                                       Purchaser, ShoppingCart, Stock,
                                       Supplier, User)


class UserSerializer(serializers.ModelSerializer):
    """
    Serializer class to serialize user instances
    """

    password = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "password",
            "email",
            "first_name",
            "last_name",
            "company",
            "position",
            "type",
            "is_staff",
            "is_superuser",
        ]
        read_only_fields = ["is_staff", "is_superuser"]


class SupplierSerializer(serializers.ModelSerializer):
    """
    Serializer class to serialize supplier instances
    """

    address = serializers.CharField(required=False)
    order_status = serializers.BooleanField(required=False)

    class Meta:
        model = Supplier
        fields = ["id", "user", "name", "address", "order_status"]


class CategorySerializer(serializers.ModelSerializer):
    """
    Serializer class to serialize category instances
    """

    class Meta:
        model = Category
        fields = ["id", "name"]


class ProductSerializer(serializers.ModelSerializer):
    """
    Serializer class to serialize product instances
    """

    class Meta:
        model = Product
        fields = ["id", "name", "category"]


class CharacteristicSerializer(serializers.ModelSerializer):
    """
    Serializer class to serialize characteristic instances
    """

    class Meta:
        model = Characteristic
        fields = ["id", "name"]


class ProductCharacteristicSerializer(serializers.ModelSerializer):
    """
    Serializer class to serialize product characteristic instances
    """

    class Meta:
        model = ProductCharacteristic
        fields = ["id", "stock", "characteristic", "value"]


class StockSerializer(serializers.ModelSerializer):
    """
    Serializer class to serialize stock instances
    """

    description = serializers.CharField(required=False)
    model = serializers.CharField(required=False)
    sku = serializers.CharField()
    product_characteristics = serializers.StringRelatedField(read_only=True, many=True)

    class Meta:
        model = Stock
        fields = [
            "id",
            "description",
            "model",
            "sku",
            "product",
            "supplier",
            "price",
            "price_rrc",
            "quantity",
            "product_characteristics",
        ]


class ChainStoreSerializer(serializers.ModelSerializer):
    """
    Serializer class to serialize chain store instances
    """

    class Meta:
        model = ChainStore
        fields = ["id", "purchaser", "name", "address", "phone"]


class PurchaserSerializer(serializers.ModelSerializer):
    """
    Serializer class to serialize purchaser instances
    """

    chain_stores = ChainStoreSerializer(read_only=True, many=True)

    class Meta:
        model = Purchaser
        fields = ["id", "user", "name", "address", "shopping_cart", "chain_stores"]
        read_only_fields = ["shopping_cart"]


class CartPositionSerializer(serializers.ModelSerializer):
    """
    Serializer class to serialize cart position instances
    """

    class Meta:
        model = CartPosition
        fields = ["id", "shopping_cart", "stock", "quantity", "price", "amount"]
        read_only_fields = ["amount"]


class ShoppingCartSerializer(serializers.ModelSerializer):
    """
    Serializer class to serialize shopping cart instances
    """

    cart_positions = CartPositionSerializer(many=True)

    class Meta:
        model = ShoppingCart
        fields = ["id", "purchaser", "total_quantity", "total_amount", "cart_positions"]


class OrderPositionSerializer(serializers.ModelSerializer):
    """
    Serializer class to serialize order position instances
    """

    stock = StockSerializer(read_only=True)

    class Meta:
        model = OrderPosition
        fields = [
            "id",
            "order",
            "stock",
            "quantity",
            "price",
            "confirmed",
            "delivered",
            "amount",
        ]
        read_only_fields = ["order", "stock", "quantity", "price" "amount"]


class OrderSerializer(serializers.ModelSerializer):
    """
    Serializer class to serialize order instances
    """

    chain_store = ChainStoreSerializer()
    order_positions = OrderPositionSerializer(read_only=True, many=True)

    class Meta:
        model = Order
        fields = [
            "id",
            "purchaser",
            "date",
            "chain_store",
            "total_quantity",
            "total_amount",
            "status",
            "confirmed",
            "delivered",
            "order_positions",
        ]
        read_only_fields = [
            "total_quantity",
            "date",
            "total_amount",
            "status",
            "confirmed",
            "delivered",
        ]


class OrderCreateSerializer(serializers.ModelSerializer):
    """
    Serializer class to serialize order instances upon create or update actions
    """

    class Meta:
        model = Order
        fields = ["id", "purchaser", "date", "chain_store", "status"]
        read_only_fields = ["date", "status"]
