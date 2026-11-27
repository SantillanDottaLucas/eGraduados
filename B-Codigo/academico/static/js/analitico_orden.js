/*
 * Reorden de materias en la previsualización del analítico.
 *
 * El servidor sigue leyendo `fila_orden` (un hidden por fila). Acá
 * sólo se intercambian filas completas del <tbody> y se renumera ese
 * hidden junto con la posición visible. `fila_indice` NO se toca: es
 * la clave estable que usan los radios de requisito y el botón Quitar.
 */

(function () {
    "use strict";

    const cuerpo = document.querySelector(".documento-tabla tbody");

    if (!cuerpo) {
        return;
    }

    function filas() {
        return Array.from(cuerpo.querySelectorAll("tr"));
    }

    function renumerar() {
        const lista = filas();

        lista.forEach(function (fila, indice) {
            const posicion = indice + 1;

            const visible = fila.querySelector(".fila-orden");
            if (visible) {
                visible.textContent = String(posicion);
            }

            const oculto = fila.querySelector('input[name="fila_orden"]');
            if (oculto) {
                oculto.value = String(posicion);
            }

            const arriba = fila.querySelector('[data-mover="arriba"]');
            if (arriba) {
                arriba.disabled = indice === 0;
            }

            const abajo = fila.querySelector('[data-mover="abajo"]');
            if (abajo) {
                abajo.disabled = indice === lista.length - 1;
            }
        });
    }

    cuerpo.addEventListener("click", function (evento) {
        const boton = evento.target.closest("[data-mover]");

        if (!boton || boton.disabled) {
            return;
        }

        const fila = boton.closest("tr");
        if (!fila) {
            return;
        }

        if (boton.dataset.mover === "arriba" && fila.previousElementSibling) {
            cuerpo.insertBefore(fila, fila.previousElementSibling);
        } else if (boton.dataset.mover === "abajo" && fila.nextElementSibling) {
            cuerpo.insertBefore(fila.nextElementSibling, fila);
        } else {
            return;
        }

        renumerar();
    });

    renumerar();
})();
