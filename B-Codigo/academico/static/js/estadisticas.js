document.addEventListener("DOMContentLoaded", function () {

    // ==========================================
    // 1. CONTROL DE LOS FILTROS
    // ==========================================

    document.querySelectorAll(".formulario-estadistica").forEach(formulario => {

        const filtros = formulario.querySelectorAll('input[name="filtro"]');
        const campoEscuela = formulario.querySelector(".campoEscuela");
        const campoCarrera = formulario.querySelector(".campoCarrera");

        if (!campoEscuela || !campoCarrera || filtros.length === 0) {
            return;
        }

        function actualizarFiltro() {
            const filtroSeleccionado =
                formulario.querySelector('input[name="filtro"]:checked');

            const filtro = filtroSeleccionado
                ? filtroSeleccionado.value
                : "todos";

            // Habilitar solamente el campo correspondiente.
            campoEscuela.disabled = filtro !== "escuela";
            campoCarrera.disabled = filtro !== "carrera";

            // Mostrar solamente el campo correspondiente.
            campoEscuela.hidden = filtro !== "escuela";
            campoCarrera.hidden = filtro !== "carrera";

            // Exigir una selección cuando corresponda.
            campoEscuela.required = filtro === "escuela";
            campoCarrera.required = filtro === "carrera";

            // Limpiar los campos que no se utilizan.
            if (filtro !== "escuela") {
                campoEscuela.value = "";
            }

            if (filtro !== "carrera") {
                campoCarrera.value = "";
            }
        }

        filtros.forEach(filtro => {
            filtro.addEventListener("change", actualizarFiltro);
        });

        actualizarFiltro();
    });


    // ==========================================
    // 2. GENERACIÓN DE LOS GRÁFICOS
    // ==========================================

    document.querySelectorAll(".grafico-contenedor").forEach(contenedor => {

        const canvas = contenedor.querySelector("canvas");
        const idDatos = contenedor.dataset.datos;
        const elementoDatos = document.getElementById(idDatos);

        if (!canvas || !elementoDatos) {
            return;
        }

        let datos;

        try {
            datos = JSON.parse(elementoDatos.textContent);
        } catch (error) {
            console.error("No se pudieron interpretar los datos del gráfico:", error);
            canvas.hidden = true;
            return;
        }

        // Comprobar que existan etiquetas y valores.
        if (
            !datos ||
            !Array.isArray(datos.etiquetas) ||
            !Array.isArray(datos.valores) ||
            datos.etiquetas.length === 0 ||
            datos.valores.length === 0
        ) {
            canvas.hidden = true;
            return;
        }

        // Evitar representar gráficos sin datos numéricos.
        const hayValores = datos.valores.some(valor =>
            valor !== null &&
            valor !== "" &&
            Number.isFinite(Number(valor))
        );

        if (!hayValores) {
            canvas.hidden = true;
            return;
        }

        canvas.hidden = false;

        // El título se determina según el conjunto de datos.
        let titulo = "Estadística";

        if (idDatos === "datos-promedios") {
            titulo = "Promedios académicos";
        } else if (idDatos === "datos-totales") {
            titulo = "Cantidad de graduados";
        } else if (idDatos === "datos-tiempos") {
            titulo = "Tiempo promedio de graduación";
        }

        // El eje Y debe adaptarse a cada estadística.
        const opcionesEscala = {
            beginAtZero: true
        };

        if (idDatos === "datos-promedios") {
            opcionesEscala.min = 0;
            opcionesEscala.max = 10;
        }

        new Chart(canvas, {
            type: "bar",

            data: {
                labels: datos.etiquetas,

                datasets: [{
                    label: titulo,
                    data: datos.valores.map(valor =>
                        valor === null || valor === ""
                            ? null
                            : Number(valor)
                    ),
                    borderWidth: 1,
                    borderRadius: 5
                }]
            },

            options: {
                responsive: true,
                maintainAspectRatio: false,

                plugins: {
                    legend: {
                        display: false
                    },

                    tooltip: {
                        enabled: true
                    }
                },

                scales: {
                    y: opcionesEscala
                }
            }
        });
    });

});
