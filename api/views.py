import json
import logging
from datetime import datetime, timezone

from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

from monitoramento.models import Dispositivo, LeituraTelemetria


logger = logging.getLogger(__name__)

TEMPERATURA_PADRAO = 25.0


def calcular_distancia_cm(echo_us, temperatura):
    return echo_us * (331.3 + 0.606 * temperatura) / 20000


def calcular_nivel(distancia, dispositivo):
    vazia = dispositivo.distancia_vazia_cm
    cheia = dispositivo.distancia_cheia_cm
    nivel = (vazia - distancia) / (vazia - cheia) * 100

    if nivel < 0:
        return 0.0
    if nivel > 100:
        return 100.0
    return nivel


def calcular_tds_ppm(tds_mv, temperatura, fator):
    v = tds_mv / 1000 / (1 + 0.02 * (temperatura - 25))
    return (133.42 * v**3 - 255.86 * v**2 + 857.39 * v) * 0.5 * fator


def calcular_tensao(milivolts, divisor):
    if milivolts is None:
        return None
    return milivolts * divisor / 1000


# O firmware só apaga o lote com resposta 2xx. Leituras com problema são
# ignoradas com 200; um erro faria o ESP32 reenviar o lote para sempre.
@csrf_exempt
def receber_leituras(request):
    if request.method != 'POST':
        return JsonResponse({'erro': 'Método não permitido.'}, status=405)

    token_configurado = settings.DEVICE_API_TOKEN
    token_recebido = request.headers.get('Authorization', '')

    if not token_configurado or token_recebido != f'Bearer {token_configurado}':
        return JsonResponse({'erro': 'Dispositivo não autenticado.'}, status=401)

    try:
        dados = json.loads(request.body)
        identificacao = dados['device_id']
        leituras = dados['readings']
    except (ValueError, KeyError, TypeError):
        return JsonResponse({'erro': 'JSON inválido.'}, status=400)

    if not isinstance(leituras, list):
        return JsonResponse({'erro': 'JSON inválido.'}, status=400)

    dispositivo = (
        Dispositivo.objects
        .select_related('cisterna')
        .filter(identificacao=identificacao, situacao='ativo')
        .first()
    )

    if not dispositivo:
        logger.warning('Dispositivo %s não encontrado ou inativo', identificacao)
        return JsonResponse(
            {'erro': 'Dispositivo não encontrado ou está inativo.'},
            status=404,
        )

    if not dispositivo.calibrado():
        logger.warning('Dispositivo %s sem calibração', identificacao)
        return JsonResponse(
            {'erro': 'Dispositivo sem as distâncias de calibração.'},
            status=409,
        )

    validas = []
    for leitura in leituras:
        if isinstance(leitura, dict):
            validas.append(leitura)
    validas.sort(key=lambda leitura: leitura.get('ts') or 0)

    salvas = 0
    ignoradas = len(leituras) - len(validas)

    for leitura in validas:
        ts = leitura.get('ts')
        echo_us = leitura.get('echo_us')

        if ts is None:
            logger.warning('%s: leitura ignorada, sem hora', identificacao)
            ignoradas += 1
            continue

        if echo_us is None:
            logger.warning('%s: leitura ignorada, sem eco (ts=%s)', identificacao, ts)
            ignoradas += 1
            continue

        try:
            data_hora = datetime.fromtimestamp(ts, tz=timezone.utc)

            repetida = LeituraTelemetria.objects.filter(
                dispositivo=dispositivo,
                data_hora=data_hora,
            ).exists()

            if repetida:
                ignoradas += 1
                continue

            temperatura_agua = leitura.get('water_temp_c')
            temperatura = temperatura_agua
            if temperatura is None:
                temperatura = TEMPERATURA_PADRAO

            distancia = calcular_distancia_cm(echo_us, temperatura)

            qualidade_agua_ppm = None
            if leitura.get('tds_mv') is not None:
                qualidade_agua_ppm = calcular_tds_ppm(
                    leitura['tds_mv'], temperatura, dispositivo.fator_tds
                )

            LeituraTelemetria.objects.create(
                cisterna=dispositivo.cisterna,
                dispositivo=dispositivo,
                data_hora=data_hora,
                nivel=calcular_nivel(distancia, dispositivo),
                temperatura_agua=temperatura_agua,
                temperatura_ar=leitura.get('air_temp_c'),
                umidade_ar=leitura.get('air_rh_pct'),
                qualidade_agua_ppm=qualidade_agua_ppm,
                tensao_bateria=calcular_tensao(leitura.get('battery_mv'), 2.0),
                tensao_placa_solar=calcular_tensao(leitura.get('solar_mv'), 3.2),
            )
            salvas += 1

        except (TypeError, ValueError, OverflowError, OSError) as erro:
            logger.warning('%s: leitura ignorada, %s (ts=%s)', identificacao, erro, ts)
            ignoradas += 1

    return JsonResponse({'salvas': salvas, 'ignoradas': ignoradas})
