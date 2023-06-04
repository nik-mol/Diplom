from django.apps import AppConfig


class ProcurementSupplyConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'procurement_supply'

    def ready(self):
        """
        Imports necessary model pre_save and post_save signals from separate file when Django starts.
        """
        import procurement_supply.signals
