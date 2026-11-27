/*
 * Código de acceso: oculto por defecto, con vista que distingue
 * visualmente mayúsculas, minúsculas y dígitos.
 *
 * El valor real sigue siendo un <input> normal: la vista es sólo
 * un espejo decorativo con aria-hidden para no confundir a lectores
 * de pantalla.
 */

(function () {
    "use strict";

    const input = document.getElementById("codigo");
    const boton = document.getElementById("login-codigo-toggle");
    const vista = document.getElementById("codigo-visual");

    if (!input || !boton) {
        return;
    }

    function clasePara(caracter) {
        if (/[A-Z]/.test(caracter)) {
            return "codigo-mayuscula";
        }

        if (/[a-z]/.test(caracter)) {
            return "codigo-minuscula";
        }

        return "codigo-digito";
    }

    function actualizarVista() {
        if (!vista) {
            return;
        }

        vista.textContent = "";

        if (input.type !== "text" || !input.value) {
            vista.hidden = true;
            return;
        }

        vista.hidden = false;

        Array.from(input.value).forEach(function (caracter) {
            const letra = document.createElement("span");
            letra.className = clasePara(caracter);
            letra.textContent = caracter;
            vista.appendChild(letra);
        });
    }

    boton.addEventListener("click", function () {
        const mostrar = input.type === "password";

        input.type = mostrar ? "text" : "password";
        boton.setAttribute("aria-pressed", mostrar ? "true" : "false");
        boton.setAttribute(
            "aria-label",
            mostrar ? "Ocultar código de acceso" : "Mostrar código de acceso"
        );
        boton.setAttribute(
            "title",
            mostrar ? "Ocultar código" : "Mostrar código"
        );

        const icono = boton.querySelector("i");

        if (icono) {
            icono.className = mostrar
                ? "bi bi-eye-slash"
                : "bi bi-eye";
        }

        actualizarVista();
        input.focus();
    });

    input.addEventListener("input", actualizarVista);
    actualizarVista();
})();
