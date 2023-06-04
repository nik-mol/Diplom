from rest_framework.permissions import BasePermission


class IsPurchaser(BasePermission):
    """
    Permission class to grant permissions to user whose type is 'purchaser'
    """

    def has_permission(self, request, view):
        """
        Return `True` if permission is granted, `False` otherwise.
        """
        if request.user.is_anonymous:
            return False
        return request.user.type == "purchaser"

    def has_object_permission(self, request, view, obj):
        """
        Return `True` if permission is granted, `False` otherwise.
        """
        return request.user.type == "purchaser"


class IsSupplier(BasePermission):
    """
    Permission class to grant permissions to user whose type is 'supplier'
    """

    def has_permission(self, request, view):
        """
        Return `True` if permission is granted, `False` otherwise.
        """
        if request.user.is_anonymous:
            return False
        return request.user.type == "supplier"

    def has_object_permission(self, request, view, obj):
        """
        Return `True` if permission is granted, `False` otherwise.
        """
        return request.user.type == "supplier"


class IsAdmin(BasePermission):
    """
    Permission class to grant permissions to user whose 'is_superuser' status is True
    """

    def has_permission(self, request, view):
        """
        Return `True` if permission is granted, `False` otherwise.
        """
        if request.user.is_anonymous:
            return False
        return request.user.is_superuser

    def has_object_permission(self, request, view, obj):
        """
        Return `True` if permission is granted, `False` otherwise.
        """
        return request.user.is_superuser


class IsUser(BasePermission):
    """
    Permission class to grant permissions on user instances
    """

    def has_permission(self, request, view):
        """
        Return `True` if permission is granted, `False` otherwise.
        """
        if request.user.is_anonymous:
            return False
        return True

    def has_object_permission(self, request, view, obj):
        """
        Return `True` if permission is granted, `False` otherwise.
        """
        return request.user == obj


class IsOwner(BasePermission):
    """
    Permission class to grant permissions on instances referred to user
    """

    def has_permission(self, request, view):
        """
        Return `True` if permission is granted, `False` otherwise.
        """
        if request.user.is_anonymous:
            return False
        return True

    def has_object_permission(self, request, view, obj):
        """
        Return `True` if permission is granted, `False` otherwise.
        """
        return request.user == obj.user


class IsStockOwner(BasePermission):
    """
    Permission class to grant permissions on stock instances to user owning their supplier instance
    """

    def has_permission(self, request, view):
        """
        Return `True` if permission is granted, `False` otherwise.
        """
        if request.user.is_anonymous:
            return False
        if request.user.type == "supplier":
            return True
        return False

    def has_object_permission(self, request, view, obj):
        """
        Return `True` if permission is granted, `False` otherwise.
        """
        return request.user == obj.supplier.user


class IsStockReferencedOwner(BasePermission):
    """
    Permission class to grant permissions on stock referring instances to user owning this stock purchaser instance
    """

    def has_permission(self, request, view):
        """
        Return `True` if permission is granted, `False` otherwise.
        """
        if request.user.is_anonymous:
            return False
        if request.user.type == "supplier":
            return True
        return False

    def has_object_permission(self, request, view, obj):
        """
        Return `True` if permission is granted, `False` otherwise.
        """
        return request.user == obj.stock.supplier.user


class IsPurchaserOwner(BasePermission):
    """
    Permission class to grant permissions on instances to user owning their purchaser instance
    """

    def has_permission(self, request, view):
        """
        Return `True` if permission is granted, `False` otherwise.
        """
        if request.user.is_anonymous:
            return False
        if request.user.type == "purchaser":
            return True
        return False

    def has_object_permission(self, request, view, obj):
        """
        Return `True` if permission is granted, `False` otherwise.
        """
        return request.user == obj.purchaser.user


class IsCartStockOwner(BasePermission):
    """
    Permission class to grant permissions on cart to supplier, which is owner of at least one position from cart
    """

    def has_permission(self, request, view):
        """
        Return `True` if permission is granted, `False` otherwise.
        """
        if request.user.is_anonymous:
            return False
        if request.user.type == "supplier":
            return True
        return False

    def has_object_permission(self, request, view, obj):
        """
        Return `True` if permission is granted, `False` otherwise.
        """
        for position in obj.cart_positions.all():
            if position.stock.supplier.user == request.user:
                return True
        return False


class IsCartPositionOwner(BasePermission):
    """
    Permission class to grant permissions on cart positions to purchaser, which is owner of cart
    """

    def has_permission(self, request, view):
        """
        Return `True` if permission is granted, `False` otherwise.
        """
        if request.user.is_anonymous:
            return False
        if request.user.type == "purchaser":
            return True
        return False

    def has_object_permission(self, request, view, obj):
        """
        Return `True` if permission is granted, `False` otherwise.
        """
        return request.user == obj.shopping_cart.purchaser.user


class IsOrderStockOwner(BasePermission):
    """
    Permission class to grant permissions on order to supplier, which is owner of at least one position from order
    """

    def has_permission(self, request, view):
        """
        Return `True` if permission is granted, `False` otherwise.
        """
        if request.user.is_anonymous:
            return False
        if request.user.type == "supplier":
            return True
        return False

    def has_object_permission(self, request, view, obj):
        """
        Return `True` if permission is granted, `False` otherwise.
        """
        for position in obj.order_positions.all():
            if position.stock.supplier.user == request.user:
                return True
        return False


class IsOrderPositionOwner(BasePermission):
    """
    Permission class to grant permissions on order positions to purchaser, which is owner of order
    """

    def has_permission(self, request, view):
        """
        Return `True` if permission is granted, `False` otherwise.
        """
        if request.user.is_anonymous:
            return False
        if request.user.type == "purchaser":
            return True
        return False

    def has_object_permission(self, request, view, obj):
        """
        Return `True` if permission is granted, `False` otherwise.
        """
        return request.user == obj.order.purchaser.user
