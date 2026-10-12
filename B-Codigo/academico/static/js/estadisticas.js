const filtroEscuela = document.getElementById("filtroEscuela");
const filtroCarrera = document.getElementById("filtroCarrera");

const campoEscuela = document.getElementById("campoEscuela");
const campoCarrera = document.getElementById("campoCarrera");

function actualizarFiltro(){
    campoEscuela.disabled = !filtroEscuela.checked; 
    campoEscuela.required = filtroEscuela.checked;

    campoCarrera.disabled = !filtroCarrera.checked;
    campoCarrera.required = filtroCarrera.checked;
}
filtroEscuela.addEventListener("change",actualizarFiltro);
filtroCarrera.addEventListener("change",actualizarFiltro);


actualizarFiltro();


const canvas=document.getElementById("graficoPromedios");
const mensaje = document.getElementById("mensajeSinDatos");
const jsonDatos= document.getElementById("datos-grafico");

if (canvas && jsonDatos) {
    const datos= JSON.parse(jsonDatos.textContent);

    if(datos == null || datos.valores.length === 0){
        canvas.hidden=true;
        mensaje.hidden=false;
    }else{
        canvas.hidden= false;
        mensaje.hidden=true;
        new Chart(canvas, {
            type: 'bar',
            data: {
                labels: datos.etiquetas,
                datasets: [{
                    label: 'Promedio de graduados',
                    data: datos.valores
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio:false,
                scales: {
                    y: {
                        min: 0,
                        max: 12
                    }
                }
            }
        });
    }
}

console.log(canvas)