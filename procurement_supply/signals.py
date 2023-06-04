from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from procurement_supply.models import OrderPosition, User
from procurement_supply.tasks import send_email


@receiver(pre_save, sender=OrderPosition)
def cache_previous_order_position_status(sender, instance, **kwargs):
    """
    Save previous confirmed and delivered OrderPosition status in order to post_save check whether it was changed or not
    """

    if instance.id:
        order_position = sender.objects.get(pk=instance.id)
        instance.__original_confirmed = order_position.confirmed
        instance.__original_delivered = order_position.delivered


@receiver(post_save, sender=OrderPosition)
def send_email_change_order_pos_status(sender, instance, created, **kwargs):
    """
    Compares new and previous confirmation and delivery status and sends to purchaser the corresponding notification
    """

    if not created:
        if (instance.__original_confirmed == instance.confirmed) \
                and (instance.__original_delivered == instance.delivered):
            return
        if (instance.__original_confirmed and not instance.confirmed) \
                or (instance.__original_delivered and not instance.delivered):
            send_email.delay(
                "Order position confirmation and/or delivery status revoked",
                f'''Please contact supplier of position {instance.id} from your order #{instance.order.id}.
                 Confirmation and/or delivery status or both of this position was revoked through admin site''',
                instance.order.purchaser.user.email,
            )
            return
        text = f'Your order #{instance.order.id} position {instance.id} was\n'
        if not instance.__original_confirmed and instance.confirmed:
            text += '- confirmed\n'
        if not instance.__original_delivered and instance.delivered:
            text += '- delivered\n'
        text += """by supplier.
        Order is confirmed when all positions are confirmed and delivered after all position are delivered"""
        send_email.delay(
            "Order position confirmation and/or delivery status changed",
            text,
            instance.order.purchaser.user.email
        )


@receiver(post_save, sender=User)
def send_email_new_user(sender, instance, created, **kwargs):
    """
    Sends user a welcome email after registration
    """

    if created:
        send_email.delay(
            "Welcome to our site",
            f"""Thank you for your registration, {instance.username}.""",
            instance.email
        )
