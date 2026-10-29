document.addEventListener("DOMContentLoaded", function () {
  console.log("estadisticas.js cargado correctamente");
  console.log("Chart disponible:", typeof Chart);
  console.log(
    "Formularios encontrados:",
    document.querySelectorAll(".formulario-estadistica").length,
  );
  console.log(
    "Gráficos encontrados:",
    document.querySelectorAll(".grafico-contenedor").length,
  );

  document.querySelectorAll(".formulario-estadistica").forEach(formulario => {

    formulario.addEventListener("submit", function () {
        sessionStorage.setItem(
            "posicionEstadisticas",
            window.scrollY
        );
    });

});

const posicionGuardada = sessionStorage.getItem("posicionEstadisticas");

if (posicionGuardada !== null) {
    window.scrollTo(0, Number(posicionGuardada));
    sessionStorage.removeItem("posicionEstadisticas");
}

  // ==========================================
  // 1. CONTROL DE LOS FILTROS
  // ==========================================

  document.querySelectorAll(".formulario-estadistica").forEach((formulario) => {
    const filtros = formulario.querySelectorAll('input[name="filtro"]');
    const campoEscuela = formulario.querySelector(".campoEscuela");
    const campoCarrera = formulario.querySelector(".campoCarrera");

    function actualizarFiltro() {
      const seleccionado = formulario.querySelector(
        'input[name="filtro"]:checked',
      );

      const filtro = seleccionado?.value || "todos";
      const mostrarEscuela = filtro === "escuela";
      const mostrarCarrera = filtro === "carrera";

      if (campoEscuela) {
        campoEscuela.hidden = !mostrarEscuela;
        campoEscuela.disabled = !mostrarEscuela;
        campoEscuela.required = mostrarEscuela;

        if (!mostrarEscuela) {
          campoEscuela.value = "";
        }
      }

      if (campoCarrera) {
        campoCarrera.hidden = !mostrarCarrera;
        campoCarrera.disabled = !mostrarCarrera;
        campoCarrera.required = mostrarCarrera;

        if (!mostrarCarrera) {
          campoCarrera.value = "";
        }
      }
    }

    filtros.forEach((filtro) => {
      filtro.addEventListener("change", actualizarFiltro);
    });

    actualizarFiltro();
  });

  // ==========================================
  // 2. CONFIGURACIÓN DE LOS GRÁFICOS
  // ==========================================

  const configuraciones = {
    "datos-promedios": {
      titulo: "Promedios académicos",
      etiqueta: "Promedio",
      ejeY: "Calificación",
      tipo: "bar",
      maximo: 10,
      decimales: 2,
    },

    "datos-totales": {
      titulo: "Cantidad de graduados",
      etiqueta: "Graduados",
      ejeY: "Cantidad de graduados",
      tipo: "bar",
      decimales: 0,
    },

    "datos-tiempos": {
      titulo: "Tiempo de graduación",
      etiqueta: "Duración",
      ejeY: "Años",
      tipo: "bar",
      decimales: 2,
    },
  };

  // ==========================================
  // 3. FORMATO DE LOS VALORES
  // ==========================================

  function formatearNumero(valor, decimales) {
    return Number(valor).toLocaleString("es-AR", {
      minimumFractionDigits: 0,
      maximumFractionDigits: decimales,
    });
  }

  // ==========================================
  // 4. CREACIÓN DE LOS GRÁFICOS
  // ==========================================

  if (typeof Chart === "undefined") {
    console.error(
      "Chart.js no está cargado. Revisá su inclusión en base.html.",
    );
    return;
  }

  document.querySelectorAll(".grafico-contenedor").forEach((contenedor) => {
    const canvas = contenedor.querySelector("canvas");
    const idDatos = contenedor.dataset.datos;
    const elementoDatos = document.getElementById(idDatos);
    const mensaje = contenedor.querySelector(".mensaje-sin-datos");

    if (!canvas || !elementoDatos) {
      console.warn("Falta el canvas o los datos para:", idDatos);
      return;
    }

    let datos;

    try {
      datos = JSON.parse(elementoDatos.textContent);
    } catch (error) {
      console.error("Error al leer los datos de", idDatos, error);
      canvas.hidden = true;

      if (mensaje) {
        mensaje.hidden = false;
        mensaje.textContent = "No se pudieron cargar los datos.";
      }

      return;
    }

    if (
      !Array.isArray(datos.etiquetas) ||
      !Array.isArray(datos.valores) ||
      datos.etiquetas.length === 0 ||
      datos.etiquetas.length !== datos.valores.length
    ) {
      canvas.hidden = true;

      if (mensaje) {
        mensaje.hidden = false;
        mensaje.textContent = "No hay datos disponibles para graficar.";
      }

      return;
    }

    const valores = datos.valores.map((valor) => {
      if (valor === null || valor === "") {
        return null;
      }

      const numero = Number(valor);

      return Number.isFinite(numero) ? numero : null;
    });

    if (!valores.some((valor) => valor !== null)) {
      canvas.hidden = true;

      if (mensaje) {
        mensaje.hidden = false;
        mensaje.textContent = "No hay valores numéricos para mostrar.";
      }

      return;
    }

    const configuracion = configuraciones[idDatos] || {
      titulo: "Estadística",
      etiqueta: "Valor",
      ejeY: "Valor",
      tipo: "bar",
      decimales: 2,
    };

    canvas.hidden = false;

    if (mensaje) {
      mensaje.hidden = true;
    }

    // Evita duplicar gráficos si se vuelve a ejecutar el código.
    const graficoExistente = Chart.getChart(canvas);

    if (graficoExistente) {
      graficoExistente.destroy();
    }

    new Chart(canvas, {
      type: configuracion.tipo,

      data: {
        labels: datos.etiquetas,

        datasets: [
          {
            label: configuracion.etiqueta,
            data: valores,
            borderWidth: 2,
            borderRadius: 5,
            maxBarThickness: 65,
            tension: 0.3,
            spanGaps: false,
          },
        ],
      },

      options: {
        responsive: true,
        maintainAspectRatio: false,

        interaction: {
          intersect: false,
          mode: "index",
        },

        plugins: {
          legend: {
            display: true,
            position: "bottom",
          },

          title: {
            display: true,
            text: configuracion.titulo,
          },

          tooltip: {
            callbacks: {
              label: function (contexto) {
                const valor = contexto.parsed.y;

                if (valor === null || valor === undefined) {
                  return "Sin datos";
                }

                let texto =
                  configuracion.etiqueta +
                  ": " +
                  formatearNumero(valor, configuracion.decimales);

                if (idDatos === "datos-tiempos") {
                  texto += " años";
                }

                return texto;
              },
            },
          },
        },

        scales: {
          x: {
            title: {
              display: true,
              text: "Categoría",
            },

            ticks: {
              autoSkip: true,
              maxRotation: 45,
              minRotation: 0,
            },
          },

          y: {
            beginAtZero: true,

            ...(configuracion.maximo !== undefined
              ? { max: configuracion.maximo }
              : {}),

            title: {
              display: true,
              text: configuracion.ejeY,
            },
          },
        },
      },
    });
  });
});
