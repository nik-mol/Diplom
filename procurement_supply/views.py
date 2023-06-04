from uuid import UUID

from django.contrib.auth.hashers import check_password, make_password
from django.contrib.auth.password_validation import validate_password
from django.db.models.query import QuerySet
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.viewsets import ModelViewSet
from celery.result import AsyncResult

from order_service.celery import app as celery_app
from procurement_supply.tasks import send_email, do_import
from procurement_supply.models import (CartPosition, Category, ChainStore,
                                       Characteristic, Order, OrderPosition,
                                       PasswordResetToken, Product,
                                       ProductCharacteristic, Purchaser,
                                       ShoppingCart, Stock, Supplier, User)
from procurement_supply.permissions import (IsAdmin, IsCartPositionOwner,
                                            IsCartStockOwner,
                                            IsOrderPositionOwner,
                                            IsOrderStockOwner, IsOwner,
                                            IsPurchaser, IsPurchaserOwner,
                                            IsStockOwner,
                                            IsStockReferencedOwner, IsSupplier,
                                            IsUser)
from procurement_supply.serializers import (CartPositionSerializer,
                                            CategorySerializer,
                                            ChainStoreSerializer,
                                            CharacteristicSerializer,
                                            OrderCreateSerializer,
                                            OrderPositionSerializer,
                                            OrderSerializer,
                                            ProductCharacteristicSerializer,
                                            ProductSerializer,
                                            PurchaserSerializer,
                                            ShoppingCartSerializer,
                                            StockSerializer,
                                            SupplierSerializer, UserSerializer)


class UserViewSet(ModelViewSet):
    """
    ViewSet class to provide CRUD operations with user instances
    """

    queryset = User.objects.all()
    serializer_class = UserSerializer
    http_method_names = ["post", "patch", "get", "delete"]

    def get_queryset(self):
        """
        Get the list of user items for view.
        """

        assert self.queryset is not None, (
            "'%s' should either include a `queryset` attribute, "
            "or override the `get_queryset()` method." % self.__class__.__name__
        )

        queryset = self.queryset
        if isinstance(queryset, QuerySet):
            queryset = queryset.all()
        if self.request.user.is_superuser:
            return queryset
        else:
            return queryset.filter(id=self.request.user.id)

    def get_permissions(self):
        """
        Instantiates and returns the list of permissions that this view requires.
        """

        if self.action == "list":
            return [IsAuthenticated()]
        if self.action == "destroy":
            return [IsAdmin()]
        if self.action in ["retrieve", "update", "partial_update"]:
            RetrieveUpdatePerm = IsAdmin | IsUser
            return [RetrieveUpdatePerm()]
        return []

    def create(self, request, *args, **kwargs):
        """
        Create a user instance and send email confirmation.
        """

        if not request.data.get("password"):
            return Response(
                {"password": ["This field is required."]}, status.HTTP_400_BAD_REQUEST
            )

        try:
            validate_password(request.data["password"])
        except Exception as errors:
            return Response(
                {"error": [error for error in errors]}, status.HTTP_400_BAD_REQUEST
            )

        request.data["password"] = make_password(request.data["password"])

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)

        return Response(
            serializer.data, status=status.HTTP_201_CREATED, headers=headers
        )

    def destroy(self, request, *args, **kwargs):
        """
        Destroy (deactivate) a user instance.
        """
        instance = self.get_object()
        instance.is_active = False
        instance.save()
        return Response(status=status.HTTP_204_NO_CONTENT)

    def update(self, request, *args, **kwargs):
        """
        Update a user instance.
        """

        if "type" in request.data:
            return Response(
                {"error": "type cannot be amended"}, status=status.HTTP_403_FORBIDDEN
            )

        password = request.data.pop("password", None)

        if (
            password
            and request.data.get("new_password")
            and request.user == self.get_object()
        ):
            if check_password(password, self.get_object().password):
                try:
                    validate_password(request.data["new_password"])
                except Exception as errors:
                    return Response(
                        {"error": [error for error in errors]},
                        status.HTTP_400_BAD_REQUEST,
                    )
                request.data["password"] = make_password(request.data["new_password"])

            else:
                return Response(
                    {"error": "wrong password"}, status=status.HTTP_403_FORBIDDEN
                )

        if type(request.data.get("is_superuser")) == bool and request.user.is_superuser:
            instance = self.get_object()
            instance.is_superuser = request.data.get("is_superuser")
            instance.save()

        if type(request.data.get("is_staff")) == bool and request.user.is_superuser:
            instance = self.get_object()
            instance.is_staff = request.data.get("is_staff")
            instance.save()

        return super().update(request, *args, **kwargs)


class PasswordResetView(APIView):
    """
    APIView class to perform password reset operations
    """

    def post(self, request):
        """
        Method to arrange receipt of password reset token and to reset password using this token
        :param request: request objects
        :return: response with corresponding status code
        """

        if request.data.get("token"):
            if {"username", "new_password"}.issubset(request.data):
                if not User.objects.filter(
                    username=request.data.get("username")
                ).exists():
                    return Response(
                        {"error": "User with such username does not exist"},
                        status.HTTP_400_BAD_REQUEST,
                    )

                user = User.objects.get(username=request.data.get("username"))

                try:
                    UUID(request.data.get("token"))
                except ValueError:
                    return Response(
                        {"error": "Wrong token"}, status.HTTP_400_BAD_REQUEST
                    )

                if not PasswordResetToken.objects.filter(
                    token=request.data.get("token")
                ).exists():
                    return Response(
                        {"error": "Wrong token"}, status.HTTP_400_BAD_REQUEST
                    )

                token = PasswordResetToken.objects.get(token=request.data.get("token"))

                if token.user == user:
                    try:
                        validate_password(request.data["new_password"])
                    except Exception as errors:
                        return Response(
                            {"error": [error for error in errors]},
                            status.HTTP_400_BAD_REQUEST,
                        )
                    token.delete()

                    user.password = make_password(request.data.get("new_password"))
                    user.save()
                    return Response(
                        {"success": "Your password has been changed"},
                        status.HTTP_200_OK,
                    )
                else:
                    return Response(
                        {"error": "Wrong token"}, status.HTTP_400_BAD_REQUEST
                    )

            else:
                return Response(
                    {
                        "error": '"username" and "new_password" fields are required for set of new password'
                    },
                    status.HTTP_400_BAD_REQUEST,
                )
        else:
            if request.data.get("username"):
                if not User.objects.filter(
                    username=request.data.get("username")
                ).exists():
                    return Response(
                        {"error": "User with such username does not exist"},
                        status.HTTP_400_BAD_REQUEST,
                    )

                user = User.objects.get(username=request.data.get("username"))

                token, created = PasswordResetToken.objects.get_or_create(user=user)

                text = f"Your password reset token is {token.token}"
                send_email.delay("Password reset token", text, user.email)
                return Response(
                    {
                        "success": "Reset token is sent to your email."
                    },
                    status.HTTP_200_OK,
                )
            else:
                return Response(
                    {"error": '"username" field is required for reset token obtain'},
                    status.HTTP_400_BAD_REQUEST,
                )


class SupplierViewSet(ModelViewSet):
    """
    ViewSet class to provide CRUD operations with supplier instances
    """
    queryset = Supplier.objects.all()
    serializer_class = SupplierSerializer
    http_method_names = ["post", "patch", "get", "delete"]

    def get_queryset(self):
        """
        Get the list of supplier items for view.
        """

        assert self.queryset is not None, (
            "'%s' should either include a `queryset` attribute, "
            "or override the `get_queryset()` method." % self.__class__.__name__
        )

        queryset = self.queryset
        if isinstance(queryset, QuerySet):
            queryset = queryset.all()
        if self.request.user.is_superuser or self.request.user.type == "purchaser":
            return queryset
        if self.request.user.type == "supplier":
            return queryset.filter(user=self.request.user.id)

    def get_permissions(self):
        """
        Instantiates and returns the list of permissions that this view requires.
        """

        if self.action == "list":
            return [IsAuthenticated()]
        if self.action == "destroy":
            return [IsAdmin()]
        if self.action == "retrieve":
            RetrievePerm = IsAdmin | IsOwner | IsPurchaser
            return [RetrievePerm()]
        if self.action in ["update", "partial_update"]:
            return [IsOwner()]
        if self.action == "create":
            return [IsSupplier()]
        return []

    def create(self, request, *args, **kwargs):
        """
        Create a supplier instance.
        """

        request.data["user"] = request.user.id
        return super().create(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        """
        Destroy (stop orders for) a supplier instance.
        """

        instance = self.get_object()
        instance.order_status = False
        instance.save()
        return Response(status=status.HTTP_204_NO_CONTENT)

    def update(self, request, *args, **kwargs):
        """
        Update a supplier instance.
        """

        if "user" in request.data:
            return Response(
                {"error": "user cannot be amended"}, status=status.HTTP_403_FORBIDDEN
            )
        return super().update(request, *args, **kwargs)


class CategoryViewSet(ModelViewSet):
    """
    ViewSet class to provide CRUD operations with category instances
    """
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    http_method_names = ["post", "patch", "get", "delete"]

    filterset_fields = ["id", "name"]
    search_fields = ["name"]

    def get_permissions(self):
        """
        Instantiates and returns the list of permissions that this view requires.
        """

        if self.action in ["list", "retrieve"]:
            return [IsAuthenticated()]
        if self.action == "create":
            CreatePerm = IsAdmin | IsSupplier
            return [CreatePerm()]
        if self.action in ["destroy", "update", "partial_update"]:
            return [IsAdmin()]
        return []


class ProductViewSet(ModelViewSet):
    """
    ViewSet class to provide CRUD operations with product instances
    """
    queryset = Product.objects.all()
    serializer_class = ProductSerializer
    http_method_names = ["post", "patch", "get", "delete"]
    filterset_fields = ["id", "name", "category__id", "category__name"]
    search_fields = ["name"]

    def get_permissions(self):
        """
        Instantiates and returns the list of permissions that this view requires.
        """

        if self.action in ["list", "retrieve"]:
            return [IsAuthenticated()]
        if self.action == "create":
            CreatePerm = IsAdmin | IsSupplier
            return [CreatePerm()]
        if self.action in ["destroy", "update", "partial_update"]:
            return [IsAdmin()]
        return []


class CharacteristicViewSet(ModelViewSet):
    """
    ViewSet class to provide CRUD operations with characteristic instances
    """
    queryset = Characteristic.objects.all()
    serializer_class = CharacteristicSerializer
    http_method_names = ["post", "patch", "get", "delete"]

    def get_permissions(self):
        """
        Instantiates and returns the list of permissions that this view requires.
        """

        if self.action in ["list", "retrieve"]:
            return [IsAuthenticated()]
        if self.action == "create":
            CreatePerm = IsAdmin | IsSupplier
            return [CreatePerm()]
        if self.action in ["destroy", "update", "partial_update"]:
            return [IsAdmin()]
        return []


class StockViewSet(ModelViewSet):
    """
    ViewSet class to provide CRUD operations with stock instances
    """
    queryset = Stock.objects.all()
    serializer_class = StockSerializer
    http_method_names = ["post", "patch", "get", "delete"]
    filterset_fields = [
        "product__id",
        "product__name",
        "product__category__id",
        "product__category__name",
        "supplier__id",
        "supplier__name",
    ]
    search_fields = [
        "description",
        "model",
        "product__name",
        "product__category__name",
        "supplier__name",
        "supplier__address",
        "product_characteristics__value",
    ]

    def get_queryset(self):
        """
        Get the list of stock items for view.
        """

        assert self.queryset is not None, (
            "'%s' should either include a `queryset` attribute, "
            "or override the `get_queryset()` method." % self.__class__.__name__
        )

        queryset = self.queryset
        if isinstance(queryset, QuerySet):
            queryset = queryset.all()
        if self.request.user.is_superuser:
            return queryset.select_related("product").prefetch_related(
                "product_characteristics", "product"
            )
        if self.request.user.type == "purchaser":
            return (
                queryset.filter(supplier__order_status=True, quantity__gt=0)
                .select_related("product")
                .prefetch_related("product_characteristics", "product")
            )
        if self.request.user.type == "supplier":
            return (
                queryset.filter(supplier__user=self.request.user)
                .select_related("product")
                .prefetch_related("product_characteristics", "product")
            )

    def get_permissions(self):
        """
        Instantiates and returns the list of permissions that this view requires.
        """

        if self.action in ["list"]:
            return [IsAuthenticated()]
        if self.action in ["retrieve"]:
            RetrievePerm = IsAdmin | IsPurchaser | IsStockOwner
            return [RetrievePerm()]
        if self.action == "create":
            return [IsSupplier()]
        if self.action in ["update", "partial_update"]:
            return [IsStockOwner()]
        if self.action == "destroy":
            return [IsAdmin()]
        return []

    def create(self, request, *args, **kwargs):
        """
        Create a stock instance.
        """

        user = request.user
        if not Supplier.objects.filter(user=user).exists():
            return Response(
                {
                    "error": "you need to create Supplier before you create or update Stock"
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        request.data["supplier"] = Supplier.objects.get(user=user).id
        if Stock.objects.filter(
            sku=request.data.get("sku"),
            product=request.data.get("product"),
            supplier=request.data.get("supplier"),
        ).exists():
            return Response(
                {"error": "This Stock already exists"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return super().create(request, *args, **kwargs)

    def update(self, request, *args, **kwargs):
        """
        Update a stock instance.
        """

        if request.data.get("product") or request.data.get("supplier"):
            return Response(
                {"error": "Stocks product and supplier cannot be amended"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        stock = self.get_object()
        if request.data.get("sku"):
            if Stock.objects.filter(
                sku=request.data.get("sku"),
                product=stock.product.id,
                supplier=stock.supplier.id,
            ).exists():
                return Response(
                    {"error": "Stock with this sku and product already exists"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        return super().update(request, *args, **kwargs)


class ProductCharacteristicViewSet(ModelViewSet):
    """
    ViewSet class to provide CRUD operations with product characteristic instances
    """
    queryset = ProductCharacteristic.objects.all()
    serializer_class = ProductCharacteristicSerializer
    http_method_names = ["post", "patch", "get", "delete"]

    def get_permissions(self):
        """
        Instantiates and returns the list of permissions that this view requires.
        """

        if self.action in ["list", "retrieve"]:
            return [IsAuthenticated()]
        if self.action == "create":
            return [IsSupplier()]
        if self.action in ["update", "partial_update", "destroy"]:
            return [IsStockReferencedOwner()]
        return []

    def create(self, request, *args, **kwargs):
        """
        Create a product characteristic instance.
        """

        if (
            request.data.get("stock")
            and Stock.objects.filter(id=request.data.get("stock")).exists()
        ):
            if (
                Stock.objects.get(id=request.data.get("stock")).supplier.user
                == request.user
            ):
                if ProductCharacteristic.objects.filter(
                    stock=request.data.get("stock"),
                    characteristic=request.data.get("characteristic"),
                ).exists():
                    return Response(
                        {"error": "this stock already has this characteristic"},
                        status.HTTP_400_BAD_REQUEST,
                    )
                return super().create(request, *args, **kwargs)
            else:
                return Response(
                    {"detail": "You do not have permission to perform this action."},
                    status.HTTP_403_FORBIDDEN,
                )
        else:
            return Response(
                {
                    "error": '"stock" is either not indicated or such stock does not exist'
                },
                status.HTTP_400_BAD_REQUEST,
            )

    def update(self, request, *args, **kwargs):
        """
        Update a product characteristic instance.
        """

        if request.data.get("stock") or request.data.get("characteristic"):
            return Response(
                {"error": 'Only "value" field can be amended'},
                status.HTTP_400_BAD_REQUEST,
            )
        return super().update(request, *args, **kwargs)


class ImportView(APIView):
    """
    APIView class to perform stocks import operations
    """

    def post(self, request):
        """
        Method to arrange import of stocks from suppliers file with determinated structure
        :param request: request object
        :return: response with corresponding status code
        """
        if not request.user.is_authenticated:
            return Response(
                {"detail": "Authentication credentials were not provided."},
                status.HTTP_401_UNAUTHORIZED,
            )
        if not request.user.type == "supplier":
            return Response(
                {"detail": "You do not have permission to perform this action."},
                status.HTTP_403_FORBIDDEN,
            )
        url = request.data.get("url")
        if url:
            async_result = do_import.delay(url, request.user.id)
            return Response({"detail": f"Your task id is {async_result.task_id}"}, status.HTTP_200_OK)
        return Response({"url": ["This field is required."]}, status.HTTP_400_BAD_REQUEST)


class ImportCheckView(APIView):
    """
    APIView class to get result of stocks import operations
    """

    def get(self, request, task_id):
        """
        Checks status and result of celery-task fulfilment for authenticated supplier or admin user
        """
        if not request.user.is_authenticated:
            return Response(
                {"detail": "Authentication credentials were not provided."},
                status.HTTP_401_UNAUTHORIZED,
            )
        if not request.user.type == "supplier" and not request.user.is_superuser:
            return Response(
                {"detail": "You do not have permission to perform this action."},
                status.HTTP_403_FORBIDDEN,
            )
        result = AsyncResult(task_id, app=celery_app)
        return Response({"status": result.status, 'result': result.result}, status.HTTP_200_OK)


class PurchaserViewSet(ModelViewSet):
    """
    ViewSet class to provide CRUD operations with purchaser instances
    """
    queryset = Purchaser.objects.all()
    serializer_class = PurchaserSerializer
    http_method_names = ["post", "patch", "get"]

    def get_queryset(self):
        """
        Get the list of purchaser items for view.
        """

        assert self.queryset is not None, (
            "'%s' should either include a `queryset` attribute, "
            "or override the `get_queryset()` method." % self.__class__.__name__
        )

        queryset = self.queryset
        if isinstance(queryset, QuerySet):
            queryset = queryset.all()
        if self.request.user.is_superuser:
            return queryset.prefetch_related("chain_stores")
        if self.request.user.type == "purchaser":
            return queryset.filter(user=self.request.user.id).prefetch_related(
                "chain_stores"
            )

    def get_permissions(self):
        """
        Instantiates and returns the list of permissions that this view requires.
        """

        if self.action in ["list"]:
            ListPerm = IsAdmin | IsPurchaser
            return [ListPerm()]
        if self.action in ["retrieve"]:
            RetrievePerm = IsAdmin | IsOwner
            return [RetrievePerm()]
        if self.action in ["update", "partial_update"]:
            return [IsOwner()]
        if self.action == "create":
            return [IsPurchaser()]
        return []

    def create(self, request, *args, **kwargs):
        """
        Create a purchaser instance and corresponding shopping cart instance
        """

        request.data["user"] = request.user.id
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        shoppingcart = ShoppingCart.objects.create(
            purchaser=Purchaser.objects.get(id=serializer.data["id"])
        )
        response = serializer.data.copy()
        response["shopping_cart"] = shoppingcart.id
        return Response(response, status=status.HTTP_201_CREATED, headers=headers)

    def update(self, request, *args, **kwargs):
        """
        Update a purchaser instance.
        """

        if "user" in request.data:
            return Response(
                {"error": "user cannot be amended"}, status=status.HTTP_403_FORBIDDEN
            )
        return super().update(request, *args, **kwargs)


class ShoppingCartViewSet(ModelViewSet):
    """
    ViewSet class to provide CRUD operations with shopping cart instances
    """
    queryset = ShoppingCart.objects.all()
    serializer_class = ShoppingCartSerializer
    http_method_names = ["get", "delete"]

    def get_queryset(self):
        """
        Get the list of shopping cart items for view.
        """

        assert self.queryset is not None, (
            "'%s' should either include a `queryset` attribute, "
            "or override the `get_queryset()` method." % self.__class__.__name__
        )

        queryset = self.queryset
        if isinstance(queryset, QuerySet):
            queryset = queryset.all()
        if self.request.user.is_superuser:
            return queryset.prefetch_related("cart_positions")
        if self.request.user.type == "purchaser":
            return queryset.filter(purchaser__user=self.request.user).prefetch_related(
                "cart_positions"
            )
        if self.request.user.type == "supplier":
            return (
                queryset.filter(cart_positions__stock__supplier__user=self.request.user)
                .distinct()
                .prefetch_related("cart_positions")
            )

    def get_permissions(self):
        """
        Instantiates and returns the list of permissions that this view requires.
        """

        if self.action == "list":
            return [IsAuthenticated()]
        if self.action == "retrieve":
            RetrievePerm = IsAdmin | IsPurchaserOwner | IsCartStockOwner
            return [RetrievePerm()]
        if self.action == "destroy":
            return [IsPurchaserOwner()]
        return []

    def destroy(self, request, *args, **kwargs):
        """
        Delete all positions from shopping cart
        """

        cart_positions = CartPosition.objects.filter(shopping_cart=self.get_object())
        for position in cart_positions:
            stock = Stock.objects.get(id=position.stock.id)
            stock.quantity += position.quantity
            stock.save()
        cart_positions.delete()
        return Response({"success": f"Your shopping cart is empty"}, status.HTTP_200_OK)


class CartPositionViewSet(ModelViewSet):
    """
    ViewSet class to provide CRUD operations with cart position instances
    """
    queryset = CartPosition.objects.all()
    serializer_class = CartPositionSerializer
    http_method_names = ["post", "patch", "get", "delete"]

    def get_queryset(self):
        """
        Get the list of cart position items for view.
        """

        assert self.queryset is not None, (
            "'%s' should either include a `queryset` attribute, "
            "or override the `get_queryset()` method." % self.__class__.__name__
        )

        queryset = self.queryset
        if isinstance(queryset, QuerySet):
            queryset = queryset.all()
        if self.request.user.is_superuser:
            return queryset
        if self.request.user.type == "purchaser":
            return queryset.filter(shopping_cart__purchaser__user=self.request.user)
        if self.request.user.type == "supplier":
            return queryset.filter(stock__supplier__user=self.request.user)

    def get_permissions(self):
        """
        Instantiates and returns the list of permissions that this view requires.
        """

        if self.action == "list":
            return [IsAuthenticated()]
        if self.action == "retrieve":
            RetrievePerm = IsAdmin | IsCartPositionOwner | IsStockReferencedOwner
            return [RetrievePerm()]
        if self.action in ["destroy", "update", "partial_update"]:
            return [IsCartPositionOwner()]
        if self.action == "create":
            return [IsPurchaser()]
        return []

    def create(self, request, *args, **kwargs):
        """
        Create a cart position instance.
        """
        if request.data.get("stock") and request.data.get("quantity"):
            if not Purchaser.objects.filter(user=request.user.id).exists():
                return Response(
                    {
                        "error": f"You need to create Purchaser and ShoppingCart will be created as well"
                    },
                    status.HTTP_400_BAD_REQUEST,
                )
            shopping_cart = request.user.purchaser.shopping_cart
            if CartPosition.objects.filter(
                stock=request.data["stock"], shopping_cart=shopping_cart.id
            ).exists():
                return Response(
                    {"error": f"You already have this product in your cart"},
                    status.HTTP_400_BAD_REQUEST,
                )
            request.data["shopping_cart"] = shopping_cart.id
            stock = Stock.objects.get(id=request.data["stock"])
            if not stock.supplier.order_status:
                return Response(
                    {"error": f"This supplier does not take new orders at the moment"},
                    status.HTTP_400_BAD_REQUEST,
                )
            request.data["price"] = stock.price
            if request.data["quantity"] <= 0 or type(request.data["quantity"]) != int:
                return Response(
                    {"quantity": ["Ensure this value is integer and greater than 0."]},
                    status.HTTP_400_BAD_REQUEST,
                )
            if request.data["quantity"] > stock.quantity:
                return Response(
                    {"error": f"Not enough stock. Only {stock.quantity} is available"},
                    status.HTTP_400_BAD_REQUEST,
                )
            else:
                stock.quantity = stock.quantity - request.data["quantity"]
                stock.save()
            return super().create(request, *args, **kwargs)
        else:
            return Response(
                {"error": f'Fields "stock" and "quantity" are required'},
                status.HTTP_400_BAD_REQUEST,
            )

    def destroy(self, request, *args, **kwargs):
        """
        Destroy a cart position instance.
        """

        cart_position = self.get_object()
        stock = Stock.objects.get(id=cart_position.stock.id)
        stock.quantity += cart_position.quantity
        stock.save()
        return super().destroy(request, *args, **kwargs)

    def update(self, request, *args, **kwargs):
        """
        Update a cart position instance.
        """

        if (
            request.data.get("shopping_cart")
            or request.data.get("stock")
            or request.data.get("price")
        ):
            return Response(
                {"error": f'Only "quantity" field may be amended'},
                status.HTTP_400_BAD_REQUEST,
            )
        if "quantity" in request.data:
            if request.data["quantity"] <= 0 or type(request.data["quantity"]) != int:
                return Response(
                    {"quantity": ["Ensure this value is integer and greater than 0."]},
                    status.HTTP_400_BAD_REQUEST,
                )
            cart_position = self.get_object()
            stock = Stock.objects.get(id=cart_position.stock.id)

            if request.data["quantity"] <= cart_position.quantity:
                stock.quantity += cart_position.quantity - request.data["quantity"]
                stock.save()
            else:
                if not stock.supplier.order_status:
                    return Response(
                        {
                            "error": f"This supplier does not take new orders at the moment"
                        },
                        status.HTTP_400_BAD_REQUEST,
                    )
                if stock.quantity >= (
                    request.data["quantity"] - cart_position.quantity
                ):
                    stock.quantity -= request.data["quantity"] - cart_position.quantity
                    stock.save()
                    request.data["price"] = stock.price
                else:
                    return Response(
                        {
                            "error": f"Not enough stock. You can add only {stock.quantity} to your initial quantity"
                        },
                        status.HTTP_400_BAD_REQUEST,
                    )
        return super().update(request, *args, **kwargs)


class ChainStoreViewSet(ModelViewSet):
    """
    ViewSet class to provide CRUD operations with chain store instances
    """
    queryset = ChainStore.objects.all()
    serializer_class = ChainStoreSerializer
    http_method_names = ["post", "patch", "get", "delete"]

    def get_queryset(self):
        """
        Get the list of chain store items for view.
        """

        assert self.queryset is not None, (
            "'%s' should either include a `queryset` attribute, "
            "or override the `get_queryset()` method." % self.__class__.__name__
        )

        queryset = self.queryset
        if isinstance(queryset, QuerySet):
            queryset = queryset.all()
        if self.request.user.is_superuser or self.request.user.type == "supplier":
            return queryset
        if self.request.user.type == "purchaser":
            return queryset.filter(purchaser__user=self.request.user)

    def get_permissions(self):
        """
        Instantiates and returns the list of permissions that this view requires.
        """

        if self.action == "list":
            return [IsAuthenticated()]
        if self.action == "retrieve":
            RetrievePerm = IsAdmin | IsPurchaserOwner | IsSupplier
            return [RetrievePerm()]
        if self.action in ["update", "partial_update"]:
            return [IsPurchaserOwner()]
        if self.action == "destroy":
            return [IsAdmin()]
        if self.action == "create":
            return [IsPurchaser()]
        return []

    def create(self, request, *args, **kwargs):
        """
        Create a chain store instance.
        """

        user = request.user
        if not Purchaser.objects.filter(user=user).exists():
            return Response(
                {
                    "error": "you need to create Purchaser before you create or update ChainStore"
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        request.data["purchaser"] = Purchaser.objects.get(user=user).id
        return super().create(request, *args, **kwargs)

    def update(self, request, *args, **kwargs):
        """
        Update a chain store instance.
        """

        user = request.user
        request.data["purchaser"] = Purchaser.objects.get(user=user).id
        return super().update(request, *args, **kwargs)


class OrderViewSet(ModelViewSet):
    """
    ViewSet class to provide CRUD operations with order instances
    """
    queryset = Order.objects.all()
    serializer_class = OrderSerializer
    http_method_names = ["post", "patch", "get", "delete"]

    def get_queryset(self):
        """
        Get the list of order items for view.
        """

        assert self.queryset is not None, (
            "'%s' should either include a `queryset` attribute, "
            "or override the `get_queryset()` method." % self.__class__.__name__
        )

        queryset = self.queryset
        if isinstance(queryset, QuerySet):
            queryset = queryset.all()
        if self.request.user.is_superuser:
            return queryset.select_related("chain_store").prefetch_related(
                "order_positions",
                "order_positions__stock",
                "order_positions__stock__product_characteristics",
            )
        if self.request.user.type == "purchaser":
            return (
                queryset.filter(purchaser__user=self.request.user)
                .select_related("chain_store")
                .prefetch_related(
                    "order_positions",
                    "order_positions__stock",
                    "order_positions__stock__product_characteristics",
                )
            )
        if self.request.user.type == "supplier":
            return (
                queryset.filter(
                    order_positions__stock__supplier__user=self.request.user
                )
                .distinct()
                .select_related("chain_store")
                .prefetch_related(
                    "order_positions",
                    "order_positions__stock",
                    "order_positions__stock__product_characteristics",
                )
            )

    def get_permissions(self):
        """
        Instantiates and returns the list of permissions that this view requires.
        """

        if self.action == "list":
            return [IsAuthenticated()]
        if self.action == "retrieve":
            RetrievePerm = IsAdmin | IsPurchaserOwner | IsOrderStockOwner
            return [RetrievePerm()]
        if self.action in ["destroy", "update", "partial_update"]:
            return [IsPurchaserOwner()]
        if self.action == "create":
            return [IsPurchaser()]
        return []

    def create(self, request, *args, **kwargs):
        """
        Create an order instance and order position instances based on shopping cart instance and cart position
        instances
        """

        user = request.user
        if not Purchaser.objects.filter(user=user).exists():
            return Response(
                {
                    "error": "you need to create Purchaser before you create or update Orders"
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        purchaser = Purchaser.objects.get(user=user)
        cart_positions = purchaser.shopping_cart.cart_positions.all()
        if not cart_positions.count():
            return Response(
                {"error": "Your shopping cart is empty"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        request.data["purchaser"] = purchaser.id

        serializer = OrderCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        if (
            ChainStore.objects.get(id=request.data["chain_store"]).purchaser
            != purchaser
        ):
            return Response(
                {"error": "Your can order delivery only to your chain stores"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)

        order = Order.objects.get(id=serializer.data["id"])
        suppliers = {}
        for position in cart_positions:
            new_position = OrderPosition.objects.create(
                order=order,
                stock=position.stock,
                quantity=position.quantity,
                price=position.price,
            )
            if new_position.stock.supplier.user not in suppliers:
                suppliers[new_position.stock.supplier.user] = [
                    {
                        "id": new_position.id,
                        "order": order.id,
                        "stock": new_position.stock,
                        "quantity": new_position.quantity,
                        "price": new_position.price,
                    }
                ]
            else:
                suppliers[new_position.stock.supplier.user].append(
                    {
                        "id": new_position.id,
                        "order": order.id,
                        "stock": new_position.stock,
                        "quantity": new_position.quantity,
                        "price": new_position.price,
                    }
                )

        cart_positions.delete()
        for supplier, positions in suppliers.items():
            text = "You have new orders\n"
            for position in positions:
                text += f'''Order #{position["order"]}, stock {position["stock"].product.name}, 
                quantity {position["quantity"]}, price {position["price"]}\n'''
            text += "Use application to confirm orders"
            send_email.delay("New order", text, supplier.email)

        response = serializer.data.copy()
        response["total_quantity"] = order.total_quantity
        response["total_amount"] = order.total_amount
        send_email.delay(
            "New order",
            f"""Thank you for your order.
            You have created new order #{response["id"]} to chain store {response["chain_store"]} 
            for total amount of {response["total_amount"]}
            Status of your order will automatically update after suppliers confirmations""",
            user.email
        )
        return Response(response, status=status.HTTP_201_CREATED, headers=headers)

    def destroy(self, request, *args, **kwargs):
        """
        Set to cancelled an order instance.
        """

        instance = self.get_object()

        if instance.status == "cancelled":
            return Response(
                {"error": "Order is already cancelled"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        for position in instance.order_positions.all():
            if position.confirmed or position.delivered:
                return Response(
                    {
                        "error": "Your can cancel only fully unconfirmed and undelivered orders"
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

        instance.status = "cancelled"
        instance.save()

        for position in instance.order_positions.all():
            stock = Stock.objects.get(id=position.stock.id)
            stock.quantity += position.quantity
            stock.save()
        return Response({"success": "Order cancelled"}, status.HTTP_200_OK)

    def update(self, request, *args, **kwargs):
        """
        Update an order instance.
        """

        instance = self.get_object()
        if instance.status == "cancelled":
            return Response(
                {"error": "Your cannot amend cancelled order"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        for position in instance.order_positions.all():
            if position.confirmed or position.delivered:
                return Response(
                    {
                        "error": "Your can amend only fully unconfirmed and undelivered orders"
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )
        if "purchaser" in request.data:
            return Response(
                {"error": "Purchaser cannot be amended"},
                status=status.HTTP_403_FORBIDDEN,
            )

        partial = kwargs.pop("partial", False)

        serializer = OrderCreateSerializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)

        if (
            request.data.get("chain_store")
            and ChainStore.objects.get(id=request.data["chain_store"]).purchaser.user
            != request.user
        ):
            return Response(
                {"error": "Your can order delivery only to your chain stores"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        self.perform_update(serializer)

        if getattr(instance, "_prefetched_objects_cache", None):
            instance._prefetched_objects_cache = {}

        return Response(serializer.data)


class OrderPositionViewSet(ModelViewSet):
    """
    ViewSet class to provide CRUD operations with order position instances
    """
    queryset = OrderPosition.objects.all()
    serializer_class = OrderPositionSerializer
    http_method_names = ["patch", "get"]
    filterset_fields = ["order__status"]

    def get_queryset(self):
        """
        Get the list of order position items for view.
        """

        assert self.queryset is not None, (
            "'%s' should either include a `queryset` attribute, "
            "or override the `get_queryset()` method." % self.__class__.__name__
        )

        queryset = self.queryset
        if isinstance(queryset, QuerySet):
            queryset = queryset.all()
        if self.request.user.is_superuser:
            return queryset.select_related("stock").prefetch_related(
                "stock__product_characteristics"
            )
        if self.request.user.type == "purchaser":
            return (
                queryset.filter(order__purchaser__user=self.request.user)
                .select_related("stock")
                .prefetch_related("stock__product_characteristics")
            )
        if self.request.user.type == "supplier":
            return (
                queryset.filter(stock__supplier__user=self.request.user)
                .select_related("stock")
                .prefetch_related("stock__product_characteristics")
            )

    def get_permissions(self):
        """
        Instantiates and returns the list of permissions that this view requires.
        """

        if self.action == "list":
            return [IsAuthenticated()]
        if self.action == "retrieve":
            RetrievePerm = IsAdmin | IsOrderPositionOwner | IsStockReferencedOwner
            return [RetrievePerm()]
        if self.action in ["update", "partial_update"]:
            return [IsStockReferencedOwner()]
        return []

    def update(self, request, *args, **kwargs):
        """
        Update an order position instance (confirm or/and deliver).
        """

        if "confirmed" not in request.data and "delivered" not in request.data:
            return Response(
                {"error": "You can amend confirmed or/and delivered status"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        instance = self.get_object()
        if instance.order.status == "cancelled":
            return Response(
                {"error": "You cannot confirm and deliver cancelled order positions"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        purchaser = instance.order.purchaser.user
        if "confirmed" in request.data:
            if type(request.data["confirmed"]) == bool and request.data["confirmed"]:
                if not instance.confirmed:
                    instance.confirmed = True
            elif (
                type(request.data["confirmed"]) == bool
                and not request.data["confirmed"]
            ):
                if instance.confirmed:
                    return Response(
                        {"error": "Your cannot revoke your confirmation"},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
            else:
                return Response(
                    {"confirmed": ["Must be a valid boolean."]},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        if "delivered" in request.data:
            if type(request.data["delivered"]) == bool and request.data["delivered"]:
                if not instance.delivered:
                    instance.delivered = True
            elif (
                type(request.data["delivered"]) == bool
                and not request.data["delivered"]
            ):
                if instance.delivered:
                    return Response(
                        {"error": "Your cannot revoke your delivery"},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
            else:
                return Response(
                    {"delivered": ["Must be a valid boolean."]},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        instance.save()
        return Response(
            {"success": "Оrder position successfully amended"}, status.HTTP_200_OK
        )
