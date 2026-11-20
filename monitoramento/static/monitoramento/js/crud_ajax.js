document.addEventListener("DOMContentLoaded", function () {
    function csrfToken() {
        const field = document.querySelector("[name=csrfmiddlewaretoken]");
        if (field) return field.value;
        for (const item of document.cookie.split(";")) {
            const cookie = item.trim();
            if (cookie.startsWith("csrftoken=")) return cookie.slice(10);
        }
        return "";
    }

    function errorText(data) {
        if (data && data.erros) {
            let text = "";
            for (const field in data.erros) {
                data.erros[field].forEach(error => { text += field + ": " + error.message + "\n"; });
            }
            return text || data.mensagem || "Verifique os dados.";
        }
        return data && data.mensagem ? data.mensagem : "Não foi possível concluir a operação.";
    }

    document.querySelectorAll("form[data-ajax-url]").forEach(function (form) {
        form.addEventListener("submit", function (event) {
            event.preventDefault();
            const button = form.querySelector("button[type=submit]");
            const original = button ? button.textContent : "";
            if (button) { button.disabled = true; button.textContent = "Salvando..."; }
            fetch(form.dataset.ajaxUrl, {
                method: "POST",
                body: new FormData(form),
                headers: { "X-Requested-With": "XMLHttpRequest", "X-CSRFToken": csrfToken() }
            })
            .then(async response => {
                const data = await response.json();
                if (!response.ok) throw data;
                return data;
            })
            .then(data => {
                alert(data.mensagem || "Registro salvo com sucesso!");
                window.location.href = form.dataset.redirectUrl || window.location.href;
            })
            .catch(error => {
                alert(errorText(error));
                if (button) { button.disabled = false; button.textContent = original; }
            });
        });
    });

    document.addEventListener("click", function (event) {
        const button = event.target.closest(".ajax-delete");
        if (!button || button.disabled) return;
        event.preventDefault();
        if (!confirm(button.dataset.confirm || "Tem certeza que deseja excluir este registro?")) return;
        const original = button.textContent;
        button.disabled = true;
        button.textContent = "Excluindo...";
        fetch(button.dataset.url, {
            method: "POST",
            headers: { "X-Requested-With": "XMLHttpRequest", "X-CSRFToken": csrfToken() }
        })
        .then(async response => {
            const data = await response.json();
            if (!response.ok) throw data;
            return data;
        })
        .then(data => {
            alert(data.mensagem || "Registro excluído com sucesso!");
            const row = button.closest(".crud-row");
            if (row) row.remove();
        })
        .catch(error => {
            alert(errorText(error));
            button.disabled = false;
            button.textContent = original;
        });
    });

    document.addEventListener("click", function (event) {
        const button = event.target.closest(".ajax-resolver-alerta");
        if (!button || button.disabled) return;
        button.disabled = true;
        const original = button.textContent;
        button.textContent = "Atualizando...";
        fetch(button.dataset.url, {
            method: "POST",
            headers: { "X-Requested-With": "XMLHttpRequest", "X-CSRFToken": csrfToken() }
        })
        .then(async response => {
            const data = await response.json();
            if (!response.ok) throw data;
            return data;
        })
        .then(data => {
            const card = button.closest(".alerta-card");
            if (card) {
                card.classList.add("resolvido");
                const status = card.querySelector(".status-pendente");
                if (status) { status.className = "alerta-status status-resolvido"; status.textContent = "Resolvido"; }
                const icon = card.querySelector(".alerta-icone");
                if (icon) { icon.className = "alerta-icone resolvido-icone"; icon.textContent = "✓"; }
                button.closest("form")?.remove();
            }
            alert(data.mensagem || "Alerta resolvido!");
        })
        .catch(error => {
            alert(errorText(error));
            button.disabled = false;
            button.textContent = original;
        });
    });
});
