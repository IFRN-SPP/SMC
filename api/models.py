from datetime import datetime, timezone

from django.db import models


class LeituraRecebida(models.Model):
    dispositivo = models.CharField(max_length=100)
    ts = models.BigIntegerField(null=True, blank=True)
    recebida_em = models.DateTimeField(auto_now_add=True)
    firmware = models.CharField(max_length=20, blank=True)
    rssi = models.IntegerField(null=True, blank=True)
    dados = models.JSONField()
    motivo = models.CharField(max_length=255, blank=True)

    class Meta:
        verbose_name = 'leitura recebida'
        verbose_name_plural = 'leituras recebidas'
        ordering = ['-recebida_em', '-ts']

    def data_hora(self):
        if self.ts is None:
            return None
        return datetime.fromtimestamp(self.ts, tz=timezone.utc)

    def __str__(self):
        return f'{self.dispositivo} - {self.ts}'
