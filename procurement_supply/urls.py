"""order_service URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/4.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from django.urls import path
from rest_framework.authtoken.views import obtain_auth_token
from rest_framework.routers import DefaultRouter

from procurement_supply.views import (CartPositionViewSet, CategoryViewSet,
                                      ChainStoreViewSet, CharacteristicViewSet,
                                      ImportView, OrderPositionViewSet,
                                      OrderViewSet, PasswordResetView,
                                      ProductCharacteristicViewSet,
                                      ProductViewSet, PurchaserViewSet,
                                      ShoppingCartViewSet, StockViewSet,
                                      SupplierViewSet, UserViewSet, ImportCheckView)

app_name = "procurement_supply"
r = DefaultRouter()
r.register("users", UserViewSet)
r.register("suppliers", SupplierViewSet)
r.register("categories", CategoryViewSet)
r.register("products", ProductViewSet)
r.register("characteristics", CharacteristicViewSet)
r.register("stocks", StockViewSet)
r.register("product_characteristics", ProductCharacteristicViewSet)
r.register("purchasers", PurchaserViewSet)
r.register("cart_positions", CartPositionViewSet)
r.register("shopping_carts", ShoppingCartViewSet)
r.register("chain_stores", ChainStoreViewSet)
r.register("orders", OrderViewSet)
r.register("order_positions", OrderPositionViewSet)
urlpatterns = [
    path("authorize/", obtain_auth_token),
    path("password_reset/", PasswordResetView.as_view()),
    path("import/", ImportView.as_view()),
    path("import/<str:task_id>/", ImportCheckView.as_view()),
] + r.urls
