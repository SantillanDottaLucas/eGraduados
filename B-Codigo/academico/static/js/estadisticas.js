
document.querySelectorAll("form").forEach(form => {
    const filtroTodos = form.querySelector(".filtroTodos");
    const filtroEscuela = form.querySelector(".filtroEscuela");
    const filtroCarrera = form.querySelector(".filtroCarrera");

    const campoEscuela = form.querySelector(".campoEscuela");
    const campoCarrera = form.querySelector(".campoCarrera");

    if (!filtroTodos || !filtroEscuela || !filtroCarrera ||
        !campoEscuela || !campoCarrera) {
        return;
    }

    function actualizarFiltro() {
        campoEscuela.disabled = !filtroEscuela.checked;
        campoEscuela.required = filtroEscuela.checked;

        campoCarrera.disabled = !filtroCarrera.checked;
        campoCarrera.required = filtroCarrera.checked;
    }

    filtroTodos.addEventListener("change", actualizarFiltro);
    filtroEscuela.addEventListener("change", actualizarFiltro);
    filtroCarrera.addEventListener("change", actualizarFiltro);

    actualizarFiltro();
});



document.querySelectorAll(".contenedorGrafico").forEach(contenedor => {
    const canvas = contenedor.querySelector(".graficoPromedios");
    const mensaje = contenedor.querySelector(".mensajeSinDatos");
    const idDatos = contenedor.dataset.datos;
    const jsonDatos = document.getElementById(idDatos);

    if (!canvas || !mensaje || !jsonDatos) {
        return;
    }

    const datos = JSON.parse(jsonDatos.textContent);

    if (datos === null || !datos.valores || datos.valores.length === 0) {
        canvas.hidden = true;
        mensaje.hidden = false;
    } else {
        canvas.hidden = false;
        mensaje.hidden = true;

        new Chart(canvas, {
            type: "bar",
            data: {
                labels: datos.etiquetas,
                datasets: [{
                    label: "Estadística",
                    data: datos.valores
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    y: {
                        min: 0,
                        max: 12
                    }
                }
            }
        });
    }
});