document.addEventListener("DOMContentLoaded", function () {
  // ==========================================
  // 1. CONTROL DEL PANEL DE FILTROS (UNIFICADO)
  // ==========================================

  var formulario = document.getElementById(
    "formulario-filtros-estadisticas"
  );

  if (formulario) {
    var filtros = formulario.querySelectorAll('input[name="filtro"]');
    var bloqueCarrera = document.getElementById("bloque-carrera");
    var bloqueEscuela = document.getElementById("bloque-escuela");
    var campoCarrera = formulario.querySelector(".campoCarrera");
    var campoEscuela = formulario.querySelector(".campoEscuela");
    var avisoCliente = document.getElementById(
      "aviso-fechas-cliente"
    );

    function actualizarFiltro() {
      var seleccionado = formulario.querySelector(
        'input[name="filtro"]:checked'
      );
      var filtro = seleccionado ? seleccionado.value : "todos";
      var mostrarCarrera = filtro === "carrera";
      var mostrarEscuela = filtro === "escuela";

      if (bloqueCarrera) {
        bloqueCarrera.hidden = !mostrarCarrera;
      }
      if (campoCarrera) {
        campoCarrera.disabled = !mostrarCarrera;
        if (!mostrarCarrera) {
          campoCarrera.value = "";
        }
      }

      if (bloqueEscuela) {
        bloqueEscuela.hidden = !mostrarEscuela;
      }
      if (campoEscuela) {
        campoEscuela.disabled = !mostrarEscuela;
        if (!mostrarEscuela) {
          campoEscuela.value = "";
        }
      }
    }

    filtros.forEach(function (radio) {
      radio.addEventListener("change", actualizarFiltro);
    });

    actualizarFiltro();

    // Validar el período en el cliente (el servidor
    // también lo valida, como defensa adicional).
    formulario.addEventListener("submit", function (evento) {
      var inicio = formulario.querySelector(
        '[name="fechaInicio"]'
      );
      var fin = formulario.querySelector('[name="fechaFin"]');

      if (avisoCliente) {
        avisoCliente.hidden = true;
        avisoCliente.textContent = "";
      }

      if (
        inicio &&
        fin &&
        inicio.value &&
        fin.value &&
        inicio.value > fin.value
      ) {
        evento.preventDefault();

        if (avisoCliente) {
          avisoCliente.hidden = false;
          avisoCliente.textContent =
            "La fecha de inicio no puede ser posterior a la fecha de fin.";
        }
      }
    });
  }

  // ==========================================
  // 2. CONFIGURACIÓN DE LOS GRÁFICOS
  // ==========================================

  var configuraciones = {
    "datos-promedios": {
      titulo: "Promedios académicos",
      etiqueta: "Promedio",
      ejeY: "Calificación",
      tipo: "bar",
      maximo: 10,
      decimales: 2,
      color: "rgba(36, 92, 166, 0.75)",
      borde: "rgba(36, 92, 166, 1)",
    },
    "datos-totales": {
      titulo: "Cantidad de graduados",
      etiqueta: "Graduados",
      ejeY: "Cantidad de graduados",
      tipo: "bar",
      decimales: 0,
      color: "rgba(25, 115, 75, 0.75)",
      borde: "rgba(25, 115, 75, 1)",
    },
    "datos-tiempos": {
      titulo: "Tiempo de graduación",
      etiqueta: "Duración",
      ejeY: "Años",
      tipo: "bar",
      decimales: 2,
      sufijo: " años",
      color: "rgba(113, 66, 166, 0.75)",
      borde: "rgba(113, 66, 166, 1)",
    },
    "datos-anios": {
      titulo: "Graduados por año",
      etiqueta: "Graduados",
      ejeY: "Cantidad de graduados",
      tipo: "bar",
      decimales: 0,
      color: "rgba(152, 98, 12, 0.75)",
      borde: "rgba(152, 98, 12, 1)",
    },
  };

  function formatearNumero(valor, decimales) {
    return Number(valor).toLocaleString("es-AR", {
      minimumFractionDigits: 0,
      maximumFractionDigits: decimales,
    });
  }

  // ==========================================
  // 3. CREACIÓN DE LOS GRÁFICOS
  // ==========================================

  if (typeof Chart === "undefined") {
    return;
  }

  document.querySelectorAll(".grafico-contenedor").forEach(function (
    contenedor
  ) {
    var canvas = contenedor.querySelector("canvas");
    var idDatos = contenedor.dataset.datos;
    var elementoDatos = document.getElementById(idDatos);
    var mensaje = contenedor.querySelector(".mensaje-sin-datos");

    if (!canvas || !elementoDatos) {
      return;
    }

    var datos;

    try {
      datos = JSON.parse(elementoDatos.textContent);
    } catch (error) {
      canvas.hidden = true;
      if (mensaje) {
        mensaje.hidden = false;
        mensaje.textContent =
          "No se pudieron cargar los datos del gráfico.";
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
        mensaje.textContent =
          "No hay datos disponibles para los filtros seleccionados.";
      }
      return;
    }

    var valores = datos.valores.map(function (valor) {
      if (valor === null || valor === "") {
        return null;
      }
      var numero = Number(valor);
      return Number.isFinite(numero) ? numero : null;
    });

    if (!valores.some(function (valor) { return valor !== null; })) {
      canvas.hidden = true;
      if (mensaje) {
        mensaje.hidden = false;
        mensaje.textContent =
          "No hay valores numéricos para mostrar.";
      }
      return;
    }

    var config = configuraciones[idDatos] || {
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

    var graficoExistente = Chart.getChart(canvas);
    if (graficoExistente) {
      graficoExistente.destroy();
    }

    new Chart(canvas, {
      type: config.tipo,
      data: {
        labels: datos.etiquetas,
        datasets: [
          {
            label: config.etiqueta,
            data: valores,
            borderWidth: 2,
            borderRadius: 5,
            maxBarThickness: 65,
            tension: 0.3,
            spanGaps: false,
            backgroundColor: config.color,
            borderColor: config.borde,
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
            text: config.titulo,
          },
          tooltip: {
            callbacks: {
              label: function (contexto) {
                var valor = contexto.parsed.y;
                if (valor === null || valor === undefined) {
                  return "Sin datos";
                }
                var texto =
                  config.etiqueta +
                  ": " +
                  formatearNumero(valor, config.decimales);
                if (config.sufijo) {
                  texto += config.sufijo;
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
            ...(config.maximo !== undefined
              ? { max: config.maximo }
              : {}),
            title: {
              display: true,
              text: config.ejeY,
            },
          },
        },
      },
    });
  });
});
