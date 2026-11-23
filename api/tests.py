import json
from datetime import date

from django.test import TestCase, override_settings
from django.urls import reverse

from api.models import LeituraRecebida
from monitoramento.models import (
    Cisterna,
    Dispositivo,
    LeituraTelemetria,
    Localidade,
    Participante,
)


LEITURA = {
    'ts': 1759921200,
    'air_temp_c': 31.42,
    'air_rh_pct': 38.7,
    'water_temp_c': 27.06,
    'tds_mv': 412,
    'echo_us': 4920,
    'battery_mv': 1990,
    'solar_mv': 1810,
}


@override_settings(
    DEVICE_API_TOKEN='smc-dev-token',
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
)
class ReceberLeituras(TestCase):
    def setUp(self):
        cisterna = Cisterna.objects.create(
            identificacao='CISTERNA-TESTE',
            localidade=Localidade.objects.create(nome='Comunidade teste'),
            participante=Participante.objects.create(nome='Pessoa teste'),
        )
        self.dispositivo = Dispositivo.objects.create(
            identificacao='smc-a1b2c3',
            tipo_sensor='Data logger SMC',
            cisterna=cisterna,
            data_instalacao=date(2026, 1, 1),
            distancia_vazia_cm=200,
            distancia_cheia_cm=20,
        )

    def enviar(self, leituras, device_id='smc-a1b2c3', token='smc-dev-token'):
        corpo = {'device_id': device_id, 'fw': '0.1.0', 'rssi': -71, 'readings': leituras}
        return self.client.post(
            reverse('api_leituras'),
            json.dumps(corpo),
            content_type='application/json',
            HTTP_AUTHORIZATION=f'Bearer {token}',
        )

    def test_salva_leitura_convertida(self):
        resposta = self.enviar([LEITURA])
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.json(), {'salvas': 1, 'ignoradas': 0})

        leitura = LeituraTelemetria.objects.get()
        self.assertEqual(leitura.dispositivo, self.dispositivo)
        self.assertEqual(leitura.data_hora.timestamp(), 1759921200)
        self.assertAlmostEqual(leitura.nivel, 63.6, places=1)
        self.assertEqual(leitura.temperatura_agua, 27.06)
        self.assertAlmostEqual(leitura.tensao_bateria, 3.98)
        self.assertAlmostEqual(leitura.tensao_placa_solar, 5.792)
        self.assertGreater(leitura.qualidade_agua_ppm, 0)

    def test_rejeita_token_errado(self):
        resposta = self.enviar([LEITURA], token='errado')
        self.assertEqual(resposta.status_code, 401)
        self.assertEqual(LeituraTelemetria.objects.count(), 0)

    def test_rejeita_get(self):
        resposta = self.client.get(reverse('api_leituras'))
        self.assertEqual(resposta.status_code, 405)

    def test_rejeita_json_invalido(self):
        resposta = self.client.post(
            reverse('api_leituras'),
            'nao é json',
            content_type='application/json',
            HTTP_AUTHORIZATION='Bearer smc-dev-token',
        )
        self.assertEqual(resposta.status_code, 400)

    def test_dispositivo_desconhecido_retorna_404(self):
        resposta = self.enviar([LEITURA], device_id='smc-000000')
        self.assertEqual(resposta.status_code, 404)

    def test_dispositivo_sem_calibracao_retorna_409(self):
        self.dispositivo.distancia_vazia_cm = None
        self.dispositivo.save()
        resposta = self.enviar([LEITURA])
        self.assertEqual(resposta.status_code, 409)

    def test_ignora_leitura_repetida(self):
        self.enviar([LEITURA])
        resposta = self.enviar([LEITURA])
        self.assertEqual(resposta.json(), {'salvas': 0, 'ignoradas': 1})
        self.assertEqual(LeituraTelemetria.objects.count(), 1)

    def test_ignora_leitura_sem_hora_ou_sem_eco_e_aceita_o_lote(self):
        sem_hora = {**LEITURA, 'ts': None}
        sem_eco = {**LEITURA, 'ts': LEITURA['ts'] + 600, 'echo_us': None}
        with self.assertLogs('api.views', level='WARNING') as logs:
            resposta = self.enviar([sem_hora, sem_eco, {**LEITURA, 'ts': LEITURA['ts'] + 1200}])
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.json(), {'salvas': 1, 'ignoradas': 2})
        self.assertIn('sem hora', logs.output[0])
        self.assertIn('sem eco', logs.output[1])

    def test_ignora_valor_fora_da_faixa_e_aceita_o_lote(self):
        with self.assertLogs('api.views', level='WARNING') as logs:
            resposta = self.enviar([{**LEITURA, 'air_rh_pct': 150}])
        self.assertIn('fora da faixa', logs.output[0])
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.json(), {'salvas': 0, 'ignoradas': 1})

    def test_sensores_ausentes_ficam_nulos(self):
        leitura = {'ts': LEITURA['ts'], 'echo_us': 4920, 'air_temp_c': None,
                   'air_rh_pct': None, 'water_temp_c': None, 'tds_mv': None,
                   'battery_mv': None, 'solar_mv': None}
        resposta = self.enviar([leitura])
        self.assertEqual(resposta.json(), {'salvas': 1, 'ignoradas': 0})

        salva = LeituraTelemetria.objects.get()
        self.assertIsNone(salva.temperatura_agua)
        self.assertIsNone(salva.qualidade_agua_ppm)
        self.assertIsNone(salva.tensao_bateria)

    def test_atualiza_situacao_pela_leitura_mais_recente(self):
        cheia = {**LEITURA, 'ts': LEITURA['ts'] + 600, 'echo_us': 1200}
        vazia = {**LEITURA, 'echo_us': 11000}
        self.enviar([cheia, vazia])
        self.dispositivo.cisterna.refresh_from_db()
        self.assertEqual(self.dispositivo.cisterna.situacao, 'normal')

    def test_guarda_leitura_recebida_mesmo_sem_eco(self):
        self.enviar([{**LEITURA, 'echo_us': None}])
        self.assertEqual(LeituraTelemetria.objects.count(), 0)

        recebida = LeituraRecebida.objects.get()
        self.assertEqual(recebida.dispositivo, 'smc-a1b2c3')
        self.assertEqual(recebida.motivo, 'sem eco')
        self.assertEqual(recebida.rssi, -71)
        self.assertEqual(recebida.firmware, '0.1.0')
        self.assertEqual(recebida.dados['battery_mv'], 1990)
        self.assertAlmostEqual(recebida.convertidos['tensao_bateria'], 3.98)
        self.assertAlmostEqual(recebida.convertidos['tensao_placa_solar'], 5.792)
        self.assertGreater(recebida.convertidos['qualidade_agua_ppm'], 0)
        self.assertIsNone(recebida.convertidos['nivel'])

    def test_guarda_leitura_recebida_salva_sem_motivo(self):
        self.enviar([LEITURA])
        recebida = LeituraRecebida.objects.get()
        self.assertEqual(recebida.motivo, '')
        self.assertAlmostEqual(recebida.convertidos['nivel'], LeituraTelemetria.objects.get().nivel)
        self.assertAlmostEqual(recebida.convertidos['distancia_cm'], 85.53, places=2)

    def test_nao_duplica_leitura_recebida_sem_eco(self):
        self.enviar([{**LEITURA, 'echo_us': None}])
        resposta = self.enviar([{**LEITURA, 'echo_us': None}])
        self.assertEqual(resposta.json(), {'salvas': 0, 'ignoradas': 1})
        self.assertEqual(LeituraRecebida.objects.count(), 1)

    def test_dispositivo_desconhecido_nao_guarda_leitura_recebida(self):
        self.enviar([LEITURA], device_id='smc-000000')
        self.assertEqual(LeituraRecebida.objects.count(), 0)
