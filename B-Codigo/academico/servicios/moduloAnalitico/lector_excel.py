import pandas as pd

def leer_excel(archivo):
    datos= pd.read_excel(archivo, usecols=[
        "carrera",
        "legajo", 
        "nombre_alumno",
        "nombre_materia",
        "fecha_regular",
        "fecha_examen",
        "materia", 
        "acta_final",
        "res_final",
        "tipo"])
    materias=[]

    for indice,fila in datos.iterrows():               
        materia = {
            "nombre_materia": fila["nombre_materia"],
            "fecha_regular": fila["fecha_regular"],
            "fecha_examen": fila["fecha_examen"],
            "codigo_materia":fila["materia"],
            "acta_respaldatoria": fila["acta_final"],
            "tipo":fila["tipo"]
        }
        if str(fila["tipo"]).strip() == "Equivalencia":
            materia["acta_respaldatoria"] = fila["res_final"]

    return {
        "carrera": datos.iloc[0]["carrera"],
        "legajo":  datos.iloc[0]["legajo"],
        "nombre_alumno":  datos.iloc[0]["nombre_alumno"],
        "materias": materias
    }

