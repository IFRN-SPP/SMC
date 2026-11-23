from .models import Cisterna, LeituraTelemetria
from functools import wraps
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import Group, User
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .forms import (
    CisternaForm,
    DispositivoForm,
    LocalidadeForm,
    MunicipioForm,
    ParticipanteForm,
    UsuarioForm,
    UsuarioEdicaoForm,
)

from .models import (
    Alerta,
    Cisterna,
    Dispositivo,
    LeituraTelemetria,
    Localidade,
    Municipio,
    Participante,
    PerfilUsuario,
)


def somente_perfis(*perfis):
    def decorator(view_func):
        @wraps(view_func)
        @login_required
        def wrapper(request, *args, **kwargs):
            if (
                request.user.is_superuser
                or request.user.groups.filter(name__in=perfis).exists()
            ):
                return view_func(request, *args, **kwargs)

            return render(
                request,
                'monitoramento/acesso_negado.html',
                status=403,
            )

        return wrapper

    return decorator


def ultima_leitura_da_cisterna(cisterna_id):
    return (
        LeituraTelemetria.objects
        .filter(cisterna_id=cisterna_id)
        .order_by('-data_hora', '-pk')
        .first()
    )


def montar_sensores(leitura):
    """Lista os sensores de uma leitura (valor None quando não há dado)."""
    return [
        {
            'chave': campo,
            'curto': faixa['curto'],
            'rotulo': faixa['rotulo'],
            'unidade': faixa['unidade'],
            'casas': faixa['casas'],
            'valor': getattr(leitura, campo) if leitura else None,
        }
        for campo, faixa in LeituraTelemetria.CAMPOS_SENSORES.items()
    ]


def resumir_sensores(leituras):
    """Resume as últimas leituras de todas as cisternas, sensor a sensor.

    Usa a média, exceto na bateria, onde o menor valor é mais útil: uma média
    esconderia a bateria de uma cisterna que está acabando.
    """
    resumo = []

    for campo, faixa in LeituraTelemetria.CAMPOS_SENSORES.items():
        valores = [
            getattr(leitura, campo)
            for leitura in leituras
            if getattr(leitura, campo) is not None
        ]

        usa_menor = campo == 'tensao_bateria'

        if not valores:
            valor = None
        elif usa_menor:
            valor = min(valores)
        else:
            valor = sum(valores) / len(valores)

        resumo.append({
            'chave': campo,
            'rotulo': faixa['rotulo'],
            'unidade': faixa['unidade'],
            'casas': faixa['casas'],
            'valor': valor,
            'n': len(valores),
            'tipo': 'menor entre' if usa_menor else 'média de',
        })

    return resumo


@login_required
def index(request):
    total_usuarios = get_user_model().objects.count()
    total_cisternas = Cisterna.objects.count()
    total_participantes = Participante.objects.count()
    total_leituras = LeituraTelemetria.objects.count()
    total_alertas = Alerta.objects.count()
    total_localidades = Localidade.objects.count()

    total_atencao = Alerta.objects.filter(tipo='atencao').count()
    total_criticos = Alerta.objects.filter(tipo='critico').count()

    alertas_recentes = (
        Alerta.objects.select_related('cisterna')
        .order_by('-data_hora')[:5]
    )

    ultimas = [
        leitura
        for leitura in (
            ultima_leitura_da_cisterna(pk)
            for pk in Cisterna.objects.values_list('pk', flat=True)
        )
        if leitura
    ]

    contexto = {
        'sensores_resumo': resumir_sensores(ultimas),
        'ultima_atualizacao': max(
            (leitura.data_hora for leitura in ultimas), default=None
        ),
        'total_usuarios': total_usuarios,
        'total_cisternas': total_cisternas,
        'total_participantes': total_participantes,
        'total_leituras': total_leituras,
        'total_alertas': total_alertas,
        'total_localidades': total_localidades,
        'total_atencao': total_atencao,
        'total_criticos': total_criticos,
        'alertas_recentes': alertas_recentes,
    }

    return render(request, 'monitoramento/index.html', contexto)

@login_required
def lista_cisternas(request):
    cisternas = Cisterna.objects.select_related(
        'participante',
        'localidade',
        'municipio',
    ).all()

    return render(
        request,
        'monitoramento/cisternas/lista.html',
        {'cisternas': cisternas},
    )


@somente_perfis('Administrador do sistema')
def criar_cisterna(request):
    if request.method == 'POST':
        form = CisternaForm(request.POST, request.FILES)

        if form.is_valid():
            form.save()
            return redirect('lista_cisternas')
    else:
        form = CisternaForm()

    return render(
        request,
        'monitoramento/cisternas/form.html',
        {
            'form': form,
            'titulo': 'Cadastrar cisterna',
        },
    )


@somente_perfis('Administrador do sistema')
def editar_cisterna(request, id):
    cisterna = get_object_or_404(Cisterna, id=id)

    if request.method == 'POST':
        form = CisternaForm(
            request.POST,
            request.FILES,
            instance=cisterna,
        )

        if form.is_valid():
            form.save()
            return redirect('lista_cisternas')
    else:
        form = CisternaForm(instance=cisterna)

    return render(
        request,
        'monitoramento/cisternas/form.html',
        {
            'form': form,
            'titulo': 'Editar cisterna',
        },
    )


@somente_perfis('Administrador do sistema')
def excluir_cisterna(request, id):
    cisterna = get_object_or_404(Cisterna, id=id)

    if request.method == 'POST':
        cisterna.delete()

        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'sucesso': True,
                'mensagem': 'Cisterna excluída com sucesso!'
            })

        return redirect('lista_cisternas')

    return render(
        request,
        'monitoramento/cisternas/confirmar_exclusao.html',
        {'cisterna': cisterna},
    )


@somente_perfis('Administrador do sistema')
def lista_usuarios(request):
    usuarios = User.objects.all().order_by('username')

    return render(
        request,
        'monitoramento/usuarios/lista.html',
        {'usuarios': usuarios},
    )


@somente_perfis('Administrador do sistema')
def criar_usuario(request):
    if request.method == 'POST':
        form = UsuarioForm(request.POST)

        if form.is_valid():
            usuario = form.save(commit=False)
            usuario.set_password(form.cleaned_data['senha'])
            usuario.save()

            grupo, _ = Group.objects.get_or_create(
                name=form.cleaned_data['perfil'],
            )

            usuario.groups.clear()
            usuario.groups.add(grupo)

            PerfilUsuario.objects.update_or_create(
                usuario=usuario,
                defaults={
                    'municipio': form.cleaned_data.get('municipio'),
                },
            )

            return redirect('lista_usuarios')
    else:
        form = UsuarioForm()

    return render(
        request,
        'monitoramento/usuarios/form.html',
        {
            'form': form,
            'titulo': 'Cadastrar usuário',
        },
    )


@somente_perfis('Administrador do sistema')
def editar_usuario(request, id):
    usuario = get_object_or_404(User, pk=id)

    if usuario.is_superuser and not request.user.is_superuser:
        return render(
            request,
            'monitoramento/acesso_negado.html',
            status=403,
        )

    if request.method == 'POST':
        form = UsuarioEdicaoForm(
            request.POST,
            instance=usuario,
        )

        # Permite editar o usuário sem informar um município.
        if 'municipio' in form.fields:
            form.fields['municipio'].required = False

        if form.is_valid():
            usuario = form.save(commit=False)

            senha = form.cleaned_data.get('nova_senha')
            if senha:
                usuario.set_password(senha)

            usuario.save()

            grupo, _ = Group.objects.get_or_create(
                name=form.cleaned_data['perfil'],
            )
            usuario.groups.set([grupo])

            municipio = form.cleaned_data.get('municipio')

            # Mantém o município anterior se nenhum novo for informado.
            if municipio is None:
                perfil_atual = PerfilUsuario.objects.filter(
                    usuario=usuario,
                ).first()

                if perfil_atual:
                    municipio = perfil_atual.municipio

            PerfilUsuario.objects.update_or_create(
                usuario=usuario,
                defaults={
                    'municipio': municipio,
                },
            )

            return redirect('lista_usuarios')

        print('ERROS DO FORMULÁRIO DE EDIÇÃO:', form.errors)
        print('DADOS RECEBIDOS:', request.POST)

    else:
        form = UsuarioEdicaoForm(instance=usuario)

    return render(
        request,
        'monitoramento/usuarios/editar.html',
        {
            'form': form,
            'titulo': 'Editar usuário',
            'usuario': usuario,
        },
    )


@somente_perfis('Administrador do sistema')
def excluir_usuario(request, id):
    usuario = get_object_or_404(User, pk=id)

    if usuario.pk == request.user.pk:
        return render(
            request,
            'monitoramento/acesso_negado.html',
            status=403,
        )

    if usuario.is_superuser and not request.user.is_superuser:
        return render(
            request,
            'monitoramento/acesso_negado.html',
            status=403,
        )

    if request.method == 'POST':
        usuario.delete()
        return redirect('lista_usuarios')

    return render(
        request,
        'monitoramento/confirmar_exclusao_generica.html',
        {
            'objeto': usuario,
            'titulo': 'Excluir usuário',
            'voltar_url': 'lista_usuarios',
            'tipo': 'usuário',
        },
    )



@login_required
def monitoramento(request):
    cisternas = list(
        Cisterna.objects.select_related(
            "participante",
            "localidade",
            "municipio",
        ).all()
    )

    for cisterna in cisternas:
        cisterna.ultima_leitura = ultima_leitura_da_cisterna(cisterna.id)
        cisterna.sensores = montar_sensores(cisterna.ultima_leitura)

        if cisterna.ultima_leitura:
            nivel = cisterna.ultima_leitura.nivel

            if nivel >= 70:
                cisterna.status_monitoramento = "Normal"
                cisterna.status_classe = "normal"
            elif nivel >= 30:
                cisterna.status_monitoramento = "Atenção"
                cisterna.status_classe = "atencao"
            else:
                cisterna.status_monitoramento = "Crítico"
                cisterna.status_classe = "critico"
        else:
            cisterna.status_monitoramento = "Sem leitura"
            cisterna.status_classe = "sem-dados"

    total_leituras = LeituraTelemetria.objects.count()

    total_atencao = sum(
        1 for c in cisternas if c.status_classe in ("atencao", "critico")
    )

    contexto = {
        "cisternas": cisternas,
        "total_monitoradas": len(cisternas),
        "total_leituras": total_leituras,
        "total_requer_atencao": total_atencao,
    }

    return render(
        request,
        "monitoramento/monitoramento.html",
        contexto,
    )


@login_required
def lista_alertas(request):
    busca = request.GET.get('q', '').strip()

    alertas = (
        Alerta.objects
        .select_related(
            'cisterna',
            'cisterna__municipio',
            'cisterna__localidade',
        )
        .order_by('-data_hora')
    )

    if busca:
        alertas = alertas.filter(
            Q(mensagem__icontains=busca)
            | Q(cisterna__identificacao__icontains=busca)
            | Q(cisterna__municipio__nome__icontains=busca)
            | Q(cisterna__localidade__nome__icontains=busca)
        )

    return render(
        request,
        'monitoramento/alertas/lista.html',
        {
            'alertas': alertas,
            'busca': busca,
        },
    )



@somente_perfis('Administrador do sistema', 'Operador-técnico')
def resolver_alerta(request, id):
    if request.method != 'POST':
        return redirect('lista_alertas')

    alerta = get_object_or_404(Alerta, id=id)

    if not alerta.resolvido:
        alerta.resolvido = True
        alerta.resolvido_em = timezone.now()
        alerta.save(update_fields=['resolvido', 'resolvido_em'])

    return redirect('lista_alertas')


@somente_perfis('Administrador do sistema')
def lista_municipios(request):
    municipios = Municipio.objects.all().order_by('nome')

    return render(
        request,
        'monitoramento/municipios/lista.html',
        {'municipios': municipios},
    )


@somente_perfis('Administrador do sistema')
def criar_municipio(request):
    if request.method == 'POST':
        form = MunicipioForm(request.POST)

        if form.is_valid():
            form.save()
            return redirect('lista_municipios')
    else:
        form = MunicipioForm()

    return render(
        request,
        'monitoramento/municipios/form.html',
        {
            'form': form,
            'titulo': 'Cadastrar município',
            'municipio': None,
        },
    )


@somente_perfis('Administrador do sistema')
def editar_municipio(request, id):
    municipio = get_object_or_404(Municipio, id=id)

    if request.method == 'POST':
        form = MunicipioForm(
            request.POST,
            instance=municipio,
        )

        if form.is_valid():
            form.save()
            return redirect('lista_municipios')
    else:
        form = MunicipioForm(instance=municipio)

    return render(
        request,
        'monitoramento/municipios/form.html',
        {
            'form': form,
            'titulo': 'Editar município',
            'municipio': municipio,
        },
    )


@somente_perfis('Administrador do sistema')
def excluir_municipio(request, id):
    municipio = get_object_or_404(Municipio, pk=id)
    bloqueada = municipio.cisternas.exists()

    if request.method == 'POST' and not bloqueada:
        municipio.delete()
        return redirect('lista_municipios')

    return render(
        request,
        'monitoramento/confirmar_exclusao_generica.html',
        {
            'objeto': municipio,
            'titulo': 'Excluir município',
            'voltar_url': 'lista_municipios',
            'tipo': 'município',
            'bloqueada': bloqueada,
        },
        status=400 if bloqueada else 200,
    )

@somente_perfis('Administrador do sistema')
def lista_localidades(request):
    localidades = Localidade.objects.all().order_by('nome')

    return render(
        request,
        'monitoramento/localidades/lista.html',
        {'localidades': localidades}
    )


@somente_perfis('Administrador do sistema')
def criar_localidade(request):
    if request.method == 'POST':
        form = LocalidadeForm(request.POST)

        if form.is_valid():
            form.save()
            return redirect('lista_localidades')
    else:
        form = LocalidadeForm()

    return render(
        request,
        'monitoramento/localidades/form.html',
        {'form': form, 'titulo': 'Cadastrar localidade', 'localidade': None}
    )


@somente_perfis('Administrador do sistema')
def editar_localidade(request, id):
    localidade = get_object_or_404(Localidade, id=id)

    if request.method == 'POST':
        form = LocalidadeForm(request.POST, instance=localidade)

        if form.is_valid():
            form.save()
            return redirect('lista_localidades')
    else:
        form = LocalidadeForm(instance=localidade)

    return render(
        request,
        'monitoramento/localidades/form.html',
        {'form': form, 'titulo': 'Editar localidade', 'localidade': localidade}
    )


@somente_perfis('Administrador do sistema')
def excluir_localidade(request, id):
    localidade = get_object_or_404(Localidade, pk=id)

    # Impede excluir uma localidade que tenha cisternas vinculadas.
    bloqueada = localidade.cisternas.exists()

    if request.method == 'POST' and not bloqueada:
        localidade.delete()
        return redirect('lista_localidades')

    return render(
        request,
        'monitoramento/confirmar_exclusao_generica.html',
        {
            'objeto': localidade,
            'titulo': 'Excluir localidade',
            'voltar_url': 'lista_localidades',
            'tipo': 'localidade',
            'bloqueada': bloqueada,
        },
        status=400 if bloqueada else 200
    )

@login_required
def historico_leituras(request, id):
    cisterna = get_object_or_404(Cisterna, id=id)

    leituras = LeituraTelemetria.objects.filter(
        cisterna=cisterna,
    ).order_by('-data_hora')

    return render(
        request,
        'monitoramento/historico/lista.html',
        {
            'cisterna': cisterna,
            'leituras': leituras,
        },
    )


@somente_perfis('Administrador do sistema')
def lista_dispositivos(request):
    dispositivos = Dispositivo.objects.select_related(
        'cisterna',
    ).all().order_by('identificacao')

    return render(
        request,
        'monitoramento/dispositivos/lista.html',
        {'dispositivos': dispositivos},
    )


@somente_perfis('Administrador do sistema')
def criar_dispositivo(request):
    if request.method == 'POST':
        form = DispositivoForm(request.POST)

        if form.is_valid():
            form.save()
            return redirect('lista_dispositivos')
    else:
        form = DispositivoForm()

    return render(
        request,
        'monitoramento/dispositivos/form.html',
        {
            'form': form,
            'titulo': 'Cadastrar dispositivo',
            'dispositivo': None,
        },
    )


@somente_perfis('Administrador do sistema')
def editar_dispositivo(request, id):
    dispositivo = get_object_or_404(Dispositivo, pk=id)

    if request.method == 'POST':
        form = DispositivoForm(
            request.POST,
            instance=dispositivo,
        )

        if form.is_valid():
            form.save()
            return redirect('lista_dispositivos')
    else:
        form = DispositivoForm(instance=dispositivo)

    return render(
        request,
        'monitoramento/dispositivos/form.html',
        {
            'form': form,
            'titulo': 'Editar dispositivo',
            'dispositivo': dispositivo,
        },
    )


@somente_perfis('Administrador do sistema')
def excluir_dispositivo(request, id):
    dispositivo = get_object_or_404(Dispositivo, pk=id)

    if request.method == 'POST':
        dispositivo.delete()
        return redirect('lista_dispositivos')

    return render(
        request,
        'monitoramento/confirmar_exclusao_generica.html',
        {
            'objeto': dispositivo,
            'titulo': 'Excluir dispositivo',
            'voltar_url': 'lista_dispositivos',
            'tipo': 'dispositivo',
        },
    )


@login_required
def mapa(request):
    cisternas = Cisterna.objects.filter(
        latitude__isnull=False,
        longitude__isnull=False,
    )

    dados_cisternas = []

    for cisterna in cisternas:
        dados_cisternas.append({
            'latitude': float(cisterna.latitude),
            'longitude': float(cisterna.longitude),
            'identificacao': cisterna.identificacao,
            'participante': str(cisterna.participante),
            'municipio': str(cisterna.municipio),
            'localidade': str(cisterna.localidade),
            'capacidade': cisterna.capacidade_total,
            'situacao': cisterna.get_situacao_display(),
        })

    return render(
        request,
        'monitoramento/mapa.html',
        {'cisternas': dados_cisternas},
    )


@login_required
def apresentacao(request):
    return render(
        request,
        'monitoramento/apresentacao.html',
    )


@login_required
@somente_perfis('Administrador do sistema',  'Operador-técnico')
def resolver_alerta(request, id):
    if request.method != 'POST':
        return redirect('lista_alertas')

    alerta = get_object_or_404(Alerta, id=id)

    if not alerta.resolvido:
        alerta.resolvido = True
        alerta.resolvido_em = timezone.now()
        alerta.save(update_fields=['resolvido', 'resolvido_em'])

    return redirect('lista_alertas')

@login_required
def relatorios(request):
    total_cisternas = Cisterna.objects.count()
    total_leituras = LeituraTelemetria.objects.count()

    total_alertas_pendentes = Alerta.objects.filter(
        resolvido=False
    ).count()

    total_municipios = (
        Municipio.objects.filter(cisternas__isnull=False)
        .distinct()
        .count()
    )

    leituras = LeituraTelemetria.objects.select_related(
        'cisterna',
        'cisterna__municipio',
    ).order_by('-data_hora')

    municipio_id = request.GET.get('municipio', '').strip()

    if municipio_id.isdigit():
        leituras = leituras.filter(
            cisterna__municipio_id=int(municipio_id)
        )

    cisterna_id = request.GET.get('cisterna', '').strip()

    if cisterna_id.isdigit():
        leituras = leituras.filter(
            cisterna_id=int(cisterna_id)
        )

    data_inicio = request.GET.get('data_inicio', '').strip()
    data_fim = request.GET.get('data_fim', '').strip()

    if data_inicio:
        leituras = leituras.filter(
            data_hora__date__gte=data_inicio
        )

    if data_fim:
        leituras = leituras.filter(
            data_hora__date__lte=data_fim
        )

    contexto = {
        'total_cisternas': total_cisternas,
        'total_leituras': total_leituras,
        'total_alertas_pendentes': total_alertas_pendentes,
        'total_municipios': total_municipios,
        'leituras': leituras[:100],
        'municipios': Municipio.objects.order_by('nome'),
        'cisternas': Cisterna.objects.order_by('identificacao'),
        'municipio_selecionado': municipio_id,
        'cisterna_selecionada': cisterna_id,
        'data_inicio': data_inicio,
        'data_fim': data_fim,
        'total_resultados': leituras.count(),
    }

    return render(
        request,
        'monitoramento/relatorios.html',
        contexto,
    )


def usuario_admin_ajax(request):
    return (
        request.user.is_authenticated
        and (
            request.user.is_superuser
            or request.user.groups.filter(
                name='Administrador do sistema'
            ).exists()
        )
    )


@login_required
def ajax_lista_cisternas(request):
    cisternas = Cisterna.objects.select_related(
        'participante',
        'localidade',
        'municipio',
    ).all()

    dados = []

    for cisterna in cisternas:
        dados.append({
            'id': cisterna.id,
            'identificacao': cisterna.identificacao,
            'participante': str(cisterna.participante),
            'localidade': str(cisterna.localidade),
            'municipio': str(cisterna.municipio or ''),
            'latitude': str(cisterna.latitude or ''),
            'longitude': str(cisterna.longitude or ''),
            'capacidade_total': cisterna.capacidade_total,
            'situacao': cisterna.situacao,
            'imagem': cisterna.imagem.url if cisterna.imagem else '',
        })

    return JsonResponse({'cisternas': dados})


@login_required
def ajax_criar_cisterna(request):
    if not usuario_admin_ajax(request):
        return JsonResponse(
            {'mensagem': 'Você não tem permissão para cadastrar cisternas.'},
            status=403
        )

    if request.method != 'POST':
        return JsonResponse(
            {'mensagem': 'Método não permitido.'},
            status=405
        )

    form = CisternaForm(request.POST, request.FILES)

    if form.is_valid():
        cisterna = form.save()

        return JsonResponse({
            'mensagem': 'Cisterna cadastrada com sucesso!',
            'cisterna': {
                'id': cisterna.id,
                'identificacao': cisterna.identificacao,
            }
        }, status=201)

    return JsonResponse({
        'mensagem': 'Verifique os campos do formulário.',
        'erros': form.errors.get_json_data(),
    }, status=400)


@login_required
def ajax_editar_cisterna(request, id):
    if not usuario_admin_ajax(request):
        return JsonResponse(
            {'mensagem': 'Você não tem permissão para editar cisternas.'},
            status=403
        )

    cisterna = get_object_or_404(Cisterna, id=id)

    if request.method == 'GET':
        return JsonResponse({
            'id': cisterna.id,
            'identificacao': cisterna.identificacao,
            'participante': cisterna.participante_id,
            'municipio': cisterna.municipio_id,
            'localidade': cisterna.localidade_id,
            'latitude': str(cisterna.latitude or ''),
            'longitude': str(cisterna.longitude or ''),
            'capacidade_total': cisterna.capacidade_total,
            'situacao': cisterna.situacao,
        })

    if request.method != 'POST':
        return JsonResponse(
            {'mensagem': 'Método não permitido.'},
            status=405
        )

    form = CisternaForm(
        request.POST,
        request.FILES,
        instance=cisterna
    )

    if form.is_valid():
        cisterna = form.save()

        return JsonResponse({
            'mensagem': 'Cisterna atualizada com sucesso!',
            'cisterna': {
                'id': cisterna.id,
                'identificacao': cisterna.identificacao,
            }
        })

    return JsonResponse({
        'mensagem': 'Verifique os campos do formulário.',
        'erros': form.errors.get_json_data(),
    }, status=400)


@login_required
def ajax_excluir_cisterna(request, id):
    if not usuario_admin_ajax(request):
        return JsonResponse(
            {'mensagem': 'Você não tem permissão para excluir cisternas.'},
            status=403
        )

    if request.method != 'POST':
        return JsonResponse(
            {'mensagem': 'Método não permitido.'},
            status=405
        )

    cisterna = get_object_or_404(Cisterna, id=id)
    identificacao = cisterna.identificacao

    cisterna.delete()

    return JsonResponse({
        'mensagem': f'Cisterna {identificacao} excluída com sucesso!'
    })

@login_required
def ajax_lista_municipios(request):
    if not usuario_admin_ajax(request):
        return JsonResponse(
            {'mensagem': 'Você não tem permissão para acessar municípios.'},
            status=403
        )

    municipios = Municipio.objects.all().order_by('nome')

    dados = [
        {
            'id': municipio.id,
            'nome': municipio.nome,
            'estado': municipio.estado,
        }
        for municipio in municipios
    ]

    return JsonResponse({'municipios': dados})


@login_required
def ajax_criar_municipio(request):
    if not usuario_admin_ajax(request):
        return JsonResponse(
            {'mensagem': 'Você não tem permissão para cadastrar municípios.'},
            status=403
        )

    if request.method != 'POST':
        return JsonResponse(
            {'mensagem': 'Método não permitido.'},
            status=405
        )

    form = MunicipioForm(request.POST)

    if form.is_valid():
        municipio = form.save()

        return JsonResponse({
            'sucesso': True,
            'mensagem': 'Município cadastrado com sucesso!',
            'municipio': {
                'id': municipio.id,
                'nome': municipio.nome,
                'estado': municipio.estado,
            }
        }, status=201)

    return JsonResponse({
        'sucesso': False,
        'mensagem': 'Verifique os campos do formulário.',
        'erros': form.errors.get_json_data(),
    }, status=400)


@login_required
def ajax_editar_municipio(request, id):
    if not usuario_admin_ajax(request):
        return JsonResponse(
            {'mensagem': 'Você não tem permissão para editar municípios.'},
            status=403
        )

    municipio = get_object_or_404(Municipio, id=id)

    if request.method == 'GET':
        return JsonResponse({
            'id': municipio.id,
            'nome': municipio.nome,
            'estado': municipio.estado,
        })

    if request.method != 'POST':
        return JsonResponse(
            {'mensagem': 'Método não permitido.'},
            status=405
        )

    form = MunicipioForm(request.POST, instance=municipio)

    if form.is_valid():
        municipio = form.save()

        return JsonResponse({
            'sucesso': True,
            'mensagem': 'Município atualizado com sucesso!',
            'municipio': {
                'id': municipio.id,
                'nome': municipio.nome,
                'estado': municipio.estado,
            }
        })

    return JsonResponse({
        'sucesso': False,
        'mensagem': 'Verifique os campos do formulário.',
        'erros': form.errors.get_json_data(),
    }, status=400)


@login_required
def ajax_excluir_municipio(request, id):
    if not usuario_admin_ajax(request):
        return JsonResponse(
            {'mensagem': 'Você não tem permissão para excluir municípios.'},
            status=403
        )

    if request.method != 'POST':
        return JsonResponse(
            {'mensagem': 'Método não permitido.'},
            status=405
        )

    municipio = get_object_or_404(Municipio, id=id)

    if municipio.cisternas.exists():
        return JsonResponse({
            'sucesso': False,
            'mensagem': 'Não é possível excluir este município porque existem cisternas vinculadas a ele.'
        }, status=400)

    nome = municipio.nome
    municipio.delete()

    return JsonResponse({
        'sucesso': True,
        'mensagem': f'Município {nome} excluído com sucesso!'
    })

@login_required
def ajax_lista_localidades(request):
    if not usuario_admin_ajax(request):
        return JsonResponse({'mensagem': 'Sem permissão.'}, status=403)
    localidades = Localidade.objects.order_by('nome')
    return JsonResponse({'localidades': [
        {'id': item.id, 'nome': item.nome, 'municipio': item.municipio,
         'endereco': item.endereco, 'descricao': item.descricao}
        for item in localidades
    ]})


@login_required
def ajax_criar_localidade(request):
    if not usuario_admin_ajax(request):
        return JsonResponse({'mensagem': 'Você não tem permissão para cadastrar localidades.'}, status=403)
    if request.method != 'POST':
        return JsonResponse({'mensagem': 'Método não permitido.'}, status=405)
    form = LocalidadeForm(request.POST)
    if form.is_valid():
        item = form.save()
        return JsonResponse({'sucesso': True, 'mensagem': 'Localidade cadastrada com sucesso!',
            'localidade': {'id': item.id, 'nome': item.nome, 'municipio': item.municipio,
                           'endereco': item.endereco, 'descricao': item.descricao}}, status=201)
    return JsonResponse({'mensagem': 'Verifique os campos do formulário.', 'erros': form.errors.get_json_data()}, status=400)


@login_required
def ajax_editar_localidade(request, id):
    if not usuario_admin_ajax(request):
        return JsonResponse({'mensagem': 'Você não tem permissão para editar localidades.'}, status=403)
    item = get_object_or_404(Localidade, pk=id)
    if request.method == 'GET':
        return JsonResponse({'id': item.id, 'nome': item.nome, 'municipio': item.municipio,
                             'endereco': item.endereco, 'descricao': item.descricao})
    if request.method != 'POST':
        return JsonResponse({'mensagem': 'Método não permitido.'}, status=405)
    form = LocalidadeForm(request.POST, instance=item)
    if form.is_valid():
        item = form.save()
        return JsonResponse({'sucesso': True, 'mensagem': 'Localidade atualizada com sucesso!',
            'localidade': {'id': item.id, 'nome': item.nome, 'municipio': item.municipio,
                           'endereco': item.endereco, 'descricao': item.descricao}})
    return JsonResponse({'mensagem': 'Verifique os campos do formulário.', 'erros': form.errors.get_json_data()}, status=400)


@login_required
def ajax_excluir_localidade(request, id):
    if not usuario_admin_ajax(request):
        return JsonResponse({'mensagem': 'Você não tem permissão para excluir localidades.'}, status=403)
    if request.method != 'POST':
        return JsonResponse({'mensagem': 'Método não permitido.'}, status=405)
    item = get_object_or_404(Localidade, pk=id)
    if item.cisternas.exists():
        return JsonResponse({'mensagem': 'Não é possível excluir esta localidade porque existem cisternas vinculadas.'}, status=400)
    nome = item.nome
    item.delete()
    return JsonResponse({'sucesso': True, 'mensagem': f'Localidade {nome} excluída com sucesso!'})


@login_required
def ajax_lista_dispositivos(request):
    if not usuario_admin_ajax(request):
        return JsonResponse({'mensagem': 'Sem permissão.'}, status=403)
    items = Dispositivo.objects.select_related('cisterna').order_by('identificacao')
    return JsonResponse({'dispositivos': [
        {'id': item.id, 'identificacao': item.identificacao, 'tipo_sensor': item.tipo_sensor,
         'cisterna': item.cisterna_id, 'cisterna_nome': item.cisterna.identificacao,
         'data_instalacao': item.data_instalacao.isoformat(), 'situacao': item.situacao}
        for item in items
    ]})


@login_required
def ajax_criar_dispositivo(request):
    if not usuario_admin_ajax(request):
        return JsonResponse({'mensagem': 'Você não tem permissão para cadastrar dispositivos.'}, status=403)
    if request.method != 'POST':
        return JsonResponse({'mensagem': 'Método não permitido.'}, status=405)
    form = DispositivoForm(request.POST)
    if form.is_valid():
        item = form.save()
        return JsonResponse({'sucesso': True, 'mensagem': 'Dispositivo cadastrado com sucesso!',
            'dispositivo': {'id': item.id, 'identificacao': item.identificacao}}, status=201)
    return JsonResponse({'mensagem': 'Verifique os campos do formulário.', 'erros': form.errors.get_json_data()}, status=400)


@login_required
def ajax_editar_dispositivo(request, id):
    if not usuario_admin_ajax(request):
        return JsonResponse({'mensagem': 'Você não tem permissão para editar dispositivos.'}, status=403)
    item = get_object_or_404(Dispositivo, pk=id)
    if request.method == 'GET':
        return JsonResponse({'id': item.id, 'identificacao': item.identificacao, 'tipo_sensor': item.tipo_sensor,
                             'cisterna': item.cisterna_id, 'data_instalacao': item.data_instalacao.isoformat(),
                             'situacao': item.situacao})
    if request.method != 'POST':
        return JsonResponse({'mensagem': 'Método não permitido.'}, status=405)
    form = DispositivoForm(request.POST, instance=item)
    if form.is_valid():
        item = form.save()
        return JsonResponse({'sucesso': True, 'mensagem': 'Dispositivo atualizado com sucesso!',
            'dispositivo': {'id': item.id, 'identificacao': item.identificacao}})
    return JsonResponse({'mensagem': 'Verifique os campos do formulário.', 'erros': form.errors.get_json_data()}, status=400)


@login_required
def ajax_excluir_dispositivo(request, id):
    if not usuario_admin_ajax(request):
        return JsonResponse({'mensagem': 'Você não tem permissão para excluir dispositivos.'}, status=403)
    if request.method != 'POST':
        return JsonResponse({'mensagem': 'Método não permitido.'}, status=405)
    item = get_object_or_404(Dispositivo, pk=id)
    nome = item.identificacao
    item.delete()
    return JsonResponse({'sucesso': True, 'mensagem': f'Dispositivo {nome} excluído com sucesso!'})


@somente_perfis('Administrador do sistema')
def lista_participantes(request):
    participantes = Participante.objects.order_by('nome')
    return render(request, 'monitoramento/participantes/lista.html', {'participantes': participantes})


@somente_perfis('Administrador do sistema')
def criar_participante(request):
    form = ParticipanteForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        form.save()
        return redirect('lista_participantes')
    return render(request, 'monitoramento/participantes/form.html', {'form': form, 'titulo': 'Cadastrar participante', 'participante': None})


@somente_perfis('Administrador do sistema')
def editar_participante(request, id):
    participante = get_object_or_404(Participante, pk=id)
    form = ParticipanteForm(request.POST or None, instance=participante)
    if request.method == 'POST' and form.is_valid():
        form.save()
        return redirect('lista_participantes')
    return render(request, 'monitoramento/participantes/form.html', {'form': form, 'titulo': 'Editar participante', 'participante': participante})


@login_required
def ajax_lista_participantes(request):
    if not usuario_admin_ajax(request):
        return JsonResponse({'mensagem': 'Sem permissão.'}, status=403)
    return JsonResponse({'participantes': [{'id': item.id, 'nome': item.nome} for item in Participante.objects.order_by('nome')]})


@login_required
def ajax_criar_participante(request):
    if not usuario_admin_ajax(request):
        return JsonResponse({'mensagem': 'Você não tem permissão para cadastrar participantes.'}, status=403)
    if request.method != 'POST':
        return JsonResponse({'mensagem': 'Método não permitido.'}, status=405)
    form = ParticipanteForm(request.POST)
    if form.is_valid():
        item = form.save()
        return JsonResponse({'sucesso': True, 'mensagem': 'Participante cadastrado com sucesso!', 'participante': {'id': item.id, 'nome': item.nome}}, status=201)
    return JsonResponse({'mensagem': 'Verifique os campos do formulário.', 'erros': form.errors.get_json_data()}, status=400)


@login_required
def ajax_editar_participante(request, id):
    if not usuario_admin_ajax(request):
        return JsonResponse({'mensagem': 'Você não tem permissão para editar participantes.'}, status=403)
    item = get_object_or_404(Participante, pk=id)
    if request.method == 'GET':
        return JsonResponse({'id': item.id, 'nome': item.nome})
    if request.method != 'POST':
        return JsonResponse({'mensagem': 'Método não permitido.'}, status=405)
    form = ParticipanteForm(request.POST, instance=item)
    if form.is_valid():
        item = form.save()
        return JsonResponse({'sucesso': True, 'mensagem': 'Participante atualizado com sucesso!', 'participante': {'id': item.id, 'nome': item.nome}})
    return JsonResponse({'mensagem': 'Verifique os campos do formulário.', 'erros': form.errors.get_json_data()}, status=400)


@login_required
def ajax_excluir_participante(request, id):
    if not usuario_admin_ajax(request):
        return JsonResponse({'mensagem': 'Você não tem permissão para excluir participantes.'}, status=403)
    if request.method != 'POST':
        return JsonResponse({'mensagem': 'Método não permitido.'}, status=405)
    item = get_object_or_404(Participante, pk=id)
    if item.cisternas.exists():
        return JsonResponse({'mensagem': 'Não é possível excluir este participante porque existem cisternas vinculadas.'}, status=400)
    nome = item.nome
    item.delete()
    return JsonResponse({'sucesso': True, 'mensagem': f'Participante {nome} excluído com sucesso!'})


@login_required
def ajax_resolver_alerta(request, id):
    if not (request.user.is_superuser or request.user.groups.filter(name__in=['Administrador do sistema', 'Operador-técnico']).exists()):
        return JsonResponse({'mensagem': 'Você não tem permissão para resolver alertas.'}, status=403)
    if request.method != 'POST':
        return JsonResponse({'mensagem': 'Método não permitido.'}, status=405)
    item = get_object_or_404(Alerta, pk=id)
    if not item.resolvido:
        item.resolvido = True
        item.resolvido_em = timezone.now()
        item.save(update_fields=['resolvido', 'resolvido_em'])
    return JsonResponse({'sucesso': True, 'mensagem': 'Alerta marcado como resolvido!'})


@login_required
def ajax_criar_usuario(request):
    if not usuario_admin_ajax(request):
        return JsonResponse({'mensagem': 'Você não tem permissão para cadastrar usuários.'}, status=403)
    if request.method != 'POST':
        return JsonResponse({'mensagem': 'Método não permitido.'}, status=405)
    form = UsuarioForm(request.POST)
    if form.is_valid():
        usuario = form.save(commit=False)
        usuario.set_password(form.cleaned_data['senha'])
        usuario.save()
        grupo, _ = Group.objects.get_or_create(name=form.cleaned_data['perfil'])
        usuario.groups.clear()
        usuario.groups.add(grupo)
        PerfilUsuario.objects.update_or_create(usuario=usuario, defaults={'municipio': form.cleaned_data.get('municipio')})
        return JsonResponse({'sucesso': True, 'mensagem': 'Usuário cadastrado com sucesso!', 'usuario': {'id': usuario.id, 'username': usuario.username}}, status=201)
    return JsonResponse({'mensagem': 'Verifique os campos do formulário.', 'erros': form.errors.get_json_data()}, status=400)


@login_required
def ajax_editar_usuario(request, id):
    if not usuario_admin_ajax(request):
        return JsonResponse({'mensagem': 'Você não tem permissão para editar usuários.'}, status=403)
    usuario = get_object_or_404(User, pk=id)
    if usuario.is_superuser and not request.user.is_superuser:
        return JsonResponse({'mensagem': 'Você não pode editar este usuário.'}, status=403)
    if request.method != 'POST':
        return JsonResponse({'mensagem': 'Método não permitido.'}, status=405)
    form = UsuarioEdicaoForm(request.POST, instance=usuario)
    if 'municipio' in form.fields:
        form.fields['municipio'].required = False
    if form.is_valid():
        usuario = form.save(commit=False)
        senha = form.cleaned_data.get('nova_senha')
        if senha:
            usuario.set_password(senha)
        usuario.save()
        grupo, _ = Group.objects.get_or_create(name=form.cleaned_data['perfil'])
        usuario.groups.set([grupo])
        municipio = form.cleaned_data.get('municipio')
        if municipio is None:
            perfil = PerfilUsuario.objects.filter(usuario=usuario).first()
            if perfil:
                municipio = perfil.municipio
        PerfilUsuario.objects.update_or_create(usuario=usuario, defaults={'municipio': municipio})
        return JsonResponse({'sucesso': True, 'mensagem': 'Usuário atualizado com sucesso!', 'usuario': {'id': usuario.id, 'username': usuario.username}})
    return JsonResponse({'mensagem': 'Verifique os campos do formulário.', 'erros': form.errors.get_json_data()}, status=400)


@login_required
def ajax_excluir_usuario(request, id):
    if not usuario_admin_ajax(request):
        return JsonResponse({'mensagem': 'Você não tem permissão para excluir usuários.'}, status=403)
    if request.method != 'POST':
        return JsonResponse({'mensagem': 'Método não permitido.'}, status=405)
    usuario = get_object_or_404(User, pk=id)
    if usuario.pk == request.user.pk:
        return JsonResponse({'mensagem': 'Você não pode excluir seu próprio usuário.'}, status=400)
    if usuario.is_superuser and not request.user.is_superuser:
        return JsonResponse({'mensagem': 'Você não pode excluir este usuário.'}, status=403)
    nome = usuario.username
    usuario.delete()
    return JsonResponse({'sucesso': True, 'mensagem': f'Usuário {nome} excluído com sucesso!'})
