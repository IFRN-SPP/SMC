from django.contrib import admin

from .models import LeituraRecebida


@admin.register(LeituraRecebida)
class LeituraRecebidaAdmin(admin.ModelAdmin):
    list_display = ['dispositivo', 'data_hora', 'recebida_em', 'motivo', 'rssi', 'firmware']
    list_filter = ['dispositivo', 'motivo']
    readonly_fields = ['recebida_em']
