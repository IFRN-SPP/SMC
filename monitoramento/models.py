
import math
import secrets

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


class Participante(models.Model):
    nome = models.CharField(max_length=150)

    def __str__(self):
        return self.nome


class Municipio(models.Model):
    nome = models.CharField(max_length=150)
    estado = models.CharField(max_length=2)

    def __str__(self):
        return f"{self.nome} - {self.estado}"


class Localidade(models.Model):
    nome = models.CharField(max_length=150)

    municipio = models.CharField(
        max_length=150,
        blank=True,
        null=True
    )

    endereco = models.CharField(
        max_length=255,
        blank=True
    )

    descricao = models.TextField(
        blank=True
    )

    def __str__(self):
        if self.municipio:
            return f"{self.nome} - {self.municipio}"
        return self.nome


class Cisterna(models.Model):
    SITUACAO_CHOICES = [
        ('normal', 'Normal'),
        ('atencao', 'Atenção'),
        ('critico', 'Crítico'),
        ('sem_dados', 'Sem dados'),
    ]

    participante = models.ForeignKey(
        Participante,
        on_delete=models.CASCADE,
        related_name="cisternas"
    )

    municipio = models.ForeignKey(
        Municipio,
        on_delete=models.CASCADE,
        related_name="cisternas",
        null=True,
        blank=True
    )

    localidade = models.ForeignKey(
        Localidade,
        on_delete=models.CASCADE,
        related_name="cisternas"
    )

    identificacao = models.CharField(max_length=100)

    latitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True
    )

    longitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True
    )

    capacidade_total = models.PositiveIntegerField(
        null=True,
        blank=True
    )

    situacao = models.CharField(
        max_length=20,
        choices=SITUACAO_CHOICES,
        default='sem_dados'
    )

    imagem = models.ImageField(
        upload_to='cisternas/',
        null=True,
        blank=True
    )

    def __str__(self):
        return self.identificacao


class Dispositivo(models.Model):
    SITUACAO_CHOICES = [
        ('ativo', 'Ativo'),
        ('inativo', 'Inativo'),
        ('manutencao', 'Em manutenção'),
    ]

    identificacao = models.CharField(
        max_length=100,
        unique=True
    )

    tipo_sensor = models.CharField(max_length=100)

    cisterna = models.ForeignKey(
        Cisterna,
        on_delete=models.CASCADE,
        related_name="dispositivos"
    )

    data_instalacao = models.DateField()

    situacao = models.CharField(
        max_length=20,
        choices=SITUACAO_CHOICES,
        default='ativo'
    )

    distancia_vazia_cm = models.FloatField(
        'Distância do sensor ao fundo (cm)',
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
        help_text='Medida com a cisterna vazia. Corresponde a nível 0%.',
    )

    distancia_cheia_cm = models.FloatField(
        'Distância do sensor ao nível máximo (cm)',
        null=True,
        blank=True,
        validators=[MinValueValidator(20)],
        help_text='Medida com a cisterna cheia. Corresponde a nível 100%. '
                  'Mínimo de 20 cm (zona cega do sensor).',
    )

    fator_tds = models.FloatField(
        'Fator de calibração do TDS',
        default=1.0,
        validators=[MinValueValidator(0)],
        help_text='Valor real / valor calculado, com uma solução de referência.',
    )

    token = models.CharField(
        'Token de acesso',
        max_length=64,
        blank=True,
        help_text='Gerado automaticamente. Apague e salve para gerar outro.',
    )

    def save(self, *args, **kwargs):
        if not self.token:
            self.token = secrets.token_urlsafe(24)
        super().save(*args, **kwargs)

    def calibrado(self):
        return (
            self.distancia_vazia_cm is not None
            and self.distancia_cheia_cm is not None
            and self.distancia_vazia_cm > self.distancia_cheia_cm
        )

    def __str__(self):
        return self.identificacao



class LeituraTelemetria(models.Model):
    cisterna = models.ForeignKey(
        Cisterna,
        on_delete=models.CASCADE,
        related_name="leituras"
    )

    dispositivo = models.ForeignKey(
        Dispositivo,
        on_delete=models.SET_NULL,
        related_name="leituras",
        null=True,
        blank=True
    )

    nivel = models.FloatField()
    data_hora = models.DateTimeField()

    # Sensores adicionais. Todos são opcionais (null) porque leituras antigas,
    # ou dispositivos que ainda não possuem o sensor, enviam apenas o nível.
    temperatura_agua = models.FloatField(
        'Temperatura da água (°C)',
        null=True,
        blank=True,
        validators=[MinValueValidator(-55), MaxValueValidator(125)],
    )

    temperatura_ar = models.FloatField(
        'Temperatura do ar (°C)',
        null=True,
        blank=True,
        validators=[MinValueValidator(-55), MaxValueValidator(125)],
    )

    umidade_ar = models.FloatField(
        'Umidade relativa do ar (%)',
        null=True,
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
    )

    qualidade_agua_ppm = models.FloatField(
        'Qualidade da água (ppm)',
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
    )

    tensao_bateria = models.FloatField(
        'Tensão da bateria (V)',
        null=True,
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
    )

    tensao_placa_solar = models.FloatField(
        'Tensão da placa solar (V)',
        null=True,
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
    )

    # Fonte única de rótulos, unidades e faixas válidas dos sensores.
    # É usada pela validação do save(), pela API e pelas telas do dashboard.
    # "maximo" None significa sem limite superior.
    CAMPOS_SENSORES = {
        'temperatura_agua': {
            'rotulo': 'Temperatura da água', 'curto': 'Temp. da água',
            'unidade': '°C', 'minimo': -55, 'maximo': 125, 'casas': 1,
        },
        'temperatura_ar': {
            'rotulo': 'Temperatura do ar', 'curto': 'Temp. do ar',
            'unidade': '°C', 'minimo': -55, 'maximo': 125, 'casas': 1,
        },
        'umidade_ar': {
            'rotulo': 'Umidade relativa do ar', 'curto': 'Umidade do ar',
            'unidade': '%', 'minimo': 0, 'maximo': 100, 'casas': 0,
        },
        'qualidade_agua_ppm': {
            'rotulo': 'Qualidade da água', 'curto': 'Qualidade da água',
            'unidade': 'ppm', 'minimo': 0, 'maximo': None, 'casas': 0,
        },
        'tensao_bateria': {
            'rotulo': 'Tensão da bateria', 'curto': 'Bateria',
            'unidade': 'V', 'minimo': 0, 'maximo': 100, 'casas': 2,
        },
        'tensao_placa_solar': {
            'rotulo': 'Tensão da placa solar', 'curto': 'Placa solar',
            'unidade': 'V', 'minimo': 0, 'maximo': 100, 'casas': 2,
        },
    }

    @classmethod
    def valor_sensor_valido(cls, campo, valor):
        """Diz se o valor está dentro da faixa permitida para o sensor."""
        faixa = cls.CAMPOS_SENSORES[campo]

        if not math.isfinite(valor) or valor < faixa['minimo']:
            return False

        return faixa['maximo'] is None or valor <= faixa['maximo']

    def __str__(self):
        return f"{self.cisterna} - {self.data_hora}"

    def save(self, *args, **kwargs):
        nova_leitura = self.pk is None

        if not 0 <= self.nivel <= 100:
            raise ValueError("O nível deve estar entre 0 e 100.")

        for campo, faixa in self.CAMPOS_SENSORES.items():
            valor = getattr(self, campo)

            if valor is not None and not self.valor_sensor_valido(campo, valor):
                raise ValueError(
                    f"{faixa['rotulo']} fora da faixa permitida."
                )

        leitura_anterior = None

        if nova_leitura:
            leitura_anterior = (
                LeituraTelemetria.objects
                .filter(cisterna=self.cisterna)
                .order_by('-data_hora', '-pk')
                .first()
            )

        super().save(*args, **kwargs)

        if self.nivel >= 70:
            nova_situacao = 'normal'
        elif self.nivel >= 30:
            nova_situacao = 'atencao'
        else:
            nova_situacao = 'critico'

        Cisterna.objects.filter(pk=self.cisterna_id).update(
            situacao=nova_situacao
        )

        self.cisterna.situacao = nova_situacao

        if not nova_leitura:
            return

        situacao_anterior = None

        if leitura_anterior:
            if leitura_anterior.nivel >= 70:
                situacao_anterior = 'normal'
            elif leitura_anterior.nivel >= 30:
                situacao_anterior = 'atencao'
            else:
                situacao_anterior = 'critico'

        entrou_em_atencao = (
            nova_situacao == 'atencao'
            and situacao_anterior != 'atencao'
        )

        entrou_em_critico = (
            nova_situacao == 'critico'
            and situacao_anterior != 'critico'
        )

        if entrou_em_atencao or entrou_em_critico:
            tipo_alerta = (
                'critico' if entrou_em_critico else 'atencao'
            )

            alerta = Alerta.objects.create(
                cisterna=self.cisterna,
                tipo=tipo_alerta,
                mensagem=(
                    f"Nível {'crítico' if tipo_alerta == 'critico' else 'de atenção'} "
                    f"de água: {self.nivel:.1f}%."
                ),
                data_hora=self.data_hora
            )

            if tipo_alerta == 'critico':
                from .notificacoes import enviar_email_alerta

                enviar_email_alerta(alerta)



class Alerta(models.Model):
    TIPO_CHOICES = [
        ('atencao', 'Atenção'),
        ('critico', 'Crítico'),
    ]

    cisterna = models.ForeignKey(
        Cisterna,
        on_delete=models.CASCADE,
        related_name="alertas"
    )

    tipo = models.CharField(
        max_length=20,
        choices=TIPO_CHOICES,
        default='critico'
    )

    mensagem = models.CharField(max_length=255)
    data_hora = models.DateTimeField()

    resolvido = models.BooleanField(default=False)
    resolvido_em = models.DateTimeField(
        null=True,
        blank=True
    )

    def __str__(self):
        return self.mensagem

class PerfilUsuario(models.Model):
    usuario = models.OneToOneField(
        'auth.User',
        on_delete=models.CASCADE,
        related_name='perfil_municipal'
    )

    municipio = models.ForeignKey(
        Municipio,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='usuarios'
    )

    def __str__(self):
        return self.usuario.username