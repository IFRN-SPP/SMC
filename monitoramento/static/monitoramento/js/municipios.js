document.addEventListener("DOMContentLoaded", function () {
    const formulario = document.querySelector("#municipioForm");

    function obterCSRFToken() {
        const campo = document.querySelector("[name=csrfmiddlewaretoken]");

        if (campo) {
            return campo.value;
        }

        const cookies = document.cookie.split(";");

        for (let cookie of cookies) {
            cookie = cookie.trim();

            if (cookie.startsWith("csrftoken=")) {
                return cookie.substring("csrftoken=".length);
            }
        }

        return "";
    }

    function mostrarErros(erros) {
        let mensagem = "";

        for (const campo in erros) {
            erros[campo].forEach(erro => {
                mensagem += campo + ": " + erro.message + "\n";
            });
        }

        alert(mensagem || "Verifique os dados informados.");
    }

    if (formulario) {
        formulario.addEventListener("submit", function (evento) {
            evento.preventDefault();

            const botao = formulario.querySelector("button[type='submit']");
            const textoOriginal = botao.textContent;

            botao.disabled = true;
            botao.textContent = "Salvando...";

            fetch(formulario.dataset.ajaxUrl, {
                method: "POST",
                body: new FormData(formulario),
                headers: {
                    "X-Requested-With": "XMLHttpRequest",
                    "X-CSRFToken": obterCSRFToken()
                }
            })
            .then(async response => {
                const dados = await response.json();

                if (!response.ok) {
                    throw dados;
                }

                return dados;
            })
            .then(resposta => {
                alert(resposta.mensagem);
                window.location.href = "/municipios/";
            })
            .catch(erro => {
                if (erro.erros) {
                    mostrarErros(erro.erros);
                } else {
                    alert(erro.mensagem || "Não foi possível salvar o município.");
                }

                botao.disabled = false;
                botao.textContent = textoOriginal;
            });
        });
    }

    document.addEventListener("click", function (evento) {
        const botao = evento.target.closest(".btn-excluir-municipio");

        if (!botao) {
            return;
        }

        evento.preventDefault();

        if (botao.disabled) {
            return;
        }

        if (!confirm("Tem certeza que deseja excluir este município?")) {
            return;
        }

        botao.disabled = true;
        botao.textContent = "Excluindo...";

        fetch(botao.dataset.url, {
            method: "POST",
            headers: {
                "X-Requested-With": "XMLHttpRequest",
                "X-CSRFToken": obterCSRFToken()
            }
        })
        .then(async response => {
            const dados = await response.json();

            if (!response.ok) {
                throw dados;
            }

            return dados;
        })
        .then(resposta => {
            alert(resposta.mensagem);
            const linha = botao.closest("tr");

            if (linha) {
                linha.remove();
            }

            const tabela = document.querySelector("tbody");

            if (tabela && tabela.querySelectorAll("tr").length === 0) {
                tabela.innerHTML = `
                    <tr>
                        <td colspan="3" class="empty">
                            Nenhum município cadastrado ainda.
                        </td>
                    </tr>
                `;
            }
        })
        .catch(erro => {
            alert(erro.mensagem || "Não foi possível excluir o município.");
            botao.disabled = false;
            botao.textContent = "Excluir";
        });
    });
});
