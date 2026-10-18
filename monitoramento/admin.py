
from django.contrib import admin

from .models import (
    Participante,
    Municipio,
    Localidade,
    Cisterna,
    Dispositivo,
    LeituraTelemetria,
    Alerta,
    PerfilUsuario,
)


admin.site.register(Participante)
admin.site.register(Municipio)
admin.site.register(Localidade)
admin.site.register(Cisterna)
admin.site.register(Dispositivo)
admin.site.register(LeituraTelemetria)
admin.site.register(Alerta)
admin.site.register(PerfilUsuario)
