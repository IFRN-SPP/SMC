document.addEventListener("DOMContentLoaded", function () {

    const campoImagem = document.getElementById("id_imagem");
    const campoSituacao = document.getElementById("id_situacao");
    const campoLatitude = document.getElementById("id_latitude");
    const campoLongitude = document.getElementById("id_longitude");
    const formulario = document.getElementById("cisternaForm");
    const imagemPreview = document.getElementById("imagePreview");
    const imagemVazia = document.getElementById("imageEmpty");
    const removerImagem = document.getElementById("removeImage");
    const situacaoPreview = document.getElementById("situacaoPreview");
    const marcador = document.getElementById("mapMarker");
    const mensagemMapa = document.getElementById("mapMessage");

    if (campoImagem) {
        campoImagem.addEventListener("change", function () {
            const arquivo = this.files[0];

            if (!arquivo) {
                return;
            }

            if (!arquivo.type.startsWith("image/")) {
                alert("Selecione uma imagem válida.");
                this.value = "";
                return;
            }

            const leitor = new FileReader();

            leitor.onload = function (evento) {
                if (imagemPreview) {
                    imagemPreview.src = evento.target.result;
                    imagemPreview.style.display = "block";
                }

                if (imagemVazia) {
                    imagemVazia.style.display = "none";
                }
            };

            leitor.readAsDataURL(arquivo);
        });
    }

    if (removerImagem) {
        removerImagem.addEventListener("click", function () {
            if (campoImagem) {
                campoImagem.value = "";
            }

            if (imagemPreview) {
                imagemPreview.src = "";
                imagemPreview.style.display = "none";
            }

            if (imagemVazia) {
                imagemVazia.style.display = "flex";
            }
        });
    }

    function atualizarSituacao() {
        if (!campoSituacao || !situacaoPreview) {
            return;
        }

        const valor = campoSituacao.value;

        const nomes = {
            normal: "Normal",
            atencao: "Atenção",
            critico: "Crítico",
            sem_dados: "Sem dados"
        };

        situacaoPreview.className = "situacao-preview " + valor;

        const texto = situacaoPreview.querySelector("strong");

        if (texto) {
            texto.textContent = nomes[valor] || "Sem dados";
        }
    }

    if (campoSituacao) {
        campoSituacao.addEventListener("change", atualizarSituacao);
        atualizarSituacao();
    }

    function atualizarMapa() {
        if (!campoLatitude || !campoLongitude || !marcador || !mensagemMapa) {
            return;
        }

        const latitude = parseFloat(campoLatitude.value);
        const longitude = parseFloat(campoLongitude.value);

        if (Number.isNaN(latitude) || Number.isNaN(longitude)) {
            marcador.style.display = "none";
            mensagemMapa.style.display = "flex";
            return;
        }

        let esquerda = ((longitude + 180) / 360) * 100;
        let topo = ((90 - latitude) / 180) * 100;

        esquerda = Math.max(5, Math.min(95, esquerda));
        topo = Math.max(8, Math.min(88, topo));

        marcador.style.left = esquerda + "%";
        marcador.style.top = topo + "%";
        marcador.style.display = "flex";
        mensagemMapa.style.display = "none";
    }

    if (campoLatitude) {
        campoLatitude.addEventListener("input", atualizarMapa);
    }

    if (campoLongitude) {
        campoLongitude.addEventListener("input", atualizarMapa);
    }

    atualizarMapa();

    if (formulario) {
        formulario.addEventListener("submit", function (evento) {
            const identificacao = document.getElementById("id_identificacao");

            if (identificacao && !identificacao.value.trim()) {
                evento.preventDefault();
                alert("Informe a identificação da cisterna.");
                identificacao.focus();
                return;
            }

            if (campoSituacao && !campoSituacao.value) {
                evento.preventDefault();
                alert("Selecione a situação da cisterna.");
                campoSituacao.focus();
            }
        });
    }

    if (formulario && formulario.dataset.ajaxUrl) {
        formulario.addEventListener("submit", function (evento) {
            evento.preventDefault();

            const dados = new FormData(formulario);

            fetch(formulario.dataset.ajaxUrl, {
                method: "POST",
                body: dados,
                headers: {
                    "X-Requested-With": "XMLHttpRequest"
                }
            })
            .then(response => response.json())
            .then(resposta => {
                if (resposta.erros) {
                    let mensagem = "";

                    for (const campo in resposta.erros) {
                        resposta.erros[campo].forEach(erro => {
                            mensagem += campo + ": " + erro.message + "\n";
                        });
                    }

                    alert(mensagem);
                    return;
                }

                alert(resposta.mensagem);
                window.location.href = "/cisternas/";
            })
            .catch(() => {
                alert("Erro ao enviar os dados da cisterna.");
            });
        });
    }

    function obterCSRFToken() {
        const cookies = document.cookie.split(";");

        for (let cookie of cookies) {
            cookie = cookie.trim();

            if (cookie.startsWith("csrftoken=")) {
                return cookie.substring("csrftoken=".length);
            }
        }

        const campoToken = document.querySelector("[name=csrfmiddlewaretoken]");

        return campoToken ? campoToken.value : "";
    }

    document.addEventListener("click", function (evento) {
        const botao = evento.target.closest(".btn-excluir-cisterna");

        if (!botao || botao.disabled) {
            return;
        }

        evento.preventDefault();

        if (!confirm("Tem certeza que deseja excluir esta cisterna?")) {
            return;
        }

        botao.disabled = true;

        const textoOriginal = botao.textContent;

        botao.textContent = "Excluindo...";

        fetch(botao.dataset.url, {
            method: "POST",
            headers: {
                "X-CSRFToken": obterCSRFToken(),
                "X-Requested-With": "XMLHttpRequest"
            }
        })
        .then(response => {
            if (!response.ok) {
                throw new Error("Erro ao excluir cisterna.");
            }

            return response.json();
        })
        .then(resposta => {
            if (!resposta.sucesso) {
                throw new Error(resposta.mensagem || "Erro ao excluir cisterna.");
            }

            const linha = botao.closest(".cisterna-row");

            if (linha) {
                linha.remove();
            }

            alert(resposta.mensagem);
        })
        .catch(erro => {
            alert(erro.message);
            botao.disabled = false;
            botao.textContent = textoOriginal;
        });
    });

});