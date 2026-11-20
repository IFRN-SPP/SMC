from datetime import date

from django.contrib.auth.models import Group, User
from django.test import TestCase, override_settings
from django.urls import reverse

from .models import (
    Cisterna,
    Dispositivo,
    LeituraTelemetria,
    Localidade,
    Municipio,
    Participante,
)


class SMCBaseTestCase(TestCase):
    def setUp(self):
        self.grupo_admin = Group.objects.create(name='Administrador do sistema')
        self.admin = User.objects.create_user(
            username='admin_teste',
            password='SenhaForte123!',
            email='admin@teste.com',
        )
        self.admin.groups.add(self.grupo_admin)
        self.municipio = Municipio.objects.create(nome='Teste', estado='RN')
        self.localidade = Localidade.objects.create(nome='Comunidade teste')
        self.participante = Participante.objects.create(nome='Pessoa teste')
        self.cisterna = Cisterna.objects.create(
            identificacao='CISTERNA-TESTE',
            municipio=self.municipio,
            localidade=self.localidade,
            participante=self.participante,
        )

    def autenticar_admin(self):
        self.client.force_login(self.admin)


class AutenticacaoETestesDeAcesso(SMCBaseTestCase):
    def test_pagina_protegida_redireciona_usuario_deslogado(self):
        resposta = self.client.get(reverse('lista_usuarios'))
        self.assertEqual(resposta.status_code, 302)
        self.assertIn('/login/', resposta.url)

    def test_usuario_admin_acessa_lista_de_usuarios(self):
        self.autenticar_admin()
        resposta = self.client.get(reverse('lista_usuarios'))
        self.assertEqual(resposta.status_code, 200)

    def test_usuario_sem_perfil_admin_recebe_403(self):
        usuario = User.objects.create_user(username='leitor', password='SenhaForte123!')
        self.client.force_login(usuario)
        resposta = self.client.get(reverse('lista_usuarios'))
        self.assertEqual(resposta.status_code, 403)


class CRUDMunicipios(SMCBaseTestCase):
    def test_editar_municipio(self):
        self.autenticar_admin()
        resposta = self.client.post(
            reverse('editar_municipio', args=[self.municipio.pk]),
            {'nome': 'Cidade alterada', 'estado': 'rn'},
        )
        self.assertEqual(resposta.status_code, 302)
        self.municipio.refresh_from_db()
        self.assertEqual(self.municipio.nome, 'Cidade alterada')
        self.assertEqual(self.municipio.estado, 'RN')

    def test_excluir_municipio_sem_cisterna(self):
        self.autenticar_admin()
        outro = Municipio.objects.create(nome='Outro', estado='PB')
        resposta = self.client.post(reverse('excluir_municipio', args=[outro.pk]))
        self.assertEqual(resposta.status_code, 302)
        self.assertFalse(Municipio.objects.filter(pk=outro.pk).exists())

    def test_bloqueia_exclusao_de_municipio_com_cisterna(self):
        self.autenticar_admin()
        resposta = self.client.post(reverse('excluir_municipio', args=[self.municipio.pk]))
        self.assertEqual(resposta.status_code, 400)
        self.assertTrue(Municipio.objects.filter(pk=self.municipio.pk).exists())


class CRUDDispositivos(SMCBaseTestCase):
    def setUp(self):
        super().setUp()
        self.dispositivo = Dispositivo.objects.create(
            identificacao='SENSOR-TESTE',
            tipo_sensor='Ultrassônico',
            cisterna=self.cisterna,
            data_instalacao=date(2026, 1, 1),
            situacao='ativo',
        )

    def test_editar_dispositivo(self):
        self.autenticar_admin()
        resposta = self.client.post(
            reverse('editar_dispositivo', args=[self.dispositivo.pk]),
            {
                'identificacao': 'SENSOR-ALTERADO',
                'tipo_sensor': 'Ultrassônico',
                'cisterna': self.cisterna.pk,
                'data_instalacao': '2026-01-01',
                'situacao': 'ativo',
            },
        )
        self.assertEqual(resposta.status_code, 302)
        self.dispositivo.refresh_from_db()
        self.assertEqual(self.dispositivo.identificacao, 'SENSOR-ALTERADO')

    def test_excluir_dispositivo(self):
        self.autenticar_admin()
        resposta = self.client.post(reverse('excluir_dispositivo', args=[self.dispositivo.pk]))
        self.assertEqual(resposta.status_code, 302)
        self.assertFalse(Dispositivo.objects.filter(pk=self.dispositivo.pk).exists())


class CRUDUsuarios(SMCBaseTestCase):
    def test_editar_usuario(self):
        self.autenticar_admin()
        usuario = User.objects.create_user(username='operador', password='SenhaForte123!')
        resposta = self.client.post(
            reverse('editar_usuario', args=[usuario.pk]),
            {
                'first_name': 'Maria',
                'last_name': 'Silva',
                'username': 'operador',
                'email': 'maria@teste.com',
                'perfil': 'Operador-técnico',
                'is_active': 'on',
                'nova_senha': '',
                'confirmar_senha': '',
            },
        )
        self.assertEqual(resposta.status_code, 302)
        usuario.refresh_from_db()
        self.assertEqual(usuario.email, 'maria@teste.com')
        self.assertTrue(usuario.groups.filter(name='Operador-técnico').exists())

    def test_excluir_usuario(self):
        self.autenticar_admin()
        usuario = User.objects.create_user(username='remover', password='SenhaForte123!')
        resposta = self.client.post(reverse('excluir_usuario', args=[usuario.pk]))
        self.assertEqual(resposta.status_code, 302)
        self.assertFalse(User.objects.filter(pk=usuario.pk).exists())

    def test_impede_excluir_propria_conta(self):
        self.autenticar_admin()
        resposta = self.client.post(reverse('excluir_usuario', args=[self.admin.pk]))
        self.assertEqual(resposta.status_code, 403)
        self.assertTrue(User.objects.filter(pk=self.admin.pk).exists())


class APILeituras(SMCBaseTestCase):
    @override_settings(DEVICE_API_TOKEN='smc-dev-token', EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
    def test_rejeita_dispositivo_sem_token(self):
        resposta = self.client.post(
            reverse('receber_leitura'),
            {'identificacao': 'SENSOR-NAO-EXISTE', 'nivel': '50'},
        )
        self.assertEqual(resposta.status_code, 403)

    @override_settings(DEVICE_API_TOKEN='smc-dev-token', EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
    def test_rejeita_nivel_fora_da_faixa(self):
        resposta = self.client.post(
            reverse('receber_leitura'),
            {'identificacao': 'SENSOR-NAO-EXISTE', 'nivel': '101'},
            HTTP_X_DEVICE_TOKEN='smc-dev-token',
        )
        self.assertEqual(resposta.status_code, 400)


@override_settings(
    DEVICE_API_TOKEN='smc-dev-token',
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
)
class SensoresDaLeitura(SMCBaseTestCase):
    def setUp(self):
        super().setUp()
        self.dispositivo = Dispositivo.objects.create(
            identificacao='SENSOR-COMPLETO',
            tipo_sensor='Multissensor',
            cisterna=self.cisterna,
            data_instalacao=date(2026, 1, 1),
            situacao='ativo',
        )

    def enviar(self, **dados):
        payload = {'identificacao': 'SENSOR-COMPLETO', 'nivel': '80'}
        payload.update(dados)
        return self.client.post(
            reverse('receber_leitura'),
            payload,
            HTTP_X_DEVICE_TOKEN='smc-dev-token',
        )

    def test_api_salva_todos_os_sensores(self):
        resposta = self.enviar(
            temperatura_agua='27.4',
            temperatura_ar='31.2',
            umidade_ar='58',
            qualidade_agua_ppm='312',
            tensao_bateria='12.6',
            tensao_placa_solar='17.8',
        )
        self.assertEqual(resposta.status_code, 201)

        leitura = LeituraTelemetria.objects.get()
        self.assertEqual(leitura.temperatura_agua, 27.4)
        self.assertEqual(leitura.temperatura_ar, 31.2)
        self.assertEqual(leitura.umidade_ar, 58)
        self.assertEqual(leitura.qualidade_agua_ppm, 312)
        self.assertEqual(leitura.tensao_bateria, 12.6)
        self.assertEqual(leitura.tensao_placa_solar, 17.8)

    def test_api_continua_aceitando_leitura_so_com_nivel(self):
        resposta = self.enviar()
        self.assertEqual(resposta.status_code, 201)

        leitura = LeituraTelemetria.objects.get()
        self.assertIsNone(leitura.temperatura_agua)
        self.assertIsNone(leitura.tensao_bateria)

    def test_api_aceita_virgula_decimal_e_campo_vazio(self):
        resposta = self.enviar(temperatura_agua='27,4', umidade_ar='')
        self.assertEqual(resposta.status_code, 201)

        leitura = LeituraTelemetria.objects.get()
        self.assertEqual(leitura.temperatura_agua, 27.4)
        self.assertIsNone(leitura.umidade_ar)

    def test_api_rejeita_umidade_fora_da_faixa(self):
        resposta = self.enviar(umidade_ar='120')
        self.assertEqual(resposta.status_code, 400)
        self.assertEqual(LeituraTelemetria.objects.count(), 0)

    def test_api_rejeita_tensao_negativa(self):
        resposta = self.enviar(tensao_bateria='-1')
        self.assertEqual(resposta.status_code, 400)

    def test_api_rejeita_valor_nao_numerico(self):
        resposta = self.enviar(temperatura_ar='abc')
        self.assertEqual(resposta.status_code, 400)

    def test_api_rejeita_nan(self):
        resposta = self.enviar(qualidade_agua_ppm='nan')
        self.assertEqual(resposta.status_code, 400)

    def test_model_rejeita_sensor_fora_da_faixa(self):
        from django.utils import timezone

        with self.assertRaises(ValueError):
            LeituraTelemetria.objects.create(
                cisterna=self.cisterna,
                nivel=50,
                data_hora=timezone.now(),
                umidade_ar=101,
            )

    def test_monitoramento_exibe_sensores(self):
        from django.utils import timezone

        LeituraTelemetria.objects.create(
            cisterna=self.cisterna,
            nivel=80,
            data_hora=timezone.now(),
            temperatura_agua=27.4,
            tensao_bateria=12.6,
        )
        self.autenticar_admin()
        resposta = self.client.get(reverse('monitoramento'))
        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, 'Temp. da água')
        self.assertContains(resposta, '27,4')

    def test_painel_inicial_exibe_resumo_dos_sensores(self):
        from django.utils import timezone

        LeituraTelemetria.objects.create(
            cisterna=self.cisterna,
            nivel=80,
            data_hora=timezone.now(),
            umidade_ar=58,
        )
        self.autenticar_admin()
        resposta = self.client.get(reverse('index'))
        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, 'Sensores das cisternas')