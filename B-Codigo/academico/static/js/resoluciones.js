/*
 * Campos repetibles de resoluciones/instrumentos legales.
 *
 * Cada grupo marca:
 *   data-nombre="resoluciones_institucionales"
 *   data-requeridas="1"  (0 si el campo es opcional)
 *
 * Todos los inputs comparten el mismo name, de modo que la vista
 * los recupera con request.POST.getlist().
 */

(function () {
    "use strict";

    function actualizar(grupo) {
        const contenedor = grupo.querySelector(".resoluciones-items");
        if (!contenedor) {
            return;
        }

        const nombre = grupo.dataset.nombre || "resolucion";
        const requeridas = grupo.dataset.requeridas === "1";
        const inputs = contenedor.querySelectorAll(".resolucion-input");

        inputs.forEach(function (input, indice) {
            input.name = nombre;
            input.required = requeridas && indice === 0;

            const boton = input
                .closest(".resolucion-item")
                .querySelector(".resolucion-quitar");

            if (boton) {
                boton.disabled = inputs.length === 1;
            }
        });
    }

    document.querySelectorAll(".resoluciones-repetibles").forEach(function (grupo) {
        const contenedor = grupo.querySelector(".resoluciones-items");
        const agregar = grupo.querySelector(".resolucion-agregar");

        if (!contenedor || !agregar) {
            return;
        }

        agregar.addEventListener("click", function () {
            const item = document.createElement("div");
            item.className = "input-group input-group-sm mb-2 resolucion-item";

            const input = document.createElement("input");
            input.type = "text";
            input.className = "form-control resolucion-input";
            input.setAttribute("data-nombre", grupo.dataset.nombre || "");

            const boton = document.createElement("button");
            boton.type = "button";
            boton.className = "btn btn-outline-danger resolucion-quitar";
            boton.setAttribute("aria-label", "Quitar resolución");
            boton.innerHTML = '<i class="bi bi-x-lg" aria-hidden="true"></i>';

            item.appendChild(input);
            item.appendChild(boton);
            contenedor.appendChild(item);
            actualizar(grupo);
            input.focus();
        });

        contenedor.addEventListener("click", function (evento) {
            const boton = evento.target.closest(".resolucion-quitar");
            if (!boton) {
                return;
            }

            const item = boton.closest(".resolucion-item");
            if (item && contenedor.querySelectorAll(".resolucion-item").length > 1) {
                item.remove();
                actualizar(grupo);
            }
        });

        actualizar(grupo);
    });
})();
