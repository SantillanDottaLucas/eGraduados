from datetime import date

from django.contrib.auth.hashers import make_password
import tempfile
from io import BytesIO

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from .autenticacion import CLAVE_SESION, generar_codigo_acceso
from .models import (
    Analitico,
    Auditoria,
    Carrera,
    CarreraResolucion,
    Ciudad,
    DatosNacimiento,
    Escuela,
    Examen,
    Graduado,
    GraduadoCarrera,
    GraduadoExamen,
    GrupoOptativo,
    Materia,
    OrigenPromedio,
    PlanEstudios,
    PlanEstudiosGrupoOptativo,
    PlanEstudiosMateria,
    Provincia,
    Resolucion,
    Rol,
    Secundario,
    Titulo,
    Usuario,
)
from .servicios.moduloAnalitico.promedios import calcular_promedios
from .servicios.moduloAnalitico.utilidades_texto import tipo_examen_legible
from .servicios.moduloGraduados.carga_graduados import CLAVE_PENDIENTE
from .servicios.moduloGraduados.consulta_graduados import (
    obtener_filas_busqueda,
    obtener_filas_filtradas,
)
from .servicios.validaciones import (
    validar_anios,
    validar_cronologia_fechas,
    validar_datos_graduado,
    validar_dni,
    validar_dni_unico,
)
from .servicios.legajo import generar_legajo, normalizar_dni
from .servicios.provincias import provincias_sugeridas
from .servicios.moduloCarga.carga_datos import CargaDatos
from .servicios.moduloGraduados.eliminacion import CONFIRMACION_BORRADO
from .servicios.moduloEstadistica.consulta_estadisticas import (
    consultar_graduados_por_anio,
)


class BasePrueba(TestCase):
    """Datos base: roles, usuarios y sesión iniciada."""

    @classmethod
    def setUpTestData(cls):
        cls.rol_admin = Rol.objects.create(
            nombre_rol="Administrador",
            puede_administrar=True,
        )
        cls.rol_titulos = Rol.objects.create(
            nombre_rol="Titulos",
            puede_administrar=False,
        )

        cls.codigo_admin = "Abc123"
        cls.admin = Usuario.objects.create(
            nombre_usuario="Admin",
            email="admin@gmail.com",
            codigo_acceso=make_password(cls.codigo_admin),
            id_rol=cls.rol_admin,
        )

        cls.codigo_titulos = "XyZ789"
        cls.titulos = Usuario.objects.create(
            nombre_usuario="Titulos",
            email="titulos@gmail.com",
            codigo_acceso=make_password(cls.codigo_titulos),
            id_rol=cls.rol_titulos,
        )

    def iniciar_sesion(self, usuario):
        sesion = self.client.session
        sesion[CLAVE_SESION] = usuario.id_usuario
        sesion.save()


class LoginTest(BasePrueba):
    def test_login_valido(self):
        respuesta = self.client.post(
            reverse("login"),
            {"email": "titulos@gmail.com", "codigo": self.codigo_titulos},
        )

        self.assertRedirects(respuesta, reverse("index"))
        self.assertEqual(
            self.client.session.get(CLAVE_SESION),
            self.titulos.id_usuario,
        )

    def test_login_codigo_incorrecto(self):
        respuesta = self.client.post(
            reverse("login"),
            {"email": "titulos@gmail.com", "codigo": "000000"},
        )

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "incorrectos")
        self.assertIsNone(self.client.session.get(CLAVE_SESION))

    def test_login_email_inexistente(self):
        respuesta = self.client.post(
            reverse("login"),
            {"email": "nadie@gmail.com", "codigo": "Abc123"},
        )

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "incorrectos")

    def test_vista_protegida_redirige(self):
        respuesta = self.client.get(reverse("lista_graduados"))

        self.assertEqual(respuesta.status_code, 302)
        self.assertIn(reverse("login"), respuesta.url)


class PermisosTest(BasePrueba):
    def test_titulos_no_accede_abm_usuarios(self):
        self.iniciar_sesion(self.titulos)

        respuesta = self.client.get(reverse("abm_usuarios"))

        self.assertEqual(respuesta.status_code, 403)
        self.assertContains(respuesta, "Acceso denegado", status_code=403)

    def test_admin_accede_abm_usuarios(self):
        self.iniciar_sesion(self.admin)

        respuesta = self.client.get(reverse("abm_usuarios"))

        self.assertEqual(respuesta.status_code, 200)

    def test_titulos_accede_lista_graduados(self):
        self.iniciar_sesion(self.titulos)

        respuesta = self.client.get(reverse("lista_graduados"))

        self.assertEqual(respuesta.status_code, 200)


class EdicionGraduadoTest(BasePrueba):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()

        cls.escuela = Escuela.objects.create(
            nombre_escuela="Escuela de Prueba"
        )
        cls.carrera = Carrera.objects.create(
            codigo_carrera="CAR1",
            nombre_carrera="Carrera de Prueba",
            id_escuela=cls.escuela,
        )
        cls.graduado = Graduado.objects.create(
            dni="12345678",
            anio_ingreso_universidad=2015,
            nombre="Ana",
            apellido="Perez",
        )
        cls.registro = GraduadoCarrera.objects.create(
            dni_graduado=cls.graduado,
            codigo_carrera=cls.carrera,
            fecha_ingreso_carrera=date(2016, 3, 1),
            fecha_egreso_carrera=date(2020, 12, 15),
            promedio_con_aplazo=7.5,
            promedio_sin_aplazo=8.0,
        )

    def test_editar_graduado_valido(self):
        self.iniciar_sesion(self.titulos)

        respuesta = self.client.post(
            reverse("editar_graduado", args=["12345678", "CAR1"]),
            {
                "codigo_carrera": "CAR1",
                "nombre": "Ana Maria",
                "apellido": "Perez",
                "dni": "12345678",
                "anio_ingreso_universidad": "2015",
                "fecha_ingreso_carrera": "2016-03-01",
                "fecha_egreso_carrera": "2020-12-15",
                "promedio_sin_aplazo": "8.5",
                "promedio_con_aplazo": "8.0",
            },
        )

        self.assertEqual(respuesta.status_code, 302)
        self.graduado.refresh_from_db()
        self.registro.refresh_from_db()
        self.assertEqual(self.graduado.nombre, "Ana Maria")
        self.assertEqual(self.registro.promedio_sin_aplazo, 8.5)

    def test_editar_fechas_incoherentes(self):
        self.iniciar_sesion(self.titulos)

        respuesta = self.client.post(
            reverse("editar_graduado", args=["12345678", "CAR1"]),
            {
                "codigo_carrera": "CAR1",
                "nombre": "Ana",
                "apellido": "Perez",
                "dni": "12345678",
                "anio_ingreso_universidad": "2015",
                "fecha_ingreso_carrera": "2021-03-01",
                "fecha_egreso_carrera": "2020-12-15",
                "promedio_sin_aplazo": "8.0",
                "promedio_con_aplazo": "7.5",
            },
        )

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "egreso")

    def test_dni_no_se_puede_cambiar_desde_el_formulario(self):
        """El DNI es la PK: un POST manipulado no la modifica."""

        self.iniciar_sesion(self.titulos)

        respuesta = self.client.post(
            reverse("editar_graduado", args=["12345678", "CAR1"]),
            {
                "codigo_carrera": "CAR1",
                "nombre": "Ana",
                "apellido": "Perez",
                "dni": "99999999",
                "anio_ingreso_universidad": "2015",
                "fecha_ingreso_carrera": "2016-03-01",
                "fecha_egreso_carrera": "2020-12-15",
                "promedio_sin_aplazo": "8.0",
                "promedio_con_aplazo": "7.5",
            },
        )

        self.assertEqual(respuesta.status_code, 302)
        graduado = Graduado.objects.get(pk="12345678")
        self.assertEqual(graduado.dni, "12345678")
        self.assertFalse(Graduado.objects.filter(pk="99999999").exists())

    def test_editar_legacy_con_nulls(self):
        registro = GraduadoCarrera.objects.get(
            dni_graduado=self.graduado,
            codigo_carrera=self.carrera,
        )
        registro.promedio_sin_aplazo = None
        registro.promedio_con_aplazo = None
        registro.save()

        self.iniciar_sesion(self.titulos)

        respuesta = self.client.get(
            reverse("editar_graduado", args=["12345678", "CAR1"]),
        )

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "Datos de nacimiento")
        self.assertContains(respuesta, "Estudios secundarios")

        respuesta = self.client.post(
            reverse("editar_graduado", args=["12345678", "CAR1"]),
            {
                "codigo_carrera": "CAR1",
                "nombre": "Ana",
                "apellido": "Perez",
                "dni": "12345678",
                "anio_ingreso_universidad": "2015",
                "fecha_ingreso_carrera": "2016-03-01",
                "fecha_egreso_carrera": "2020-12-15",
                "promedio_sin_aplazo": "",
                "promedio_con_aplazo": "",
                "fecha_nacimiento": "1990-04-06",
                "ciudad_nacimiento": "Rio Gallegos",
                "provincia_nacimiento": "Santa Cruz",
                "nombre_secundario": "CPES 25",
                "titulo_secundario": "Bachiller en Ciencias Naturales",
                "ciudad_secundario": "Rio Gallegos",
                "provincia_secundario": "Santa Cruz",
                "anio_egreso_secundario": "2016",
            },
        )

        self.assertEqual(respuesta.status_code, 302)
        registro.refresh_from_db()
        self.assertEqual(registro.promedio_sin_aplazo, None)

        from academico.models import DatosNacimiento, Secundario

        nacimiento = DatosNacimiento.objects.get(
            dni_graduado=self.graduado
        )
        self.assertEqual(str(nacimiento.fecha_nacimiento), "1990-04-06")

        secundario = Secundario.objects.get(
            dni_graduado=self.graduado
        )
        self.assertEqual(
            secundario.titulo_secundario,
            "Bachiller en Ciencias Naturales",
        )

    def test_cambio_de_carrera_valido(self):
        nueva_carrera = Carrera.objects.create(
            codigo_carrera="CAR2",
            nombre_carrera="Otra carrera",
            id_escuela=self.escuela,
        )

        self.iniciar_sesion(self.titulos)

        respuesta = self.client.post(
            reverse("editar_graduado", args=["12345678", "CAR1"]),
            {
                "codigo_carrera": "CAR2",
                "nombre": "Ana",
                "apellido": "Perez",
                "dni": "12345678",
                "anio_ingreso_universidad": "2015",
                "fecha_ingreso_carrera": "2016-03-01",
                "fecha_egreso_carrera": "2020-12-15",
                "promedio_sin_aplazo": "8.5",
                "promedio_con_aplazo": "8.0",
            },
        )

        self.assertEqual(respuesta.status_code, 302)
        self.assertFalse(
            GraduadoCarrera.objects.filter(
                dni_graduado=self.graduado,
                codigo_carrera="CAR1",
            ).exists()
        )
        registro = GraduadoCarrera.objects.get(
            dni_graduado=self.graduado,
            codigo_carrera=nueva_carrera,
        )
        self.assertEqual(registro.promedio_sin_aplazo, 8.5)

    def test_cambio_de_carrera_duplicada_rechazado(self):
        GraduadoCarrera.objects.create(
            dni_graduado=self.graduado,
            codigo_carrera=Carrera.objects.create(
                codigo_carrera="CAR2",
                nombre_carrera="Otra carrera",
                id_escuela=self.escuela,
            ),
            fecha_ingreso_carrera=date(2017, 3, 1),
            fecha_egreso_carrera=date(2021, 12, 15),
            promedio_con_aplazo=6.0,
            promedio_sin_aplazo=7.0,
        )

        self.iniciar_sesion(self.titulos)

        respuesta = self.client.post(
            reverse("editar_graduado", args=["12345678", "CAR1"]),
            {
                "codigo_carrera": "CAR2",
                "nombre": "Ana",
                "apellido": "Perez",
                "dni": "12345678",
                "anio_ingreso_universidad": "2015",
                "fecha_ingreso_carrera": "2016-03-01",
                "fecha_egreso_carrera": "2020-12-15",
                "promedio_sin_aplazo": "8.5",
                "promedio_con_aplazo": "8.0",
            },
        )

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(
            respuesta,
            "El graduado ya tiene datos cargados para esa carrera.",
        )
        # El registro original queda intacto.
        self.assertTrue(
            GraduadoCarrera.objects.filter(
                dni_graduado=self.graduado,
                codigo_carrera="CAR1",
            ).exists()
        )
        self.assertEqual(
            GraduadoCarrera.objects.filter(
                dni_graduado=self.graduado,
            ).count(),
            2,
        )


class CargaGraduadosTest(BasePrueba):
    """Carga manual de un graduado con datos mínimos."""

    DNI = "41734713"

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()

        cls.escuela = Escuela.objects.create(
            nombre_escuela="Escuela Carga Manual"
        )
        cls.carrera = Carrera.objects.create(
            codigo_carrera="CARGA1",
            nombre_carrera="Carrera Carga Manual",
            id_escuela=cls.escuela,
        )

    def datos(self, **cambios):
        datos = {
            "dni": self.DNI,
            "nombre": "Ana",
            "apellido": "Perez",
            "codigo_carrera": self.carrera.codigo_carrera,
            "anio_ingreso_universidad": "2017",
            "fecha_ingreso_carrera": "2018-03-01",
            "fecha_egreso_carrera": "2024-04-24",
            "promedio_sin_aplazo": "8.5",
        }
        datos.update(cambios)

        return datos

    def enviar(self, datos):
        return self.client.post(reverse("carga_graduados"), datos)

    def crear_duplicado(self, dni=None):
        graduado = Graduado.objects.create(
            dni=dni or self.DNI,
            anio_ingreso_universidad=2016,
            nombre="Viejo",
            apellido="Datos",
        )
        registro = GraduadoCarrera.objects.create(
            dni_graduado=graduado,
            codigo_carrera=self.carrera,
            fecha_ingreso_carrera=date(2018, 3, 1),
            fecha_egreso_carrera=date(2023, 1, 10),
            promedio_sin_aplazo=7.0,
            promedio_con_aplazo=6.0,
        )

        return graduado, registro

    def test_get_sin_sesion_redirige_al_login(self):
        respuesta = self.client.get(reverse("carga_graduados"))

        self.assertEqual(respuesta.status_code, 302)
        self.assertIn(reverse("login"), respuesta.url)

    def test_get_con_sesion_muestra_el_formulario(self):
        self.iniciar_sesion(self.titulos)

        respuesta = self.client.get(reverse("carga_graduados"))

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "Carga de graduados")
        self.assertContains(respuesta, "anio_ingreso_universidad")
        self.assertNotContains(
            respuesta, 'name="fecha_ingreso_universidad"'
        )

    def test_alta_correcta_guarda_anio_y_auditoria(self):
        self.iniciar_sesion(self.titulos)
        self.assertFalse(Graduado.objects.exists())

        respuesta = self.enviar(self.datos())

        self.assertRedirects(respuesta, reverse("carga_graduados"))

        graduado = Graduado.objects.get(pk=self.DNI)
        self.assertEqual(graduado.dni, self.DNI)
        self.assertEqual(graduado.anio_ingreso_universidad, 2017)

        registro = GraduadoCarrera.objects.get(
            dni_graduado=graduado,
            codigo_carrera=self.carrera,
        )
        self.assertEqual(registro.promedio_sin_aplazo, 8.5)
        self.assertEqual(
            registro.origen_promedio_sin_aplazo,
            OrigenPromedio.MANUAL,
        )

        auditoria = Auditoria.objects.get(
            accion="graduado_cargado_manualmente"
        )
        self.assertEqual(auditoria.entidad_id, self.DNI)
        self.assertEqual(auditoria.id_usuario, self.titulos)
        self.assertFalse(auditoria.detalle["sobrescribiendo"])

    def test_datos_invalidos_no_guardan(self):
        self.iniciar_sesion(self.titulos)

        respuesta = self.enviar(
            self.datos(fecha_egreso_carrera="2017-01-01")
        )

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "egreso")
        self.assertFalse(Graduado.objects.exists())
        self.assertFalse(Auditoria.objects.exists())

    def test_duplicado_sin_confirmar_no_guarda(self):
        graduado, registro = self.crear_duplicado()
        self.iniciar_sesion(self.titulos)

        respuesta = self.enviar(self.datos())

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "Confirmar sobrescritura")
        self.assertContains(respuesta, "Datos de la carrera")
        self.assertIn(CLAVE_PENDIENTE, self.client.session)

        graduado.refresh_from_db()
        registro.refresh_from_db()
        self.assertEqual(graduado.anio_ingreso_universidad, 2016)
        self.assertEqual(registro.promedio_sin_aplazo, 7.0)
        self.assertFalse(Auditoria.objects.exists())

    def test_cancelar_no_guarda_cambios(self):
        graduado, registro = self.crear_duplicado()
        self.iniciar_sesion(self.titulos)
        self.enviar(self.datos())

        respuesta = self.client.post(
            reverse("carga_graduados"), {"accion": "cancelar"}
        )

        self.assertRedirects(respuesta, reverse("carga_graduados"))
        self.assertNotIn(CLAVE_PENDIENTE, self.client.session)

        graduado.refresh_from_db()
        registro.refresh_from_db()
        self.assertEqual(graduado.nombre, "Viejo")
        self.assertEqual(registro.promedio_sin_aplazo, 7.0)
        self.assertFalse(Auditoria.objects.exists())

    def test_confirmar_sobrescribe_y_conserva_promedio_con_aplazo(self):
        graduado, registro = self.crear_duplicado()
        self.iniciar_sesion(self.titulos)
        self.enviar(self.datos())
        token = self.client.session[CLAVE_PENDIENTE]["token"]

        respuesta = self.client.post(
            reverse("carga_graduados"),
            {"accion": "confirmar", "token": token},
        )

        self.assertRedirects(respuesta, reverse("carga_graduados"))
        self.assertNotIn(CLAVE_PENDIENTE, self.client.session)

        graduado.refresh_from_db()
        registro.refresh_from_db()
        self.assertEqual(graduado.nombre, "Ana")
        self.assertEqual(graduado.anio_ingreso_universidad, 2017)
        self.assertEqual(registro.promedio_sin_aplazo, 8.5)
        self.assertEqual(registro.promedio_con_aplazo, 6.0)

        auditoria = Auditoria.objects.get(
            accion="graduado_cargado_manualmente"
        )
        self.assertTrue(auditoria.detalle["sobrescribiendo"])

    def test_token_invalido_no_guarda(self):
        graduado, registro = self.crear_duplicado()
        self.iniciar_sesion(self.titulos)
        self.enviar(self.datos())

        respuesta = self.client.post(
            reverse("carga_graduados"),
            {"accion": "confirmar", "token": "token-invalido"},
        )

        self.assertRedirects(respuesta, reverse("carga_graduados"))
        graduado.refresh_from_db()
        self.assertEqual(graduado.nombre, "Viejo")
        self.assertEqual(registro.promedio_sin_aplazo, 7.0)
        self.assertFalse(Auditoria.objects.exists())

    def test_conflicto_nuevo_vuelve_a_pedir_confirmacion(self):
        # El DNI es la PK: no puede haber dos graduados con el mismo
        # DNI. El conflicto nuevo puede aparecer en la carrera.
        Graduado.objects.create(
            dni=self.DNI,
            anio_ingreso_universidad=2016,
            nombre="Viejo",
            apellido="Datos",
        )
        self.iniciar_sesion(self.titulos)
        self.enviar(self.datos())
        token = self.client.session[CLAVE_PENDIENTE]["token"]

        # Mientras se esperaba la confirmación se cargó la carrera.
        GraduadoCarrera.objects.create(
            dni_graduado_id=self.DNI,
            codigo_carrera=self.carrera,
            fecha_ingreso_carrera=date(2018, 3, 1),
            fecha_egreso_carrera=date(2023, 1, 10),
            promedio_sin_aplazo=7.0,
        )

        respuesta = self.client.post(
            reverse("carga_graduados"),
            {"accion": "confirmar", "token": token},
        )

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "Datos personales del DNI")
        self.assertContains(respuesta, "Datos de la carrera")
        graduado = Graduado.objects.get(pk=self.DNI)
        self.assertEqual(graduado.nombre, "Viejo")
        self.assertFalse(Auditoria.objects.exists())


class ValidacionFechasTest(TestCase):
    def test_ingreso_y_egreso_validos(self):
        validar_cronologia_fechas(
            date(2016, 3, 1),
            date(2020, 12, 15),
            date(1995, 3, 1),
        )

    def test_nacimiento_posterior_al_egreso_rechazado(self):
        with self.assertRaises(ValueError):
            validar_cronologia_fechas(
                date(2016, 3, 1),
                date(2020, 12, 15),
                date(2021, 3, 1),
            )

    def test_egreso_anterior_al_ingreso_rechazado(self):
        with self.assertRaises(ValueError):
            validar_cronologia_fechas(
                date(2016, 3, 2),
                date(2016, 3, 1),
            )

    def test_egreso_igual_al_ingreso_rechazado(self):
        with self.assertRaises(ValueError):
            validar_cronologia_fechas(
                date(2016, 3, 1),
                date(2016, 3, 1),
            )


class EstadisticaPorAnioTest(BasePrueba):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()

        escuela = Escuela.objects.create(nombre_escuela="Escuela E")
        carrera = Carrera.objects.create(
            codigo_carrera="C1",
            nombre_carrera="Carrera C",
            id_escuela=escuela,
        )

        for i, anio in enumerate([2020, 2020, 2021], start=1):
            g = Graduado.objects.create(
                dni=f"1000000{i}",
                anio_ingreso_universidad=2015,
                nombre="N",
                apellido="A",
            )
            GraduadoCarrera.objects.create(
                dni_graduado=g,
                codigo_carrera=carrera,
                fecha_ingreso_carrera=date(2016, 1, 1),
                fecha_egreso_carrera=date(anio, 12, 1),
                promedio_con_aplazo=7.0,
                promedio_sin_aplazo=7.5,
            )

    def test_consulta_graduados_por_anio(self):
        resultado = consultar_graduados_por_anio(
            "todos", None, None, None, None
        )

        self.assertEqual(resultado["etiquetas"], ["2020", "2021"])
        self.assertEqual(resultado["valores"], [2, 1])
        self.assertEqual(resultado["total"], 3)


class AbmUsuariosTest(BasePrueba):
    def test_crear_usuario_genera_codigo(self):
        self.iniciar_sesion(self.admin)

        respuesta = self.client.post(
            reverse("abm_usuarios"),
            {
                "accion": "guardar",
                "nombre_usuario": "Nuevo",
                "email": "nuevo@gmail.com",
                "id_rol": self.rol_titulos.id_rol,
            },
            follow=True,
        )

        self.assertEqual(respuesta.status_code, 200)
        self.assertTrue(
            Usuario.objects.filter(email="nuevo@gmail.com").exists()
        )
        self.assertContains(respuesta, "Código de acceso generado")

    def test_no_eliminar_usuario_propio(self):
        self.iniciar_sesion(self.admin)

        self.client.post(
            reverse("abm_usuarios"),
            {"accion": "eliminar", "id_usuario": self.admin.id_usuario},
        )

        self.assertTrue(
            Usuario.objects.filter(id_usuario=self.admin.id_usuario).exists()
        )


class ABMGruposOptativosTest(BasePrueba):
    def setUp(self):
        self.escuela = Escuela.objects.create(
            nombre_escuela="Escuela Grupos"
        )
        self.carrera = Carrera.objects.create(
            codigo_carrera="GR1",
            nombre_carrera="Carrera Grupos",
            id_escuela=self.escuela,
        )
        self.plan = PlanEstudios.objects.create(
            codigo_plan="PGR1",
            codigo_carrera=self.carrera,
        )
        self.otro_plan = PlanEstudios.objects.create(
            codigo_plan="PGR2",
            codigo_carrera=self.carrera,
        )
        self.materia = Materia.objects.create(
            codigo_materia="MATGR1",
            nombre_materia="Materia Grupo 1",
        )

    def test_crear_grupo(self):
        self.iniciar_sesion(self.admin)

        respuesta = self.client.post(
            reverse("gestion_academica"),
            {
                "entidad": "grupo_optativo",
                "accion": "guardar",
                "plan": "PGR1",
                "nombre_grupo": "Optativas X",
            },
        )

        self.assertEqual(respuesta.status_code, 302)
        self.assertTrue(
            GrupoOptativo.objects.filter(
                codigo_plan=self.plan,
                nombre_grupo="Optativas X",
            ).exists()
        )

    def test_nombre_duplicado_en_mismo_plan(self):
        GrupoOptativo.objects.create(
            codigo_plan=self.plan,
            nombre_grupo="Optativas X",
        )

        self.iniciar_sesion(self.admin)

        respuesta = self.client.post(
            reverse("gestion_academica"),
            {
                "entidad": "grupo_optativo",
                "accion": "guardar",
                "plan": "PGR1",
                "nombre_grupo": "Optativas X",
            },
        )

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(
            respuesta,
            "Ya existe un grupo con ese nombre en este plan.",
        )

    def test_ubicar_grupo_en_cronograma(self):
        grupo = GrupoOptativo.objects.create(
            codigo_plan=self.plan,
            nombre_grupo="Optativas X",
        )

        self.iniciar_sesion(self.admin)

        respuesta = self.client.post(
            reverse("gestion_academica"),
            {
                "entidad": "grupo_optativo",
                "accion": "ubicar",
                "plan": "PGR1",
                "id_grupo_optativo": grupo.id_grupo_optativo,
                "anio_materia": "3",
                "cuatrimestre_materia": "1er",
                "orden_materia": "2",
            },
        )

        self.assertEqual(respuesta.status_code, 302)
        ubicacion = PlanEstudiosGrupoOptativo.objects.get(
            codigo_plan=self.plan,
            id_grupo_optativo=grupo,
        )
        self.assertEqual(ubicacion.anio_materia, 3)
        self.assertEqual(ubicacion.orden_materia, 2)

    def test_materia_miembro_hereda_y_guarda_nulos(self):
        grupo = GrupoOptativo.objects.create(
            codigo_plan=self.plan,
            nombre_grupo="Optativas X",
        )
        PlanEstudiosGrupoOptativo.objects.create(
            codigo_plan=self.plan,
            id_grupo_optativo=grupo,
            anio_materia=3,
            cuatrimestre_materia="1er",
            orden_materia=2,
        )

        self.iniciar_sesion(self.admin)

        respuesta = self.client.post(
            reverse("gestion_academica"),
            {
                "entidad": "plan_materia",
                "accion": "guardar",
                "plan": "PGR1",
                "codigo_plan": "PGR1",
                "codigo_materia": "MATGR1",
                "anio_materia": "",
                "cuatrimestre_materia": "",
                "orden_materia": "",
                "id_grupo_optativo": grupo.id_grupo_optativo,
                "materia_requisito": "",
            },
        )

        self.assertEqual(respuesta.status_code, 302)
        fila = PlanEstudiosMateria.objects.get(
            codigo_plan=self.plan,
            codigo_materia=self.materia,
        )
        self.assertEqual(fila.anio_materia, None)
        self.assertEqual(fila.cuatrimestre_materia, None)
        self.assertEqual(fila.orden_materia, None)

    def test_miembro_requiere_grupo_ubicado(self):
        grupo = GrupoOptativo.objects.create(
            codigo_plan=self.plan,
            nombre_grupo="Optativas X",
        )

        self.iniciar_sesion(self.admin)

        respuesta = self.client.post(
            reverse("gestion_academica"),
            {
                "entidad": "plan_materia",
                "accion": "guardar",
                "plan": "PGR1",
                "codigo_plan": "PGR1",
                "codigo_materia": "MATGR1",
                "anio_materia": "",
                "cuatrimestre_materia": "",
                "orden_materia": "",
                "id_grupo_optativo": grupo.id_grupo_optativo,
                "materia_requisito": "",
            },
        )

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "todavía no está ubicado")

    def test_eliminar_grupo_con_miembro_bloqueado(self):
        grupo = GrupoOptativo.objects.create(
            codigo_plan=self.plan,
            nombre_grupo="Optativas X",
        )
        PlanEstudiosGrupoOptativo.objects.create(
            codigo_plan=self.plan,
            id_grupo_optativo=grupo,
            anio_materia=3,
            cuatrimestre_materia="1er",
            orden_materia=2,
        )
        PlanEstudiosMateria.objects.create(
            codigo_plan=self.plan,
            codigo_materia=self.materia,
            materia_requisito=False,
            id_grupo_optativo=grupo,
        )

        self.iniciar_sesion(self.admin)

        self.client.post(
            reverse("gestion_academica"),
            {
                "entidad": "grupo_optativo",
                "accion": "eliminar_grupo",
                "plan": "PGR1",
                "id": grupo.id_grupo_optativo,
            },
        )

        self.assertTrue(
            GrupoOptativo.objects.filter(
                pk=grupo.pk
            ).exists()
        )

    def test_eliminar_grupo_libre_permitido(self):
        grupo = GrupoOptativo.objects.create(
            codigo_plan=self.plan,
            nombre_grupo="Optativas X",
        )

        self.iniciar_sesion(self.admin)

        self.client.post(
            reverse("gestion_academica"),
            {
                "entidad": "grupo_optativo",
                "accion": "eliminar_grupo",
                "plan": "PGR1",
                "id": grupo.id_grupo_optativo,
            },
        )

        self.assertFalse(
            GrupoOptativo.objects.filter(
                pk=grupo.pk
            ).exists()
        )


class ResolucionCarreraTest(BasePrueba):
    def setUp(self):
        self.escuela = Escuela.objects.create(
            nombre_escuela="Escuela Resoluciones"
        )
        self.carrera = Carrera.objects.create(
            codigo_carrera="RC1",
            nombre_carrera="Carrera Resoluciones",
            id_escuela=self.escuela,
        )
        self.res_a = Resolucion.objects.create(
            resolucion="186/CS/06",
            tipo_resolucion="institucional",
        )
        self.res_b = Resolucion.objects.create(
            resolucion="1496/99",
            tipo_resolucion="ministerial_nacional",
        )

    def test_crear_resolucion_desde_abm(self):
        self.iniciar_sesion(self.admin)

        respuesta = self.client.post(
            reverse("gestion_academica"),
            {
                "entidad": "carrera",
                "accion": "crear_resolucion",
                "resolucion": "1186/14",
                "tipo_resolucion": "otro_instrumento",
            },
        )

        self.assertEqual(respuesta.status_code, 302)
        self.assertTrue(
            Resolucion.objects.filter(resolucion="1186/14").exists()
        )

    def test_asociar_y_quitar_resolucion(self):
        self.iniciar_sesion(self.admin)

        self.client.post(
            reverse("gestion_academica"),
            {
                "entidad": "carrera",
                "accion": "guardar",
                "id": "RC1",
                "codigo_carrera": "RC1",
                "nombre_carrera": "Carrera Resoluciones",
                "id_escuela": self.escuela.id_escuela,
                "resoluciones": ["186/CS/06"],
            },
        )

        self.assertEqual(
            set(
                CarreraResolucion.objects.filter(
                    codigo_carrera=self.carrera
                ).values_list("resolucion", flat=True)
            ),
            {"186/CS/06"},
        )

        # Segunda edición: reemplazar la asociación.
        self.client.post(
            reverse("gestion_academica"),
            {
                "entidad": "carrera",
                "accion": "guardar",
                "id": "RC1",
                "codigo_carrera": "RC1",
                "nombre_carrera": "Carrera Resoluciones",
                "id_escuela": self.escuela.id_escuela,
                "resoluciones": ["1496/99"],
            },
        )

        self.assertEqual(
            set(
                CarreraResolucion.objects.filter(
                    codigo_carrera=self.carrera
                ).values_list("resolucion", flat=True)
            ),
            {"1496/99"},
        )

    def test_eliminar_resolucion_bloqueada_en_uso(self):
        CarreraResolucion.objects.create(
            codigo_carrera=self.carrera,
            resolucion=self.res_a,
        )

        self.iniciar_sesion(self.admin)

        self.client.post(
            reverse("gestion_academica"),
            {
                "entidad": "carrera",
                "accion": "eliminar_resolucion",
                "id": "186/CS/06",
            },
        )

        self.assertTrue(
            Resolucion.objects.filter(resolucion="186/CS/06").exists()
        )


def _lincoln_xlsx_fixture_equivalencia():
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    headers = [
        "unidad_academica", "carrera", "dni", "nombre_alumno",
        "desc_abreviada", "nro_documento", "nro_inscripcion",
        "nombre_materia", "fecha_regularidad", "fecha_examen",
        "escala_notas", "acta_promocion", "nombre", "materia",
        "localidad", "pais", "nota_cursada", "descr_cursada",
        "acta_cursada", "res_cursada", "nota_final", "descr_final",
        "acta_final", "res_final", "prom_gral", "observaciones",
        "tipo", "interesado", "resultado", "credito", "hs_semanalese",
        "ano_curs", "periodo_curs", "valor_numerico",
    ]
    ws.append(headers)

    for codigo, nombre in [
        ("9001", "Materia Uno"),
        ("9002", "Materia Dos"),
        ("9003", "Materia Tres"),
    ]:
        ws.append([
            "UARG", "72", "41734713", "PEREZ, JUAN", "DNI",
            "1-00000000/00", "41734713", nombre,
            "", "13/03/2024",
            "", "", "Carrera Test", codigo, "RIO GALLEGOS", "Argentina",
            "", "", "", "", 9, "Nueve",
            "", "087/23-CS-UNPA", "", "",
            "Equivalencia T", "QUIEN CORRESPONDA", "", "", "",
            "", "", "",
        ])

    buffer = BytesIO()
    wb.save(buffer)
    return buffer.getvalue()


def _lincoln_xlsx_fixture():
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    headers = [
        "unidad_academica", "carrera", "dni", "nombre_alumno",
        "desc_abreviada", "nro_documento", "nro_inscripcion",
        "nombre_materia", "fecha_regularidad", "fecha_examen",
        "escala_notas", "acta_promocion", "nombre", "materia",
        "localidad", "pais", "nota_cursada", "descr_cursada",
        "acta_cursada", "res_cursada", "nota_final", "descr_final",
        "acta_final", "res_final", "prom_gral", "observaciones",
        "tipo", "interesado", "resultado", "credito", "hs_semanalese",
        "ano_curs", "periodo_curs", "valor_numerico",
    ]
    ws.append(headers)

    for codigo, nombre, nota, descr, fecha, acta in [
        ("9001", "Materia Uno", 7, "Siete", "01/03/2023", "RG00000001"),
        ("9002", "Materia Dos", 10, "Diez", "16/12/2021", "RG00000002"),
    ]:
        ws.append([
            "UARG", "72", "41734713", "PEREZ, JUAN", "DNI",
            "1-00000000/00", "41734713", nombre, "", fecha,
            "", "", "Carrera Test", codigo, "RIO GALLEGOS", "Argentina",
            "", "", "", "", nota, descr, acta, "", "", "",
            "Final", "QUIEN CORRESPONDA", "", "", "", "2021", "Anual", "",
        ])

    buffer = BytesIO()
    wb.save(buffer)
    return buffer.getvalue()


def _lincoln_xlsx_fixture_discrepancias():
    """Dos filas: nombre distinto para un código y código fuera del plan."""

    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    headers = [
        "unidad_academica", "carrera", "dni", "nombre_alumno",
        "desc_abreviada", "nro_documento", "nro_inscripcion",
        "nombre_materia", "fecha_regularidad", "fecha_examen",
        "escala_notas", "acta_promocion", "nombre", "materia",
        "localidad", "pais", "nota_cursada", "descr_cursada",
        "acta_cursada", "res_cursada", "nota_final", "descr_final",
        "acta_final", "res_final", "prom_gral", "observaciones",
        "tipo", "interesado", "resultado", "credito", "hs_semanalese",
        "ano_curs", "periodo_curs", "valor_numerico",
    ]
    ws.append(headers)

    for codigo, nombre, acta in [
        ("9001", "Materia Uno (nombre viejo)", "RG00000011"),
        ("9999", "Materia Fuera", "RG00000012"),
    ]:
        ws.append([
            "UARG", "72", "41734713", "PEREZ, JUAN", "DNI",
            "1-00000000/00", "41734713", nombre, "", "01/03/2023",
            "", "", "Carrera Test", codigo, "RIO GALLEGOS", "Argentina",
            "", "", "", "", 7, "Siete", acta, "", "", "",
            "Final", "QUIEN CORRESPONDA", "", "", "", "2021", "Anual", "",
        ])

    buffer = BytesIO()
    wb.save(buffer)
    return buffer.getvalue()


class GeneracionAnaliticosTest(BasePrueba):
    def setUp(self):
        self.escuela = Escuela.objects.create(
            nombre_escuela="Escuela Analiticos"
        )
        self.carrera = Carrera.objects.create(
            codigo_carrera="PR1",
            nombre_carrera="Carrera Analiticos",
            id_escuela=self.escuela,
        )
        self.materia1 = Materia.objects.create(
            codigo_materia="9001",
            nombre_materia="Materia Uno",
        )
        self.materia2 = Materia.objects.create(
            codigo_materia="9002",
            nombre_materia="Materia Dos",
        )
        self.materia3 = Materia.objects.create(
            codigo_materia="9003",
            nombre_materia="Materia Tres",
        )
        plan = PlanEstudios.objects.create(
            codigo_plan="PRP1",
            codigo_carrera=self.carrera,
        )
        self.carrera.plan_vigente = plan
        self.carrera.save(update_fields=["plan_vigente"])
        PlanEstudiosMateria.objects.create(
            codigo_plan=plan,
            codigo_materia=self.materia1,
            anio_materia=1,
            cuatrimestre_materia="1er",
            orden_materia=1,
            materia_requisito=False,
        )
        PlanEstudiosMateria.objects.create(
            codigo_plan=plan,
            codigo_materia=self.materia2,
            anio_materia=2,
            cuatrimestre_materia="2do",
            orden_materia=1,
            materia_requisito=False,
        )
        PlanEstudiosMateria.objects.create(
            codigo_plan=plan,
            codigo_materia=self.materia3,
            anio_materia=2,
            cuatrimestre_materia="2do",
            orden_materia=2,
            materia_requisito=False,
        )
        Titulo.objects.create(
            nombre_titulo="Licenciado en Pruebas",
            codigo_carrera=self.carrera,
        )

    def _form_base(self):
        return {
            "nombre": "Juan",
            "apellido": "Perez",
            "dni": "41734713",
            "anio_ingreso_uarg": "2017",
            "carrera": "PR1",
            "anio_ingreso_carrera": "2018",
            "fecha_egreso_carrera": "2024-04-24",
            "promedio_sin_aplazo": "7.67",
            "promedio_con_aplazo": "7.10",
            "fecha_nacimiento": "1999-04-06",
            "ciudad_nacimiento": "Rio Gallegos",
            "provincia_nacimiento": "Santa Cruz",
            "nombre_secundario": "CPES 25",
            "titulo_secundario": "Bachiller en Ciencias Naturales",
            "ciudad_secundario": "Rio Gallegos",
            "provincia_secundario": "Santa Cruz",
            "anio_egreso_secundario": "2016",
            "titulo_otorgado": "Licenciado en Pruebas",
            "resoluciones_institucionales": "141/CS/98, 218/CS/00",
            "resoluciones_ministeriales": "1496/99",
            "otros_instrumentos": "Nota DNGU N.° 1186/14",
        }

    def test_lincoln_equivalencia_usa_res_final(self):
        self.iniciar_sesion(self.admin)

        url = reverse("generacion_analiticos")

        archivo = SimpleUploadedFile(
            "notas.xlsx",
            _lincoln_xlsx_fixture_equivalencia(),
            content_type=(
                "application/vnd.openxmlformats-officedocument."
                "spreadsheetml.sheet"
            ),
        )

        payload = dict(self._form_base())
        payload["accion"] = "continuar"
        payload["archivo_notas"] = archivo

        respuesta = self.client.post(url, payload)

        self.assertEqual(respuesta.status_code, 302)
        self.assertIn("modo=preview", respuesta.url)

        respuesta = self.client.get(respuesta.url)

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "087/23-CS-UNPA")
        self.assertContains(respuesta, "—")

        # Generar y validar con varias equivalencias que comparten
        # la misma resolución: debe guardarse sin errores.
        payload = dict(self._form_base())
        payload["accion"] = "validar"
        payload["fila_indice"] = ["01", "02", "03"]
        payload["fila_anio"] = ["1", "1", "2"]
        payload["fila_espacio"] = [
            "Materia Uno",
            "Materia Dos",
            "Materia Tres",
        ]
        payload["fila_nota"] = ["9", "9", "9"]
        payload["fila_fecha"] = ["2024-03-13", "2024-03-13", "2024-03-13"]
        payload["fila_tipo"] = [
            "Equivalencia T",
            "Equivalencia T",
            "Equivalencia T",
        ]
        payload["fila_respaldo"] = [
            "087/23-CS-UNPA",
            "087/23-CS-UNPA",
            "087/23-CS-UNPA",
        ]
        payload["fila_folio"] = ["UNPA", "UNPA", "UNPA"]
        payload["fila_materia"] = ["9001", "9002", "9003"]

        respuesta = self.client.post(url, payload)

        self.assertEqual(respuesta.status_code, 302)

        from academico.models import Examen, GraduadoExamen

        examen = Examen.objects.filter(
            acta_respaldatoria="087/23-CS-UNPA",
        ).count()

        self.assertEqual(examen, 3)

        self.assertEqual(GraduadoExamen.objects.count(), 3)

    def test_examenes_se_aislan_por_carrera(self):
        from academico.models import (
            Analitico,
            CarreraResolucion,
            Graduado,
            GraduadoCarrera,
            GraduadoExamen,
        )

        alt = Carrera.objects.create(
            codigo_carrera="PRA",
            nombre_carrera="Carrera Alternativa",
            id_escuela=self.escuela,
        )
        materia_alt = Materia.objects.create(
            codigo_materia="9004",
            nombre_materia="Materia Cuatro",
        )
        plan_alt = PlanEstudios.objects.create(
            codigo_plan="PRA1",
            codigo_carrera=alt,
        )
        PlanEstudiosMateria.objects.create(
            codigo_plan=plan_alt,
            codigo_materia=materia_alt,
            anio_materia=1,
            cuatrimestre_materia="1er",
            orden_materia=1,
            materia_requisito=False,
        )

        graduado = Graduado.objects.create(
            dni="42000000",
            anio_ingreso_universidad=2017,
            nombre="Juan",
            apellido="Perez",
        )
        GraduadoCarrera.objects.create(
            dni_graduado=graduado,
            codigo_carrera=self.carrera,
            fecha_ingreso_carrera=date(2018, 3, 1),
            fecha_egreso_carrera=date(2024, 4, 24),
            promedio_sin_aplazo=7.0,
            promedio_con_aplazo=6.5,
        )
        GraduadoCarrera.objects.create(
            dni_graduado=graduado,
            codigo_carrera=alt,
            fecha_ingreso_carrera=date(2018, 3, 1),
            fecha_egreso_carrera=date(2024, 4, 24),
            promedio_sin_aplazo=7.0,
            promedio_con_aplazo=6.5,
        )

        self.iniciar_sesion(self.admin)

        url = reverse("generacion_analiticos")

        # POST continuar con la lincoln (sólo contiene materias
        # de la carrera PR1).
        archivo = SimpleUploadedFile(
            "notas.xlsx",
            _lincoln_xlsx_fixture(),
            content_type=(
                "application/vnd.openxmlformats-officedocument."
                "spreadsheetml.sheet"
            ),
        )

        payload = dict(self._form_base())
        payload["accion"] = "continuar"
        payload["dni"] = "42000000"
        payload["archivo_notas"] = archivo

        self.client.post(url, payload)

        # Validar contra PR1: las notas se guardan para PR1.
        payload = dict(self._form_base())
        payload["accion"] = "validar"
        payload["dni"] = "42000000"
        payload["fila_indice"] = ["01", "02"]
        payload["fila_anio"] = ["1", "2"]
        payload["fila_espacio"] = ["Materia Uno", "Materia Dos"]
        payload["fila_nota"] = ["7", "10"]
        payload["fila_fecha"] = ["2023-03-01", "2021-12-16"]
        payload["fila_tipo"] = ["Final", "Final"]
        payload["fila_respaldo"] = ["RG00000001", "RG00000002"]
        payload["fila_folio"] = ["001", "002"]
        payload["fila_materia"] = ["9001", "9002"]

        self.client.post(url, payload)

        self.assertEqual(
            GraduadoExamen.objects.filter(
                dni_graduado=graduado,
                codigo_carrera=self.carrera,
            ).count(),
            2,
        )

        # PRA (la otra carrera del mismo graduado) no tiene notas.
        self.assertEqual(
            GraduadoExamen.objects.filter(
                dni_graduado=graduado,
                codigo_carrera=alt,
            ).count(),
            0,
        )

    def test_flujo_continuar_validar_descargar(self):
        from academico.models import (
            Analitico,
            Graduado,
            GraduadoCarrera,
            GraduadoExamen,
        )

        self.iniciar_sesion(self.admin)

        url = reverse("generacion_analiticos")

        archivo = SimpleUploadedFile(
            "notas.xlsx",
            _lincoln_xlsx_fixture(),
            content_type=(
                "application/vnd.openxmlformats-officedocument."
                "spreadsheetml.sheet"
            ),
        )

        payload = dict(self._form_base())
        payload["accion"] = "continuar"
        payload["archivo_notas"] = archivo

        respuesta = self.client.post(url, payload)

        self.assertEqual(respuesta.status_code, 302)
        self.assertIn("modo=preview", respuesta.url)

        respuesta = self.client.get(respuesta.url)

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "Validar analítico")

        payload = dict(self._form_base())
        payload["accion"] = "validar"
        payload["fila_indice"] = ["01", "02"]
        payload["fila_anio"] = ["1", "2"]
        payload["fila_espacio"] = ["Materia Uno", "Materia Dos"]
        payload["fila_nota"] = ["7", "10"]
        payload["fila_fecha"] = ["2023-03-01", "2021-12-16"]
        payload["fila_tipo"] = ["Final", "Final"]
        payload["fila_respaldo"] = ["RG00000001", "RG00000002"]
        payload["fila_folio"] = ["001", "002"]
        payload["fila_materia"] = ["9001", "9002"]

        respuesta = self.client.post(url, payload)

        self.assertEqual(respuesta.status_code, 302)

        graduado = Graduado.objects.get(pk="41734713")

        self.assertEqual(
            GraduadoExamen.objects.filter(
                dni_graduado=graduado
            ).count(),
            2,
        )

        self.assertTrue(
            GraduadoCarrera.objects.filter(
                dni_graduado=graduado,
                codigo_carrera=self.carrera,
            ).exists()
        )

        self.assertTrue(
            Analitico.objects.filter(
                dni_graduado=graduado,
                codigo_carrera=self.carrera,
                tipo_documento="titulo",
            ).exists()
        )

        respuesta = self.client.post(
            url,
            {
                "accion": "descargar",
                "dni": "41734713",
                "carrera": "PR1",
            },
        )

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(
            respuesta["Content-Type"],
            (
                "application/vnd.openxmlformats-officedocument."
                "wordprocessingml.document"
            ),
        )
        self.assertGreater(len(respuesta.content), 1000)

    def test_validar_crea_materia_faltante(self):
        from academico.models import GraduadoExamen, Materia

        self.iniciar_sesion(self.admin)

        url = reverse("generacion_analiticos")

        payload = dict(self._form_base())
        payload["accion"] = "validar"
        payload["fila_indice"] = ["01"]
        payload["fila_orden"] = ["1"]
        payload["fila_anio"] = ["1"]
        payload["fila_espacio"] = ["Materia Inexistente"]
        payload["fila_nota"] = ["7"]
        payload["fila_fecha"] = ["2023-03-01"]
        payload["fila_tipo"] = ["Final"]
        payload["fila_respaldo"] = ["RG00000001"]
        payload["fila_materia"] = ["9999"]

        respuesta = self.client.post(url, payload)

        # El plan no bloquea: la materia se crea desde el Lincoln.
        self.assertEqual(respuesta.status_code, 302)

        materia = Materia.objects.get(codigo_materia="9999")
        self.assertEqual(materia.nombre_materia, "Materia Inexistente")

        self.assertTrue(
            GraduadoExamen.objects.filter(
                id_examen__codigo_materia=materia,
            ).exists()
        )

    def test_validar_guarda_orden_y_requisito(self):
        from academico.models import GraduadoExamen

        self.iniciar_sesion(self.admin)

        url = reverse("generacion_analiticos")

        payload = dict(self._form_base())
        payload["accion"] = "validar"
        payload["fila_indice"] = ["1", "2"]
        payload["fila_orden"] = ["2", "1"]
        payload["fila_anio"] = ["1", "2"]
        payload["fila_espacio"] = ["Materia Uno", "Materia Dos"]
        payload["fila_nota"] = ["7", "10"]
        payload["fila_fecha"] = ["2023-03-01", "2021-12-16"]
        payload["fila_tipo"] = ["Final", "Final"]
        payload["fila_respaldo"] = ["RG00000001", "RG00000002"]
        payload["fila_materia"] = ["9001", "9002"]
        payload["fila_requisito_1"] = ["si"]
        payload["fila_requisito_2"] = ["no"]

        respuesta = self.client.post(url, payload)

        self.assertEqual(respuesta.status_code, 302)

        filas = list(
            GraduadoExamen.objects.order_by("orden")
        )

        # Ambas tienen orden 1 en el plan: el orden manual desempata
        # y «Materia Dos» queda primera.
        self.assertEqual(
            [fila.id_examen.codigo_materia.codigo_materia for fila in filas],
            ["9002", "9001"],
        )
        self.assertEqual([fila.orden for fila in filas], [1, 2])

        requisito = GraduadoExamen.objects.get(
            id_examen__codigo_materia=self.materia1
        )
        self.assertTrue(requisito.es_requisito)
        # El año escrito en la grilla se guarda tal cual.
        self.assertEqual(requisito.anio_cursado, 1)

    def test_lincoln_no_genera_mensajes_al_continuar(self):
        from django.contrib.messages import get_messages

        self.iniciar_sesion(self.admin)

        url = reverse("generacion_analiticos")

        archivo = SimpleUploadedFile(
            "notas.xlsx",
            _lincoln_xlsx_fixture(),
            content_type=(
                "application/vnd.openxmlformats-officedocument."
                "spreadsheetml.sheet"
            ),
        )

        payload = dict(self._form_base())
        payload["accion"] = "continuar"
        payload["archivo_notas"] = archivo

        respuesta = self.client.post(url, payload)

        self.assertEqual(respuesta.status_code, 302)
        self.assertEqual(list(get_messages(respuesta.wsgi_request)), [])

    def test_post_sin_accion_no_vacia_el_formulario(self):
        """El botón puede no enviarse si se deshabilita en el submit."""

        from django.contrib.messages import get_messages

        self.iniciar_sesion(self.admin)

        payload = self._form_base()

        respuesta = self.client.post(
            reverse("generacion_analiticos"), payload
        )

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.context["vista"], "carga")
        self.assertEqual(respuesta.context["datos"]["nombre"], "Juan")
        self.assertEqual(
            respuesta.context["datos"]["legajo"],
            "1-41734713/17",
        )

        mensajes = [str(m) for m in get_messages(respuesta.wsgi_request)]
        self.assertTrue(any("acción" in m.lower() for m in mensajes))

    def test_datos_invalidos_conservan_dni_y_no_derivan_legajo(self):
        self.iniciar_sesion(self.admin)

        payload = self._form_base()
        payload["accion"] = "continuar"
        payload["dni"] = "41.734.713"
        # El legajo no se ingresa: una clave extra no altera el resultado.
        payload["legajo"] = "UARG-24827"

        respuesta = self.client.post(
            reverse("generacion_analiticos"), payload
        )

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(
            respuesta.context["datos"]["dni"],
            "41.734.713",
        )
        self.assertIsNone(respuesta.context["datos"]["legajo"])

    def test_formulario_no_deshabilita_el_boton_al_enviar(self):
        self.iniciar_sesion(self.admin)

        respuesta = self.client.get(reverse("generacion_analiticos"))
        contenido = respuesta.content.decode()

        self.assertIn('name="accion"', contenido)
        self.assertNotIn("boton.disabled = true", contenido)
        self.assertIn('name="dni"', contenido)

    def test_borrador_sobrevive_a_la_recarga(self):
        self.iniciar_sesion(self.admin)

        url = reverse("generacion_analiticos")
        payload = self._form_base()
        payload["accion"] = "continuar"
        payload["dni"] = "41.734.713"

        respuesta = self.client.post(url, payload)

        self.assertEqual(respuesta.status_code, 200)
        self.assertTrue(respuesta.context["hay_borrador"])
        self.assertContains(respuesta, "Retomaste un borrador guardado")

        recarga = self.client.get(url)

        self.assertTrue(recarga.context["hay_borrador"])
        self.assertEqual(recarga.context["datos"]["nombre"], "Juan")
        self.assertEqual(recarga.context["datos"]["dni"], "41.734.713")
        self.assertEqual(
            recarga.context["datos"]["resoluciones_institucionales"],
            ["141/CS/98", "218/CS/00"],
        )
        self.assertContains(recarga, "Retomaste un borrador guardado")
        self.assertContains(
            recarga, "El archivo Excel no se guarda en el borrador"
        )

    def test_borrador_es_por_usuario_y_tipo_de_documento(self):
        from academico.views_analiticos import (
            CLAVE_SESION_BORRADOR,
            TipoDocumentoAnalitico,
        )

        self.iniciar_sesion(self.admin)

        url = reverse("generacion_analiticos")
        payload = self._form_base()
        payload["accion"] = "continuar"
        payload["dni"] = "41.734.713"

        self.client.post(url, payload)

        self.iniciar_sesion(self.titulos)
        recarga = self.client.get(url)
        self.assertFalse(recarga.context["hay_borrador"])
        self.assertEqual(recarga.context["datos"]["dni"], "")

        self.iniciar_sesion(self.admin)
        sesion = self.client.session
        borrador = sesion[CLAVE_SESION_BORRADOR]
        borrador["tipo_documento"] = TipoDocumentoAnalitico.EN_TRAMITE.value
        sesion[CLAVE_SESION_BORRADOR] = borrador
        sesion.save()

        recarga = self.client.get(url)
        self.assertFalse(recarga.context["hay_borrador"])

    def test_borrador_no_guarda_el_archivo_excel(self):
        from academico.views_analiticos import CLAVE_SESION_BORRADOR

        self.iniciar_sesion(self.admin)

        payload = self._form_base()
        payload["accion"] = "continuar"
        payload["dni"] = "41.734.713"
        payload["archivo_notas"] = SimpleUploadedFile(
            "notas.xlsx",
            _lincoln_xlsx_fixture(),
            content_type=(
                "application/vnd.openxmlformats-officedocument."
                "spreadsheetml.sheet"
            ),
        )

        self.client.post(reverse("generacion_analiticos"), payload)

        borrador = self.client.session[CLAVE_SESION_BORRADOR]
        self.assertNotIn("archivo_notas", borrador)
        self.assertNotIn("archivo_notas", borrador["datos"])

    def test_descartar_borrador_limpia_la_sesion(self):
        from academico.views_analiticos import CLAVE_SESION_BORRADOR

        self.iniciar_sesion(self.admin)

        url = reverse("generacion_analiticos")
        payload = self._form_base()
        payload["accion"] = "continuar"
        payload["dni"] = "41.734.713"

        self.client.post(url, payload)
        self.assertIn(CLAVE_SESION_BORRADOR, self.client.session)

        respuesta = self.client.post(
            url,
            {"accion": "descartar_borrador"},
            follow=True,
        )

        self.assertContains(respuesta, "Borrador descartado.")
        self.assertNotIn(CLAVE_SESION_BORRADOR, self.client.session)
        self.assertFalse(respuesta.context["hay_borrador"])
        self.assertEqual(respuesta.context["datos"]["nombre"], "")

    def test_borrador_se_limpia_al_llegar_a_la_previsualizacion(self):
        from academico.views_analiticos import CLAVE_SESION_BORRADOR

        self.iniciar_sesion(self.admin)

        url = reverse("generacion_analiticos")
        payload = self._form_base()
        payload["accion"] = "continuar"
        payload["dni"] = "41.734.713"

        self.client.post(url, payload)
        self.assertIn(CLAVE_SESION_BORRADOR, self.client.session)

        payload = self._form_base()
        payload["accion"] = "continuar"
        payload["archivo_notas"] = SimpleUploadedFile(
            "notas.xlsx",
            _lincoln_xlsx_fixture(),
            content_type=(
                "application/vnd.openxmlformats-officedocument."
                "spreadsheetml.sheet"
            ),
        )

        respuesta = self.client.post(url, payload)

        self.assertEqual(respuesta.status_code, 302)
        self.assertIn("modo=preview", respuesta.url)
        self.assertNotIn(CLAVE_SESION_BORRADOR, self.client.session)

    def test_lincoln_rojo_hasta_elegir_archivo(self):
        self.iniciar_sesion(self.admin)

        respuesta = self.client.get(reverse("generacion_analiticos"))
        contenido = respuesta.content.decode()

        self.assertIn(
            'class="analitico-upload" data-estado="sin-archivo"',
            contenido,
        )
        self.assertIn("Rojo hasta que selecciones el Excel", contenido)
        self.assertIn(
            'addEventListener("change", actualizarEstadoArchivo)',
            contenido,
        )
        self.assertIn("tiene-archivo", contenido)

    def test_bordes_visibles_en_formularios_y_paneles(self):
        from django.conf import settings

        css = (
            settings.BASE_DIR
            / "academico"
            / "static"
            / "css"
            / "app.css"
        ).read_text(encoding="utf-8")

        self.assertNotIn("border-color: transparent !important", css)
        self.assertIn("border: 1px solid #d5dee8", css)
        self.assertIn(".abm-pagina .form-control", css)
        self.assertIn(".abm-pagina .abm-panel", css)
        self.assertIn(".abm-tabla .table td", css)
        self.assertIn(".analitico-upload.tiene-archivo", css)

    def _grilla_payload(self, filas=None):
        """Arma los campos repetibles de la grilla de previsualización."""

        if filas is None:
            filas = [
                {
                    "indice": "01",
                    "orden": "1",
                    "anio": "1",
                    "espacio": "Materia Uno",
                    "nota": "7",
                    "fecha": "2023-03-01",
                    "tipo": "Final",
                    "respaldo": "RG00000001",
                    "codigo": "9001",
                },
                {
                    "indice": "02",
                    "orden": "2",
                    "anio": "2",
                    "espacio": "Materia Dos",
                    "nota": "10",
                    "fecha": "2021-12-16",
                    "tipo": "Final",
                    "respaldo": "RG00000002",
                    "codigo": "9002",
                },
            ]

        payload = self._form_base()

        for destino, origen in (
            ("fila_indice", "indice"),
            ("fila_orden", "orden"),
            ("fila_anio", "anio"),
            ("fila_espacio", "espacio"),
            ("fila_nota", "nota"),
            ("fila_fecha", "fecha"),
            ("fila_tipo", "tipo"),
            ("fila_respaldo", "respaldo"),
            ("fila_materia", "codigo"),
            ("fila_codigo_lincoln", "codigo_lincoln"),
            ("fila_nombre_lincoln", "nombre_lincoln"),
        ):
            payload[destino] = [fila.get(origen, "") for fila in filas]

        return payload

    def _grilla_desde_session(self):
        """Convierte la previsualización guardada en un POST válido."""

        from academico.views_analiticos import CLAVE_SESION_PREVIEW

        examenes = self.client.session[CLAVE_SESION_PREVIEW]["examenes"]
        filas = []

        for indice, examen in enumerate(examenes, start=1):
            filas.append({
                "indice": f"{indice:02d}",
                "orden": str(examen.get("orden") or indice),
                "anio": str(examen.get("anio_cursado") or ""),
                "espacio": examen.get("nombre_materia") or "",
                "nota": (
                    "" if examen.get("nota") is None
                    else str(examen["nota"])
                ),
                "fecha": examen.get("fecha_examen") or "",
                "tipo": examen.get("tipo") or "Examen",
                "respaldo": examen.get("acta_respaldatoria") or "",
                "codigo": examen.get("materia_codigo") or "",
                "codigo_lincoln": examen.get("codigo_lincoln") or "",
                "nombre_lincoln": examen.get("nombre_lincoln") or "",
            })

        return self._grilla_payload(filas)

    def test_agregar_materia_manual_al_preview(self):
        from academico.views_analiticos import CLAVE_SESION_PREVIEW

        self.iniciar_sesion(self.admin)

        payload = self._grilla_payload()
        payload["accion"] = "agregar_materia"
        payload["nueva_materia"] = "Materia Nueva"
        payload["nuevo_codigo"] = "M-NUEVA"
        payload["nueva_nota"] = "8"
        payload["nueva_fecha"] = "2024-05-10"

        respuesta = self.client.post(
            reverse("generacion_analiticos"), payload
        )

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "Materia Nueva")
        self.assertFalse(respuesta.context["validado"])

        examenes = self.client.session[CLAVE_SESION_PREVIEW]["examenes"]
        self.assertEqual(len(examenes), 3)
        self.assertEqual(examenes[-1]["nombre_materia"], "Materia Nueva")
        self.assertEqual(examenes[-1]["materia_codigo"], "M-NUEVA")
        self.assertEqual(examenes[-1]["nota"], 8)

        # El alta es sólo del analítico: no se crea en el catálogo
        # ni se agrega al plan hasta que se valide.
        self.assertFalse(
            Materia.objects.filter(codigo_materia="M-NUEVA").exists()
        )

    def test_agregar_materia_manual_se_crea_al_validar(self):
        from academico.models import GraduadoExamen

        self.iniciar_sesion(self.admin)

        payload = self._grilla_payload()
        payload["accion"] = "agregar_materia"
        payload["nueva_materia"] = "Materia Nueva"
        payload["nuevo_codigo"] = "M-NUEVA"
        payload["nueva_nota"] = "8"
        payload["nueva_fecha"] = "2024-05-10"

        respuesta = self.client.post(
            reverse("generacion_analiticos"), payload
        )
        self.assertEqual(respuesta.status_code, 200)

        payload = self._grilla_desde_session()
        payload["accion"] = "validar"

        respuesta = self.client.post(
            reverse("generacion_analiticos"), payload
        )

        self.assertEqual(respuesta.status_code, 302)
        self.assertTrue(
            Materia.objects.filter(codigo_materia="M-NUEVA").exists()
        )
        self.assertEqual(
            GraduadoExamen.objects.filter(
                dni_graduado__dni="41734713"
            ).count(),
            3,
        )

    def test_quitar_materia_del_preview_no_toca_el_catalogo(self):
        from academico.views_analiticos import CLAVE_SESION_PREVIEW

        self.iniciar_sesion(self.admin)

        payload = self._grilla_payload()
        payload["accion"] = "quitar_materia"
        payload["fila_a_quitar"] = "01"

        respuesta = self.client.post(
            reverse("generacion_analiticos"), payload
        )

        self.assertEqual(respuesta.status_code, 200)
        self.assertNotIn(
            'name="fila_espacio" value="Materia Uno"',
            respuesta.content.decode(),
        )
        self.assertContains(respuesta, "Materia Dos")

        examenes = self.client.session[CLAVE_SESION_PREVIEW]["examenes"]
        self.assertEqual(len(examenes), 1)
        self.assertEqual(examenes[0]["nombre_materia"], "Materia Dos")

        self.assertTrue(
            Materia.objects.filter(codigo_materia="9001").exists()
        )

    def test_quitar_materia_preserva_otras_ediciones(self):
        from academico.views_analiticos import CLAVE_SESION_PREVIEW

        self.iniciar_sesion(self.admin)

        payload = self._grilla_payload()
        payload["fila_nota"] = ["7", "9"]
        payload["accion"] = "quitar_materia"
        payload["fila_a_quitar"] = "01"

        self.client.post(reverse("generacion_analiticos"), payload)

        examenes = self.client.session[CLAVE_SESION_PREVIEW]["examenes"]
        self.assertEqual(len(examenes), 1)
        self.assertEqual(examenes[0]["nota"], 9)
        self.assertEqual(examenes[0]["nombre_materia"], "Materia Dos")

    def test_agregar_materia_sin_nombre_muestra_error(self):
        from django.contrib.messages import get_messages

        from academico.views_analiticos import CLAVE_SESION_PREVIEW

        self.iniciar_sesion(self.admin)

        payload = self._grilla_payload()
        payload["accion"] = "agregar_materia"
        payload["nueva_materia"] = "   "

        respuesta = self.client.post(
            reverse("generacion_analiticos"), payload
        )

        self.assertEqual(respuesta.status_code, 200)
        mensajes = [str(m) for m in get_messages(respuesta.wsgi_request)]
        self.assertTrue(
            any("nombre de la materia" in m.lower() for m in mensajes)
        )
        self.assertNotIn(CLAVE_SESION_PREVIEW, self.client.session)

    def test_botones_de_alta_y_baja_en_la_previsualizacion(self):
        from django.contrib.messages import get_messages

        self.iniciar_sesion(self.admin)

        url = reverse("generacion_analiticos")
        archivo = SimpleUploadedFile(
            "notas.xlsx",
            _lincoln_xlsx_fixture(),
            content_type=(
                "application/vnd.openxmlformats-officedocument."
                "spreadsheetml.sheet"
            ),
        )
        payload = dict(self._form_base())
        payload["accion"] = "continuar"
        payload["archivo_notas"] = archivo

        respuesta = self.client.post(url, payload, follow=True)

        self.assertEqual(respuesta.status_code, 200)
        contenido = respuesta.content.decode()
        self.assertIn('value="agregar_materia"', contenido)
        self.assertIn('value="quitar_materia"', contenido)
        self.assertIn('name="fila_a_quitar"', contenido)
        self.assertIn("formnovalidate", contenido)
        self.assertIn("data-fila=", contenido)
        self.assertIn("restaurarBoton", contenido)
        self.assertIn("Agregar materia manualmente", contenido)

        # Los mensajes del redirect (si los hay) no se mezclan con la
        # comprobación de los controles.
        self.assertIsInstance(list(get_messages(respuesta.wsgi_request)), list)

    def test_descarga_con_cambios_sin_validar_no_genera_archivo(self):
        from django.contrib.messages import get_messages

        self.iniciar_sesion(self.admin)

        url = reverse("generacion_analiticos")
        archivo = SimpleUploadedFile(
            "notas.xlsx",
            _lincoln_xlsx_fixture(),
            content_type=(
                "application/vnd.openxmlformats-officedocument."
                "spreadsheetml.sheet"
            ),
        )
        payload = dict(self._form_base())
        payload["accion"] = "continuar"
        payload["archivo_notas"] = archivo
        respuesta = self.client.post(url, payload)
        self.assertEqual(respuesta.status_code, 302)

        payload = self._grilla_payload()
        payload["accion"] = "validar"
        respuesta = self.client.post(url, payload)
        self.assertEqual(respuesta.status_code, 302)

        # Una edición posterior deja cambios pendientes en sesión.
        payload = self._grilla_payload()
        payload["accion"] = "agregar_materia"
        payload["nueva_materia"] = "Materia Pendiente"
        respuesta = self.client.post(url, payload)
        self.assertEqual(respuesta.status_code, 200)

        respuesta = self.client.post(
            url,
            {
                "accion": "descargar",
                "dni": "41734713",
                "carrera": "PR1",
            },
            follow=True,
        )

        self.assertEqual(respuesta.status_code, 200)
        self.assertNotEqual(
            respuesta["Content-Type"],
            (
                "application/vnd.openxmlformats-officedocument."
                "wordprocessingml.document"
            ),
        )
        mensajes = [str(m) for m in get_messages(respuesta.wsgi_request)]
        self.assertTrue(
            any("sin validar" in m.lower() for m in mensajes)
        )

    def test_descarga_con_datos_incompletos_redirige_con_error(self):
        from django.contrib.messages import get_messages

        from academico.models import Analitico, DatosNacimiento

        self.iniciar_sesion(self.admin)

        url = reverse("generacion_analiticos")
        archivo = SimpleUploadedFile(
            "notas.xlsx",
            _lincoln_xlsx_fixture(),
            content_type=(
                "application/vnd.openxmlformats-officedocument."
                "spreadsheetml.sheet"
            ),
        )
        payload = dict(self._form_base())
        payload["accion"] = "continuar"
        payload["archivo_notas"] = archivo
        respuesta = self.client.post(url, payload)
        self.assertEqual(respuesta.status_code, 302)

        payload = self._grilla_payload()
        payload["accion"] = "validar"
        respuesta = self.client.post(url, payload)
        self.assertEqual(respuesta.status_code, 302)
        self.assertTrue(Analitico.objects.exists())

        DatosNacimiento.objects.all().delete()

        respuesta = self.client.post(
            url,
            {
                "accion": "descargar",
                "dni": "41734713",
                "carrera": "PR1",
            },
            follow=True,
        )

        self.assertEqual(respuesta.status_code, 200)
        mensajes = [str(m) for m in get_messages(respuesta.wsgi_request)]
        self.assertTrue(
            any("no se puede descargar" in m.lower() for m in mensajes)
        )

    def test_ya_existe_el_graduado_ofrece_opciones(self):
        graduado = Graduado.objects.create(
            dni="41734713",
            anio_ingreso_universidad=2017,
            nombre="Juan",
            apellido="Perez",
        )
        GraduadoCarrera.objects.create(
            dni_graduado=graduado,
            codigo_carrera=self.carrera,
            fecha_ingreso_carrera=date(2018, 3, 1),
            fecha_egreso_carrera=date(2024, 4, 24),
            promedio_sin_aplazo=7.6,
            promedio_con_aplazo=7.1,
        )

        self.iniciar_sesion(self.admin)

        respuesta = self.client.get(
            reverse("generacion_analiticos")
            + "?modo=elegir&dni=41734713&carrera=PR1"
        )

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "Ya existe el graduado")
        self.assertContains(respuesta, "Generar analítico")
        self.assertContains(respuesta, "Modificar la información")

    def test_verificar_filas_contra_el_plan(self):
        from academico.servicios.moduloAnalitico.plan_estudios import (
            verificar_filas,
        )

        filas = [
            {"codigo_materia": "9001", "nombre_materia": "Materia Uno"},
            {
                "codigo_materia": "9002",
                "nombre_materia": "MATERIA DOS",
            },
            {"codigo_materia": "9001", "nombre_materia": "Otro nombre"},
            {"codigo_materia": "9999", "nombre_materia": "Materia Tres"},
            {"codigo_materia": "", "nombre_materia": "Sin código"},
        ]

        resultado = verificar_filas(self.carrera, filas)

        self.assertEqual(resultado[0]["estado"], "ok")
        self.assertEqual(resultado[0]["anio_plan"], 1)
        self.assertEqual(resultado[0]["orden_plan"], 1)

        # El nombre se compara sin caso ni acentos.
        self.assertEqual(resultado[1]["estado"], "ok")
        self.assertEqual(resultado[1]["anio_plan"], 2)

        self.assertEqual(resultado[2]["estado"], "nombre_distinto")
        self.assertEqual(resultado[2]["anio_plan"], 1)

        # El código no está en el plan, pero el nombre sí: se asiste
        # con la materia del plan en vez de dejar el año vacío.
        self.assertEqual(resultado[3]["estado"], "codigo_distinto")
        self.assertEqual(resultado[3]["codigo_esperado"], "9003")
        self.assertEqual(resultado[3]["anio_plan"], 2)
        self.assertEqual(resultado[3]["orden_plan"], 2)
        self.assertEqual(resultado[3]["tipo_sugerencia"], "exacto")

        self.assertEqual(resultado[4]["estado"], "sin_codigo")

    def test_verificar_pad_codigo_y_sin_plan(self):
        from academico.servicios.moduloAnalitico.plan_estudios import (
            pad_codigo,
            verificar_filas,
        )

        materia = Materia.objects.create(
            codigo_materia="0904",
            nombre_materia="Materia Cuatro",
        )
        PlanEstudiosMateria.objects.create(
            codigo_plan=self.carrera.plan_vigente,
            codigo_materia=materia,
            anio_materia=3,
            cuatrimestre_materia="1er",
            orden_materia=4,
            materia_requisito=False,
        )

        filas = [
            {"codigo_materia": "904", "nombre_materia": "Materia Cuatro"},
        ]
        resultado = verificar_filas(self.carrera, filas)

        self.assertEqual(pad_codigo("904"), "0904")
        self.assertEqual(resultado[0]["estado"], "ok")
        self.assertEqual(resultado[0]["anio_plan"], 3)

        incompleta = Materia.objects.create(
            codigo_materia="0905",
            nombre_materia="Materia Cinco",
        )
        PlanEstudiosMateria.objects.create(
            codigo_plan=self.carrera.plan_vigente,
            codigo_materia=incompleta,
            anio_materia=None,
            cuatrimestre_materia="",
            orden_materia=None,
            materia_requisito=False,
        )
        fila_incompleta = verificar_filas(self.carrera, [{
            "codigo_materia": "905",
            "nombre_materia": "Materia Cinco",
        }])
        self.assertEqual(fila_incompleta[0]["estado"], "plan_incompleto")
        self.assertIsNone(fila_incompleta[0]["anio_plan"])

        self.carrera.plan_vigente = None
        self.carrera.save(update_fields=["plan_vigente"])

        # Sin plan vigente pero con un único plan cargado, se usa ese
        # como sugerencia y se avisa.
        con_plan_no_vigente = verificar_filas(
            Carrera.objects.get(pk=self.carrera.pk), filas
        )
        self.assertEqual(con_plan_no_vigente[0]["estado"], "ok")
        self.assertEqual(con_plan_no_vigente[0]["anio_plan"], 3)
        self.assertTrue(con_plan_no_vigente[0]["plan_no_vigente"])

        PlanEstudios.objects.all().delete()

        sin_plan = verificar_filas(
            Carrera.objects.get(pk=self.carrera.pk), filas
        )
        self.assertEqual(sin_plan[0]["estado"], "sin_plan")
        self.assertIsNone(sin_plan[0]["anio_plan"])

    def test_discrepancias_no_bloquean_y_orden_manual_se_respeta(self):
        from academico.models import GraduadoExamen

        self.iniciar_sesion(self.admin)
        url = reverse("generacion_analiticos")

        archivo = SimpleUploadedFile(
            "notas.xlsx",
            _lincoln_xlsx_fixture_discrepancias(),
            content_type=(
                "application/vnd.openxmlformats-officedocument."
                "spreadsheetml.sheet"
            ),
        )

        payload = dict(self._form_base())
        payload["accion"] = "continuar"
        payload["archivo_notas"] = archivo

        respuesta = self.client.post(url, payload)
        self.assertEqual(respuesta.status_code, 302)

        respuesta = self.client.get(respuesta.url)
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "Discrepancias con el plan de estudios")
        self.assertContains(respuesta, "Nombre distinto")
        self.assertContains(respuesta, "Código fuera del plan")
        self.assertContains(respuesta, "no impiden validar ni descargar")

        payload = dict(self._form_base())
        payload["accion"] = "validar"
        payload["fila_indice"] = ["01", "02"]
        # Orden manual invertido: debe prevalecer aunque haya
        # discrepancias con el plan.
        payload["fila_orden"] = ["2", "1"]
        payload["fila_anio"] = ["1", "2"]
        payload["fila_espacio"] = [
            "Materia Uno (nombre viejo)",
            "Materia Fuera",
        ]
        payload["fila_nota"] = ["7", "8"]
        payload["fila_fecha"] = ["2023-03-01", "2023-03-01"]
        payload["fila_tipo"] = ["Final", "Final"]
        payload["fila_respaldo"] = ["RG00000011", "RG00000012"]
        payload["fila_materia"] = ["9001", "9999"]
        payload["fila_codigo_lincoln"] = ["9001", "9999"]
        payload["fila_nombre_lincoln"] = [
            "Materia Uno (nombre viejo)",
            "Materia Fuera",
        ]

        respuesta = self.client.post(url, payload)
        self.assertEqual(respuesta.status_code, 302)

        filas = list(GraduadoExamen.objects.order_by("orden"))
        self.assertEqual(
            [
                fila.id_examen.codigo_materia.codigo_materia
                for fila in filas
            ],
            ["9999", "9001"],
        )
        self.assertEqual(filas[0].anio_cursado, 2)
        self.assertEqual(filas[1].anio_cursado, 1)

        # La descarga queda habilitada aunque haya discrepancias.
        respuesta = self.client.post(
            url,
            {
                "accion": "descargar",
                "dni": "41734713",
                "carrera": "PR1",
            },
        )
        self.assertEqual(respuesta.status_code, 200)

    def test_orden_y_anio_editados_se_respetan_en_el_documento(self):
        from docx import Document

        from academico.models import GraduadoExamen

        # El plan sugiere otro orden y otros años: lo escrito en la
        # grilla debe ganar tanto en la base como en el .docx.
        PlanEstudiosMateria.objects.filter(
            codigo_materia=self.materia1
        ).update(anio_materia=3, orden_materia=2)
        PlanEstudiosMateria.objects.filter(
            codigo_materia=self.materia2
        ).update(anio_materia=1, orden_materia=1)

        self.iniciar_sesion(self.admin)
        url = reverse("generacion_analiticos")

        payload = dict(self._form_base())
        payload["accion"] = "validar"
        payload["fila_indice"] = ["01", "02"]
        payload["fila_orden"] = ["1", "2"]
        payload["fila_anio"] = ["4", "2"]
        payload["fila_espacio"] = ["Materia Uno", "Materia Dos"]
        payload["fila_nota"] = ["7", "10"]
        payload["fila_fecha"] = ["2023-03-01", "2021-12-16"]
        payload["fila_tipo"] = ["Final", "Final"]
        payload["fila_respaldo"] = ["RG00000001", "RG00000002"]
        payload["fila_materia"] = ["9001", "9002"]

        respuesta = self.client.post(url, payload)
        self.assertEqual(respuesta.status_code, 302)

        filas = list(GraduadoExamen.objects.order_by("orden"))
        self.assertEqual(
            [
                fila.id_examen.codigo_materia.codigo_materia
                for fila in filas
            ],
            ["9001", "9002"],
        )
        self.assertEqual([fila.orden for fila in filas], [1, 2])
        self.assertEqual([fila.anio_cursado for fila in filas], [4, 2])

        respuesta = self.client.post(
            url,
            {
                "accion": "descargar",
                "dni": "41734713",
                "carrera": "PR1",
            },
        )
        self.assertEqual(respuesta.status_code, 200)

        documento = Document(BytesIO(respuesta.content))
        filas_doc = [
            [celda.text.strip() for celda in fila.cells]
            for fila in documento.tables[0].rows[1:]
        ]
        self.assertEqual([fila[0] for fila in filas_doc], ["01", "02"])
        self.assertEqual([fila[1] for fila in filas_doc], ["4°", "2°"])
        self.assertEqual(
            [fila[2] for fila in filas_doc],
            ["Materia Uno", "Materia Dos"],
        )

    def test_carrera_sin_plan_conserva_orden_y_anio_editado(self):
        from academico.models import GraduadoExamen

        # Sin plan vigente ni planes cargados: no hay sugerencias, pero
        # el usuario puede completar orden y año a mano.
        self.carrera.plan_vigente = None
        self.carrera.save(update_fields=["plan_vigente"])
        PlanEstudios.objects.all().delete()

        self.iniciar_sesion(self.admin)
        url = reverse("generacion_analiticos")

        archivo = SimpleUploadedFile(
            "notas.xlsx",
            _lincoln_xlsx_fixture(),
            content_type=(
                "application/vnd.openxmlformats-officedocument."
                "spreadsheetml.sheet"
            ),
        )

        payload = dict(self._form_base())
        payload["accion"] = "continuar"
        payload["archivo_notas"] = archivo

        respuesta = self.client.post(url, payload)
        self.assertEqual(respuesta.status_code, 302)

        respuesta = self.client.get(respuesta.url)
        self.assertContains(respuesta, "Sin plan vigente")
        self.assertContains(respuesta, "no impiden validar ni descargar")

        payload = dict(self._form_base())
        payload["accion"] = "validar"
        payload["fila_indice"] = ["01", "02"]
        payload["fila_orden"] = ["2", "1"]
        payload["fila_anio"] = ["1", "2"]
        payload["fila_espacio"] = ["Materia Uno", "Materia Dos"]
        payload["fila_nota"] = ["7", "10"]
        payload["fila_fecha"] = ["2023-03-01", "2021-12-16"]
        payload["fila_tipo"] = ["Final", "Final"]
        payload["fila_respaldo"] = ["RG00000001", "RG00000002"]
        payload["fila_materia"] = ["9001", "9002"]

        respuesta = self.client.post(url, payload)
        self.assertEqual(respuesta.status_code, 302)

        filas = list(GraduadoExamen.objects.order_by("orden"))
        self.assertEqual(
            [
                fila.id_examen.codigo_materia.codigo_materia
                for fila in filas
            ],
            ["9002", "9001"],
        )
        self.assertEqual([fila.anio_cursado for fila in filas], [2, 1])

    def test_matcheo_asistido_por_nombre_con_codigo_distinto(self):
        from academico.servicios.moduloAnalitico.plan_estudios import (
            aplicar_plan_a_filas,
            verificar_filas,
        )

        # Caso «Organización de las Computadores»: el código del
        # certificado no existe en el plan, pero el nombre sí.
        filas = [{
            "codigo_lincoln": "9999",
            "nombre_lincoln": "Materia Tres",
            "materia_codigo": "9999",
        }]
        verificacion = verificar_filas(self.carrera, filas)[0]

        self.assertEqual(verificacion["estado"], "codigo_distinto")
        self.assertEqual(verificacion["codigo_esperado"], "9003")
        self.assertEqual(verificacion["anio_plan"], 2)
        self.assertEqual(verificacion["orden_plan"], 2)
        self.assertEqual(verificacion["tipo_sugerencia"], "exacto")

        aplicadas = aplicar_plan_a_filas(
            self.carrera,
            [{
                "codigo_lincoln": "9999",
                "nombre_lincoln": "Materia Tres",
                "espacio": "Materia Tres",
                "materia_codigo": "9999",
                "anio": "",
                "orden_num": None,
            }],
            respetar_edicion=True,
        )
        self.assertEqual(aplicadas[0]["anio"], 2)
        self.assertEqual(aplicadas[0]["anio_txt"], "2°")
        self.assertEqual(aplicadas[0]["orden_num"], 1)

        # Un nombre con una pequeña diferencia también se asocia.
        parecidas = verificar_filas(self.carrera, [{
            "codigo_lincoln": "9999",
            "nombre_lincoln": "Materia Uno!",
        }])
        self.assertEqual(parecidas[0]["estado"], "codigo_distinto")
        self.assertEqual(parecidas[0]["tipo_sugerencia"], "similar")
        self.assertEqual(parecidas[0]["anio_plan"], 1)

    def test_plan_unico_no_vigente_se_sugiere_y_anio_es_editable(self):
        import re

        self.carrera.plan_vigente = None
        self.carrera.save(update_fields=["plan_vigente"])

        self.iniciar_sesion(self.admin)
        url = reverse("generacion_analiticos")

        archivo = SimpleUploadedFile(
            "notas.xlsx",
            _lincoln_xlsx_fixture(),
            content_type=(
                "application/vnd.openxmlformats-officedocument."
                "spreadsheetml.sheet"
            ),
        )

        payload = dict(self._form_base())
        payload["accion"] = "continuar"
        payload["archivo_notas"] = archivo

        respuesta = self.client.post(url, payload)
        self.assertEqual(respuesta.status_code, 302)

        respuesta = self.client.get(respuesta.url)
        self.assertContains(respuesta, "Plan no vigente")
        self.assertContains(respuesta, "PRP1")

        contenido = respuesta.content.decode()
        campo_anio = re.search(
            r'<input[^>]*name="fila_anio"[^>]*>', contenido
        )
        self.assertIsNotNone(campo_anio)
        self.assertIn('value="1"', campo_anio.group(0))
        self.assertNotIn("readonly", campo_anio.group(0))


class TituloEnTramiteTest(BasePrueba):
    def setUp(self):
        self.escuela = Escuela.objects.create(
            nombre_escuela="Escuela Tramite"
        )
        self.carrera = Carrera.objects.create(
            codigo_carrera="TR1",
            nombre_carrera="Carrera Tramite",
            id_escuela=self.escuela,
        )
        self.graduado = Graduado.objects.create(
            dni="41734713",
            nombre="Juan",
            apellido="Perez",
            anio_ingreso_universidad=2017,
        )
        GraduadoCarrera.objects.create(
            dni_graduado=self.graduado,
            codigo_carrera=self.carrera,
            fecha_ingreso_carrera=date(2018, 3, 1),
            fecha_egreso_carrera=date(2024, 4, 24),
            promedio_sin_aplazo=None,
            promedio_con_aplazo=None,
        )

    def _form_base(self):
        return {
            "apellido": "Perez",
            "nombre": "Juan",
            "dni": "41734713",
            "carrera": "TR1",
            "anio_ingreso_uarg": "2017",
            "anio_ingreso_carrera": "2018",
            "fecha_egreso_carrera": "2024-04-24",
            "promedio_sin_aplazo": "7.67",
            "promedio_con_aplazo": "7.10",
            "fecha_nacimiento": "1999-04-06",
            "ciudad_nacimiento": "Rio Gallegos",
            "provincia_nacimiento": "Santa Cruz",
            "nombre_secundario": "CPES 25",
            "titulo_secundario": "Bachiller en Ciencias Naturales",
            "ciudad_secundario": "Rio Gallegos",
            "provincia_secundario": "Santa Cruz",
            "anio_egreso_secundario": "2016",
            "titulo_otorgado": "Licenciado en Tramite",
            "resoluciones_institucionales": "141/CS/98",
            "resoluciones_ministeriales": "1496/99",
            "otros_instrumentos": "Nota DNGU N.° 1186/14",
        }

    def test_buscar_inexistente(self):
        self.iniciar_sesion(self.titulos)

        respuesta = self.client.post(
            reverse("titulo_en_tramite"),
            {"accion": "buscar", "dni": "NOEXISTE", "carrera": "TR1"},
        )

        self.assertEqual(respuesta.status_code, 302)
        self.assertEqual(respuesta.url, reverse("titulo_en_tramite"))

    def test_buscar_existente_llega_a_preview(self):
        self.iniciar_sesion(self.titulos)

        respuesta = self.client.post(
            reverse("titulo_en_tramite"),
            {"accion": "buscar", "dni": "41734713", "carrera": "TR1"},
        )

        self.assertEqual(respuesta.status_code, 302)
        self.assertIn("modo=preview", respuesta.url)

        respuesta = self.client.get(respuesta.url)

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "Generar Título en trámite")

    def test_generar_y_descargar_en_tramite(self):
        self.iniciar_sesion(self.titulos)

        # Buscar → preview sin validar
        respuesta = self.client.post(
            reverse("titulo_en_tramite"),
            {"accion": "buscar", "dni": "41734713", "carrera": "TR1"},
        )

        self.assertEqual(respuesta.status_code, 302)

        # Generar → valida y habilita descarga
        generar = self.client.post(
            reverse("titulo_en_tramite"),
            {
                "accion": "generar",
                "dni": "41734713",
                "carrera": "TR1",
            },
        )

        self.assertEqual(generar.status_code, 302)

        # Descargar
        descargar = self.client.post(
            reverse("titulo_en_tramite"),
            {
                "accion": "descargar",
                "dni": "41734713",
                "carrera": "TR1",
            },
        )

        self.assertEqual(descargar.status_code, 200)
        self.assertEqual(
            descargar["Content-Type"],
            (
                "application/vnd.openxmlformats-officedocument."
                "wordprocessingml.document"
            ),
        )

        from academico.models import Analitico

        self.assertTrue(
            Analitico.objects.filter(
                dni_graduado_id="41734713",
                codigo_carrera=self.carrera,
                tipo_documento="en_tramite",
            ).exists()
        )

    def test_quitar_plan_vacio_permite_validar(self):
        # Sin exámenes en la base igual se puede validar.
        self.iniciar_sesion(self.titulos)

        self.client.post(
            reverse("titulo_en_tramite"),
            {"accion": "buscar", "dni": "41734713", "carrera": "TR1"},
        )

        respuesta = self.client.post(
            reverse("titulo_en_tramite"),
            {
                "accion": "generar",
                "dni": "41734713",
                "carrera": "TR1",
            },
        )

        self.assertEqual(respuesta.status_code, 302)

        from academico.models import Analitico

        self.assertTrue(
            Analitico.objects.filter(
                dni_graduado=self.graduado,
                codigo_carrera=self.carrera,
                tipo_documento="en_tramite",
            ).exists()
        )


class PromediosServicioTest(BasePrueba):
    """Reglas de cálculo de promedios con y sin aplazo."""

    def setUp(self):
        self.escuela = Escuela.objects.create(
            nombre_escuela="Escuela Promedios"
        )
        self.carrera = Carrera.objects.create(
            codigo_carrera="PRO1",
            nombre_carrera="Carrera Promedios",
            id_escuela=self.escuela,
        )
        plan = PlanEstudios.objects.create(
            codigo_plan="PLANPRO1",
            codigo_carrera=self.carrera,
        )

        self.materias = {}

        for codigo, nombre, requisito in (
            ("P001", "Materia Uno", False),
            ("P002", "Materia Dos", False),
            ("P003", "Materia Requisito", True),
            ("P004", "Materia Equivalencia", False),
        ):
            materia = Materia.objects.create(
                codigo_materia=codigo,
                nombre_materia=nombre,
            )
            PlanEstudiosMateria.objects.create(
                codigo_plan=plan,
                codigo_materia=materia,
                anio_materia=1,
                cuatrimestre_materia="1er",
                orden_materia=1,
                materia_requisito=requisito,
            )
            self.materias[codigo] = materia

    def _examen(self, codigo, nota, fecha=None, tipo="Examen",
                es_requisito=False):
        return {
            "nota": nota,
            "materia_codigo": codigo,
            "resultado": (
                "Aprobado" if nota is not None and nota >= 6
                else "Reprobado"
            ),
            "tipo": tipo,
            "fecha_examen": fecha,
            "acta_respaldatoria": "",
            "es_requisito": es_requisito,
        }

    def test_requisito_se_excluye_de_ambos_promedios(self):
        resultado = calcular_promedios(
            None,
            self.carrera,
            examenes=[
                self._examen("P001", 4, date(2023, 1, 1)),
                self._examen("P001", 8, date(2024, 1, 1)),
                self._examen("P002", 10, date(2024, 2, 1)),
                self._examen(
                    "P003", 7, date(2024, 3, 1), es_requisito=True
                ),
            ],
        )

        # (4 + 8 + 10) / 3 = 7.33: el requisito P003 no participa.
        self.assertEqual(resultado.promedio_con_aplazo, 7.33)
        # Sin aplazo: 8 (la más reciente de P001) y 10.
        self.assertEqual(resultado.promedio_sin_aplazo, 9.0)

    def test_equivalencia_con_nota_no_se_promedia(self):
        resultado = calcular_promedios(
            None,
            self.carrera,
            examenes=[
                self._examen("P001", 8, date(2024, 1, 1)),
                self._examen(
                    "P004", 10, date(2024, 1, 1), "Equivalencia"
                ),
            ],
        )

        self.assertEqual(resultado.promedio_con_aplazo, 8.0)
        self.assertEqual(resultado.promedio_sin_aplazo, 8.0)
        self.assertEqual(resultado.equivalencias_excluidas, ["P004"])

    def test_duplicado_usa_la_mas_reciente_y_avisa(self):
        resultado = calcular_promedios(
            None,
            self.carrera,
            examenes=[
                self._examen("P001", 9, date(2022, 1, 1)),
                self._examen("P001", 7, date(2024, 1, 1)),
            ],
        )

        self.assertEqual(resultado.promedio_sin_aplazo, 7.0)
        self.assertEqual(len(resultado.duplicados), 1)
        self.assertEqual(resultado.duplicados[0]["nota_elegida"], 7)
        self.assertTrue(
            any("aprobaciones" in aviso for aviso in resultado.advertencias)
        )

    def test_duplicado_misma_fecha_desempata_por_nota_mayor(self):
        resultado = calcular_promedios(
            None,
            self.carrera,
            examenes=[
                self._examen("P001", 7, date(2024, 1, 1)),
                self._examen("P001", 9, date(2024, 1, 1)),
            ],
        )

        self.assertEqual(resultado.promedio_sin_aplazo, 9.0)

    def test_duplicado_con_fechas_texto_usa_la_mas_reciente(self):
        resultado = calcular_promedios(
            None,
            self.carrera,
            examenes=[
                self._examen("P001", 9, "2023-01-01"),
                self._examen("P001", 7, "2024-01-01"),
            ],
        )

        # La fecha más reciente gana aunque la nota sea menor.
        self.assertEqual(resultado.promedio_sin_aplazo, 7.0)

    def test_equivalencia_sin_nota_se_excluye_con_advertencia(self):
        resultado = calcular_promedios(
            None,
            self.carrera,
            examenes=[
                self._examen("P001", 8, date(2024, 1, 1)),
                self._examen("P004", None, date(2024, 1, 1), "Equivalencia"),
            ],
        )

        self.assertEqual(resultado.promedio_con_aplazo, 8.0)
        self.assertEqual(resultado.promedio_sin_aplazo, 8.0)
        self.assertEqual(resultado.equivalencias_sin_nota, ["P004"])
        self.assertTrue(
            any("no tiene nota" in aviso for aviso in resultado.advertencias)
        )

    def test_sin_examenes_no_divide_por_cero(self):
        resultado = calcular_promedios(None, self.carrera, examenes=[])

        self.assertIsNone(resultado.promedio_con_aplazo)
        self.assertIsNone(resultado.promedio_sin_aplazo)

    def test_solo_requisitos_deja_ambos_promedios_nulos(self):
        resultado = calcular_promedios(
            None,
            self.carrera,
            examenes=[
                self._examen(
                    "P003", 7, date(2024, 1, 1), es_requisito=True
                )
            ],
        )

        self.assertIsNone(resultado.promedio_con_aplazo)
        self.assertIsNone(resultado.promedio_sin_aplazo)


class TipoExamenLegibleTest(TestCase):
    def test_equivalencia_t_se_muestra_como_equivalencia(self):
        self.assertEqual(tipo_examen_legible("Equivalencia T"), "Equivalencia")
        self.assertEqual(tipo_examen_legible("Examen"), "Examen")
        self.assertEqual(tipo_examen_legible(None), "")


class FiltrosListadoTest(BasePrueba):
    def setUp(self):
        self.escuela_a = Escuela.objects.create(nombre_escuela="Escuela A")
        self.escuela_b = Escuela.objects.create(nombre_escuela="Escuela B")
        self.carrera_a = Carrera.objects.create(
            codigo_carrera="FA1",
            nombre_carrera="Carrera A",
            id_escuela=self.escuela_a,
        )
        self.carrera_b = Carrera.objects.create(
            codigo_carrera="FB1",
            nombre_carrera="Carrera B",
            id_escuela=self.escuela_b,
        )

        for dni, carrera, nombre in (
            ("42000001", self.carrera_a, "Ana"),
            ("42000002", self.carrera_b, "Beto"),
        ):
            graduado = Graduado.objects.create(
                dni=dni,
                anio_ingreso_universidad=2015,
                nombre=nombre,
                apellido="Apellido",
            )
            GraduadoCarrera.objects.create(
                dni_graduado=graduado,
                codigo_carrera=carrera,
                fecha_ingreso_carrera=date(2016, 3, 1),
                fecha_egreso_carrera=date(2020, 12, 1),
            )

    def _crear_graduado_sin_carrera(self):
        return Graduado.objects.create(
            dni="42000003",
            anio_ingreso_universidad=2013,
            nombre="Carlos",
            apellido="SinCarrera",
        )

    def test_listado_devuelve_una_fila_por_carrera(self):
        graduado = Graduado.objects.get(pk="42000001")
        GraduadoCarrera.objects.create(
            dni_graduado=graduado,
            codigo_carrera=self.carrera_b,
            fecha_ingreso_carrera=date(2017, 3, 1),
            fecha_egreso_carrera=date(2021, 12, 1),
        )

        filas = obtener_filas_busqueda({})
        mismo_dni = [
            fila for fila in filas if fila.dni_graduado_id == "42000001"
        ]

        self.assertEqual(len(mismo_dni), 2)
        self.assertEqual(
            {fila.codigo_carrera_id for fila in mismo_dni},
            {"FA1", "FB1"},
        )
        self.assertTrue(
            all(fila.cantidad_carreras == 2 for fila in mismo_dni)
        )

    def test_graduado_sin_carrera_aparece_con_vacio_en_el_listado(self):
        self._crear_graduado_sin_carrera()

        filas = obtener_filas_busqueda({})
        fila = next(
            fila for fila in filas if fila.dni_graduado_id == "42000003"
        )

        self.assertTrue(fila.sin_carrera)
        self.assertIsNone(fila.codigo_carrera_id)
        self.assertEqual(fila.cantidad_carreras, 0)
        self.assertEqual(fila.anio_ingreso_universidad, 2013)

        self.iniciar_sesion(self.titulos)
        respuesta = self.client.get(reverse("lista_graduados"))

        self.assertContains(respuesta, "42000003")
        self.assertContains(respuesta, "Sin carrera")
        self.assertContains(respuesta, "Vacio")
        self.assertContains(respuesta, "2013")
        self.assertNotContains(
            respuesta,
            reverse("editar_graduado", args=["42000003", "FA1"]),
        )

    def test_filtro_situacion_y_orden_por_inconsistencias(self):
        self._crear_graduado_sin_carrera()

        filas = obtener_filas_busqueda({"situacion": "sin_carrera"})
        self.assertEqual(
            [fila.dni_graduado_id for fila in filas],
            ["42000003"],
        )

        filas = obtener_filas_busqueda({"situacion": "con_carrera"})
        self.assertEqual(
            {fila.dni_graduado_id for fila in filas},
            {"42000001", "42000002"},
        )

        # El orden por defecto pone la inconsistencia al principio.
        filas = obtener_filas_busqueda({})
        self.assertEqual(filas[0].dni_graduado_id, "42000003")
        self.assertTrue(filas[0].sin_carrera)

        # Con otro orden, vuelve a ordenar por DNI.
        filas = obtener_filas_busqueda({"orden": "legajo"})
        self.assertEqual(filas[0].dni_graduado_id, "42000001")

    def test_filtro_de_carrera_excluye_a_quien_no_tiene_carrera(self):
        self._crear_graduado_sin_carrera()

        filas = obtener_filas_busqueda({"carrera": "FA1"})

        self.assertEqual(
            [fila.dni_graduado_id for fila in filas],
            ["42000001"],
        )

    def test_excel_ignora_los_controles_nuevos_del_buscador(self):
        from openpyxl import load_workbook

        self._crear_graduado_sin_carrera()
        self.iniciar_sesion(self.admin)

        respuesta = self.client.get(
            reverse("exportar_graduados") + "?situacion=sin_carrera&orden=legajo"
        )
        libro = load_workbook(BytesIO(respuesta.content))
        dnis = [
            fila[0]
            for fila in libro.active.iter_rows(min_row=2, values_only=True)
        ]

        self.assertIn("42000001", dnis)
        self.assertNotIn("42000003", dnis)

        lista = self.client.get(
            reverse("lista_graduados") + "?situacion=sin_carrera"
        )
        self.assertNotIn("situacion", lista.context["excel_qs"])

    def test_filtro_por_carrera_no_pierde_la_condicion(self):
        filas = obtener_filas_filtradas({"carrera": "FA1"})

        self.assertEqual(filas.count(), 1)
        self.assertEqual(
            filas.first().dni_graduado_id,
            "42000001",
        )

    def test_filtro_por_escuela(self):
        filas = obtener_filas_filtradas({"escuela": str(self.escuela_b.pk)})

        self.assertEqual(filas.count(), 1)
        self.assertEqual(
            filas.first().dni_graduado_id,
            "42000002",
        )

    def test_exportacion_respeta_el_filtro(self):
        self.iniciar_sesion(self.admin)

        respuesta = self.client.get(
            reverse("exportar_graduados") + "?carrera=FA1"
        )

        self.assertEqual(respuesta.status_code, 200)
        self.assertIn(
            "spreadsheetml",
            respuesta["Content-Type"],
        )

    def test_exportacion_incluye_anio_uarg(self):
        from openpyxl import load_workbook

        self.iniciar_sesion(self.admin)

        respuesta = self.client.get(reverse("exportar_graduados"))
        libro = load_workbook(BytesIO(respuesta.content))
        hoja = libro.active

        self.assertIn(
            "Año de ingreso a la UARG",
            [celda.value for celda in hoja[1]],
        )

        fila = next(
            fila
            for fila in hoja.iter_rows(min_row=2, values_only=True)
            if fila[0] == "42000001"
        )
        self.assertEqual(fila[4], 2015)


class BloqueoLoginTest(BasePrueba):
    def test_bloqueo_tras_intentos_fallidos(self):
        from django.conf import settings

        for _ in range(settings.LOGIN_MAX_INTENTOS):
            self.client.post(
                reverse("login"),
                {"email": "titulos@gmail.com", "codigo": "000000"},
            )

        self.titulos.refresh_from_db()
        self.assertIsNotNone(self.titulos.bloqueado_hasta)

        respuesta = self.client.post(
            reverse("login"),
            {"email": "titulos@gmail.com", "codigo": self.codigo_titulos},
        )

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "bloqueada")
        self.assertIsNone(self.client.session.get(CLAVE_SESION))

    def test_login_exitoso_audita(self):
        self.client.post(
            reverse("login"),
            {"email": "titulos@gmail.com", "codigo": self.codigo_titulos},
        )

        self.assertTrue(
            Auditoria.objects.filter(
                accion="login",
                entidad_id=str(self.titulos.id_usuario),
            ).exists()
        )


class AnaliticoPromediosTest(GeneracionAnaliticosTest):
    """Promedios calculados, override manual y recálculo."""

    def _payload_filas(self, notas):
        payload = dict(self._form_base())
        payload["accion"] = "validar"
        payload["fila_indice"] = ["01", "02"]
        payload["fila_anio"] = ["1", "2"]
        payload["fila_espacio"] = ["Materia Uno", "Materia Dos"]
        payload["fila_nota"] = [str(notas[0]), str(notas[1])]
        payload["fila_fecha"] = ["2024-03-13", "2024-03-13"]
        payload["fila_tipo"] = ["Examen", "Examen"]
        payload["fila_respaldo"] = ["RG1", "RG2"]
        payload["fila_folio"] = ["001", "002"]
        payload["fila_materia"] = ["9001", "9002"]
        return payload

    def test_validar_calcula_promedios_y_origen(self):
        self.iniciar_sesion(self.admin)

        payload = self._payload_filas([7, 10])
        payload.pop("promedio_sin_aplazo")
        payload.pop("promedio_con_aplazo")

        respuesta = self.client.post(
            reverse("generacion_analiticos"),
            payload,
        )

        self.assertEqual(respuesta.status_code, 302)

        registro = GraduadoCarrera.objects.get(
            dni_graduado_id="41734713",
            codigo_carrera=self.carrera,
        )

        self.assertEqual(registro.promedio_sin_aplazo, 8.5)
        self.assertEqual(registro.promedio_con_aplazo, 8.5)
        self.assertEqual(
            registro.origen_promedio_sin_aplazo,
            OrigenPromedio.CALCULADO,
        )
        self.assertEqual(
            registro.origen_promedio_con_aplazo,
            OrigenPromedio.CALCULADO,
        )

    def test_override_manual_se_conserva_y_audita(self):
        self.iniciar_sesion(self.admin)

        payload = self._payload_filas([7, 10])
        payload["promedio_sin_aplazo"] = "9.25"
        payload["promedio_con_aplazo"] = "9.10"

        respuesta = self.client.post(
            reverse("generacion_analiticos"),
            payload,
        )

        self.assertEqual(respuesta.status_code, 302)

        registro = GraduadoCarrera.objects.get(
            dni_graduado_id="41734713",
            codigo_carrera=self.carrera,
        )

        self.assertEqual(registro.promedio_sin_aplazo, 9.25)
        self.assertEqual(registro.promedio_con_aplazo, 9.10)
        self.assertEqual(
            registro.origen_promedio_sin_aplazo,
            OrigenPromedio.MANUAL,
        )
        self.assertTrue(
            Auditoria.objects.filter(
                accion="promedio_override",
            ).exists()
        )

    def test_recalcular_vuelve_al_valor_calculado(self):
        self.iniciar_sesion(self.admin)

        payload = self._payload_filas([7, 10])
        payload["promedio_sin_aplazo"] = "9.25"
        payload["promedio_con_aplazo"] = "9.10"
        self.client.post(reverse("generacion_analiticos"), payload)

        payload = self._payload_filas([7, 10])
        payload["accion"] = "recalcular"
        payload["promedio_sin_aplazo"] = "9.25"
        payload["promedio_con_aplazo"] = "9.10"

        respuesta = self.client.post(
            reverse("generacion_analiticos"),
            payload,
        )

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "8,5")

    def test_secundario_unico_por_graduado(self):
        self.iniciar_sesion(self.admin)

        payload = self._payload_filas([7, 10])
        self.client.post(reverse("generacion_analiticos"), payload)

        payload = self._payload_filas([7, 10])
        payload["nombre_secundario"] = "Otro Secundario"
        self.client.post(reverse("generacion_analiticos"), payload)

        self.assertEqual(
            Secundario.objects.filter(
                dni_graduado_id="41734713"
            ).count(),
            1,
        )
        self.assertEqual(
            Secundario.objects.get(
                dni_graduado_id="41734713"
            ).nombre_secundario,
            "Otro Secundario",
        )


class ListaGraduadosTest(BasePrueba):
    def setUp(self):
        self.escuela = Escuela.objects.create(
            nombre_escuela="Escuela Listado"
        )
        self.carrera = Carrera.objects.create(
            codigo_carrera="LI1",
            nombre_carrera="Carrera Listado",
            id_escuela=self.escuela,
        )

        for indice in range(30):
            graduado = Graduado.objects.create(
                dni=f"4100000{indice:02d}",
                anio_ingreso_universidad=2015,
                nombre=f"Nombre{indice}",
                apellido=f"Apellido{indice}",
            )
            GraduadoCarrera.objects.create(
                dni_graduado=graduado,
                codigo_carrera=self.carrera,
                fecha_ingreso_carrera=date(2016, 3, 1),
                fecha_egreso_carrera=date(2020, 12, 1),
                promedio_sin_aplazo=7.0,
                promedio_con_aplazo=6.5,
            )

    def test_lista_pagina1_y2(self):
        self.iniciar_sesion(self.titulos)

        respuesta = self.client.get(reverse("lista_graduados"))

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "Analítico")
        self.assertContains(respuesta, "En trámite")
        self.assertContains(respuesta, "Siguiente")

        respuesta = self.client.get(
            reverse("lista_graduados") + "?pagina=2"
        )

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "Anterior")


class NavegacionTest(BasePrueba):
    """El navbar debe permitir moverse entre módulos según el rol."""

    def test_navbar_muestra_modulos_principales(self):
        self.iniciar_sesion(self.titulos)

        respuesta = self.client.get(reverse("index"))

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "Navegación principal")
        self.assertContains(respuesta, reverse("generacion_analiticos"))
        self.assertContains(respuesta, reverse("lista_graduados"))
        self.assertContains(respuesta, reverse("estadisticas"))
        self.assertContains(respuesta, reverse("carga_datos"))
        self.assertContains(respuesta, reverse("carga_graduados"))
        self.assertContains(respuesta, reverse("gestion_academica"))

    def test_navbar_oculta_administracion_a_no_admin(self):
        self.iniciar_sesion(self.titulos)

        respuesta = self.client.get(reverse("index"))

        self.assertNotContains(respuesta, reverse("abm_usuarios"))
        self.assertNotContains(respuesta, reverse("abm_roles"))

    def test_navbar_muestra_administracion_a_admin(self):
        self.iniciar_sesion(self.admin)

        respuesta = self.client.get(reverse("index"))

        self.assertContains(respuesta, reverse("abm_usuarios"))
        self.assertContains(respuesta, reverse("abm_roles"))

    def test_modulo_activo_y_migas(self):
        self.iniciar_sesion(self.titulos)

        respuesta = self.client.get(reverse("lista_graduados"))

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, 'aria-current="page"')
        self.assertContains(respuesta, "Ruta de navegación")

    def test_render_de_modulos_principales(self):
        self.iniciar_sesion(self.admin)

        rutas = (
            "index",
            "lista_graduados",
            "estadisticas",
            "gestion_academica",
            "generacion_analiticos",
            "titulo_en_tramite",
            "carga_datos",
            "carga_graduados",
            "abm_usuarios",
            "abm_roles",
        )

        for nombre in rutas:
            with self.subTest(ruta=nombre):
                respuesta = self.client.get(reverse(nombre))
                self.assertEqual(respuesta.status_code, 200)

    def test_login_renderiza_sin_sesion(self):
        respuesta = self.client.get(reverse("login"))

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "Ingresar al sistema")
        self.assertContains(respuesta, "eGraduados")


# ==========================================================
# VALIDACIONES DE NEGOCIO
# ==========================================================

class ValidacionesNegocioTest(TestCase):
    def test_dni_solo_digitos(self):
        self.assertEqual(validar_dni(" 41734713 "), "41734713")

        for invalido in ("4173471a", "41.734.713", "", "123456"):
            with self.subTest(dni=invalido):
                with self.assertRaises(ValueError):
                    validar_dni(invalido)

    def test_legajo_derivado_de_dni_y_anio(self):
        self.assertEqual(
            generar_legajo("41734713", 2017), "1-41734713/17"
        )

    def test_legajo_derivado_acepta_anio_como_texto(self):
        self.assertEqual(
            generar_legajo("41734713", "2017"), "1-41734713/17"
        )

    def test_legajo_derivado_sin_dni_o_anio_es_none(self):
        self.assertIsNone(generar_legajo("41734713", None))
        self.assertIsNone(generar_legajo("", 2017))
        self.assertIsNone(generar_legajo(None, None))

    def test_legajo_se_actualiza_al_cambiar_el_anio(self):
        graduado = Graduado.objects.create(
            dni="41734713",
            anio_ingreso_universidad=2017,
            nombre="Ana",
            apellido="Perez",
        )
        self.assertEqual(graduado.legajo, "1-41734713/17")

        Graduado.objects.update_or_create(
            pk="41734713",
            defaults={
                "nombre": "Ana",
                "apellido": "Perez",
                "anio_ingreso_universidad": 2020,
            },
        )

        graduado.refresh_from_db()
        self.assertEqual(graduado.legajo, "1-41734713/20")

    def test_normalizar_dni_quita_espacios(self):
        self.assertEqual(normalizar_dni(" 41734713 "), "41734713")
        self.assertEqual(normalizar_dni(None), "")

    def test_dni_unico_considera_la_clave_actual(self):
        Graduado.objects.create(
            dni="41734713",
            anio_ingreso_universidad=2017,
            nombre="Ana",
            apellido="Perez",
        )

        self.assertFalse(validar_dni_unico("41734713"))
        self.assertTrue(
            validar_dni_unico("41734713", dni_actual="41734713")
        )
        self.assertTrue(validar_dni_unico("99999999"))

    def test_anios_nacimiento_uarg_y_carrera(self):
        validar_anios(date(1999, 1, 1), 2017, 2018)

        with self.assertRaises(ValueError):
            validar_anios(date(1999, 1, 1), 2019, 2018)

        with self.assertRaises(ValueError):
            validar_anios(date(2020, 1, 1), 2017, 2018)

        # El año de egreso del secundario no se valida.
        validar_anios(date(1999, 1, 1), 2017, 2018)

    def test_egreso_debe_ser_posterior_al_ingreso_a_la_carrera(self):
        with self.assertRaises(ValueError):
            validar_cronologia_fechas(
                date(2018, 3, 1),
                date(2018, 3, 1),
            )

        with self.assertRaises(ValueError):
            validar_cronologia_fechas(
                date(2017, 3, 1),
                date(2017, 3, 1),
            )

        validar_cronologia_fechas(
            date(2018, 3, 1),
            date(2024, 4, 24),
            date(1999, 1, 1),
        )

    def test_fachada_devuelve_todos_los_errores(self):
        normalizados, errores = validar_datos_graduado({
            # El legajo no es un dato de entrada: se ignora.
            "legajo": "UARG-MAL/2017",
            "dni": "41.734.713",
            "anio_ingreso_universidad": 2019,
            "anio_ingreso_carrera": 2018,
            "fecha_nacimiento": date(2020, 1, 1),
            "fecha_ingreso_carrera": date(2018, 3, 1),
            "fecha_egreso_carrera": date(2017, 1, 1),
        })

        self.assertGreaterEqual(len(errores), 4)
        self.assertTrue(any("DNI" in error for error in errores))
        self.assertFalse(any("legajo" in error for error in errores))
        self.assertTrue(any("año" in error for error in errores))
        # Sin DNI válido no hay legajo derivado.
        self.assertIsNone(normalizados["legajo"])


# ==========================================================
# BORRADO DE GRADUADOS
# ==========================================================

class EliminacionGraduadoTest(BasePrueba):
    DNI = "12345678"

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()

        cls.escuela = Escuela.objects.create(nombre_escuela="Escuela Borrado")
        cls.cara = Carrera.objects.create(
            codigo_carrera="CA1",
            nombre_carrera="Carrera Uno",
            id_escuela=cls.escuela,
        )
        cls.carb = Carrera.objects.create(
            codigo_carrera="CA2",
            nombre_carrera="Carrera Dos",
            id_escuela=cls.escuela,
        )
        cls.graduado = Graduado.objects.create(
            dni=cls.DNI,
            anio_ingreso_universidad=2015,
            nombre="Ana",
            apellido="Perez",
        )

        for carrera in (cls.cara, cls.carb):
            GraduadoCarrera.objects.create(
                dni_graduado=cls.graduado,
                codigo_carrera=carrera,
                fecha_ingreso_carrera=date(2016, 3, 1),
                fecha_egreso_carrera=date(2020, 12, 15),
            )

        cls.materia = Materia.objects.create(
            codigo_materia="MB1",
            nombre_materia="Materia Borrado",
        )
        cls.examen = Examen.objects.create(
            acta_respaldatoria="ACT-BOR-1",
            codigo_materia=cls.materia,
            fecha_examen=date(2020, 12, 1),
        )
        GraduadoExamen.objects.create(
            id_examen=cls.examen,
            dni_graduado=cls.graduado,
            codigo_carrera=cls.cara,
            nota=8,
            resultado="Aprobado",
        )
        Analitico.objects.create(
            dni_graduado=cls.graduado,
            codigo_carrera=cls.cara,
            tipo_documento="titulo",
            id_usuario=cls.admin,
        )
        Secundario.objects.create(
            dni_graduado=cls.graduado,
            nombre_secundario="CPES 25",
        )
        DatosNacimiento.objects.create(
            dni_graduado=cls.graduado,
            fecha_nacimiento=date(1990, 4, 6),
        )

    def test_no_admin_no_puede_eliminar(self):
        self.iniciar_sesion(self.titulos)

        respuesta = self.client.post(
            reverse("eliminar_graduado", args=[self.DNI]),
            {"accion": "graduado"},
        )

        self.assertEqual(respuesta.status_code, 403)
        self.assertTrue(
            Graduado.objects.filter(pk=self.DNI).exists()
        )

    def test_quitar_carrera_conserva_al_graduado(self):
        self.iniciar_sesion(self.admin)

        respuesta = self.client.post(
            reverse("eliminar_graduado", args=[self.DNI]),
            {
                "accion": "carrera",
                "carrera": "CA1",
                "confirmacion": CONFIRMACION_BORRADO,
            },
        )

        self.assertEqual(respuesta.status_code, 302)
        self.assertFalse(
            GraduadoCarrera.objects.filter(
                dni_graduado=self.graduado,
                codigo_carrera="CA1",
            ).exists()
        )
        self.assertTrue(
            GraduadoCarrera.objects.filter(
                dni_graduado=self.graduado,
                codigo_carrera="CA2",
            ).exists()
        )
        self.assertEqual(
            GraduadoExamen.objects.filter(
                dni_graduado=self.graduado
            ).count(),
            0,
        )
        self.assertEqual(
            Analitico.objects.filter(
                dni_graduado=self.graduado
            ).count(),
            0,
        )
        self.assertTrue(
            Auditoria.objects.filter(
                accion="eliminar_carrera_graduado",
                entidad_id=f"{self.DNI}|CA1",
            ).exists()
        )

    def test_eliminar_graduado_exige_doble_confirmacion(self):
        self.iniciar_sesion(self.admin)
        url = reverse("eliminar_graduado", args=[self.DNI])

        respuesta = self.client.post(url, {"accion": "graduado"})
        self.assertEqual(respuesta.status_code, 302)
        self.assertTrue(Graduado.objects.filter(pk=self.DNI).exists())

        respuesta = self.client.post(
            url,
            {
                "accion": "graduado",
                "confirmacion": CONFIRMACION_BORRADO,
            },
        )

        self.assertEqual(respuesta.status_code, 302)
        self.assertFalse(Graduado.objects.filter(pk=self.DNI).exists())
        self.assertEqual(Secundario.objects.count(), 0)
        self.assertEqual(DatosNacimiento.objects.count(), 0)
        self.assertEqual(Analitico.objects.count(), 0)
        self.assertTrue(
            Auditoria.objects.filter(
                accion="eliminar_graduado",
                entidad_id=self.DNI,
            ).exists()
        )

    def test_borrado_conserva_filtros_del_buscador(self):
        self.iniciar_sesion(self.admin)

        respuesta = self.client.post(
            reverse("eliminar_graduado", args=[self.DNI]),
            {
                "accion": "graduado",
                "confirmacion": CONFIRMACION_BORRADO,
                "filtros_qs": "nombre=Ana&carrera=CA1",
            },
        )

        self.assertIn("nombre=Ana", respuesta.url)
        self.assertIn("carrera=CA1", respuesta.url)

    def test_botones_solo_para_administradores(self):
        respuesta = self.client.get(reverse("lista_graduados"))
        self.assertEqual(respuesta.status_code, 302)

        self.iniciar_sesion(self.titulos)
        respuesta = self.client.get(reverse("lista_graduados"))
        self.assertNotContains(respuesta, "Eliminar graduado")

        self.iniciar_sesion(self.admin)
        respuesta = self.client.get(reverse("lista_graduados"))
        self.assertContains(respuesta, "Eliminar graduado")
        self.assertContains(respuesta, "Quitar carrera")
        self.assertContains(respuesta, "Escribí ELIMINAR")


# ==========================================================
# RESOLUCIONES MÚLTIPLES
# ==========================================================

class ResolucionesMultiplesTest(GeneracionAnaliticosTest):
    def test_guarda_varias_resoluciones_por_tipo(self):
        self.iniciar_sesion(self.admin)
        url = reverse("generacion_analiticos")

        archivo = SimpleUploadedFile(
            "notas.xlsx",
            _lincoln_xlsx_fixture(),
            content_type=(
                "application/vnd.openxmlformats-officedocument."
                "spreadsheetml.sheet"
            ),
        )

        institucionales = [
            "141/CS/98", "218/CS/00", "186/CS/06",
            "250/CS/10", "300/CS/12",
        ]
        ministeriales = [
            "1496/99", "1500/00", "1510/01", "1520/02", "1530/03",
        ]
        otros = [
            "Nota DNGU N.° 1186/14", "Disposición 12/20",
            "Resolución 45/21", "Nota 78/22", "Disposición 90/23",
        ]

        payload = self._form_base()
        payload.update({
            "accion": "continuar",
            "archivo_notas": archivo,
            "resoluciones_institucionales": institucionales,
            "resoluciones_ministeriales": ministeriales,
            "otros_instrumentos": otros,
        })
        respuesta = self.client.post(url, payload)
        self.assertEqual(respuesta.status_code, 302)

        payload = self._form_base()
        payload.update({
            "accion": "validar",
            "fila_indice": ["01", "02"],
            "fila_anio": ["1", "2"],
            "fila_espacio": ["Materia Uno", "Materia Dos"],
            "fila_nota": ["7", "10"],
            "fila_fecha": ["2023-03-01", "2021-12-16"],
            "fila_tipo": ["Final", "Final"],
            "fila_respaldo": ["RG00000001", "RG00000002"],
            "fila_folio": ["001", "002"],
            "fila_materia": ["9001", "9002"],
            "resoluciones_institucionales": institucionales,
            "resoluciones_ministeriales": ministeriales,
            "otros_instrumentos": otros,
        })
        respuesta = self.client.post(url, payload)
        self.assertEqual(respuesta.status_code, 302)

        carrera = Carrera.objects.get(pk="PR1")
        self.assertEqual(
            set(
                carrera.resoluciones.values_list("resolucion", flat=True)
            ),
            set(institucionales + ministeriales + otros),
        )

        self.assertEqual(
            Resolucion.objects.get(
                resolucion="218/CS/00"
            ).tipo_resolucion,
            "institucional",
        )
        self.assertEqual(
            Resolucion.objects.get(
                resolucion="1500/00"
            ).tipo_resolucion,
            "ministerial_nacional",
        )
        self.assertEqual(
            Resolucion.objects.get(
                resolucion="Disposición 12/20"
            ).tipo_resolucion,
            "otro_instrumento",
        )

        # La descarga debe incluir las 15 resoluciones sin
        # desbordar la plantilla.
        descarga = self.client.post(url, {
            "accion": "descargar",
            "dni": "41734713",
            "carrera": "PR1",
        })
        self.assertEqual(descarga.status_code, 200)
        self.assertEqual(
            descarga["Content-Type"],
            (
                "application/vnd.openxmlformats-officedocument."
                "wordprocessingml.document"
            ),
        )

        from docx import Document

        documento = Document(BytesIO(descarga.content))
        texto = "\n".join(p.text for p in documento.paragraphs)

        for resolucion in institucionales + ministeriales + otros:
            with self.subTest(resolucion=resolucion):
                self.assertIn(resolucion, texto)


# ==========================================================
# PROVINCIAS SUGERIDAS
# ==========================================================

class ProvinciasSugeridasTest(BasePrueba):
    def test_incluye_todas_las_provincias_base_y_las_de_la_bd(self):
        sugeridas = provincias_sugeridas()

        for nombre in (
            "Buenos Aires",
            "Ciudad Autónoma de Buenos Aires",
            "Santa Cruz",
            "Tierra del Fuego",
            "Tucumán",
        ):
            with self.subTest(provincia=nombre):
                self.assertIn(nombre, sugeridas)

        Provincia.objects.create(nombre_provincia="Provincia Personalizada")
        self.assertIn("Provincia Personalizada", provincias_sugeridas())

    def test_datalists_de_analitico_y_edicion(self):
        escuela = Escuela.objects.create(nombre_escuela="Escuela Provincias")
        carrera = Carrera.objects.create(
            codigo_carrera="CPR1",
            nombre_carrera="Carrera Provincias",
            id_escuela=escuela,
        )
        graduado = Graduado.objects.create(
            dni="12345678",
            anio_ingreso_universidad=2015,
            nombre="Ana",
            apellido="Perez",
        )
        GraduadoCarrera.objects.create(
            dni_graduado=graduado,
            codigo_carrera=carrera,
            fecha_ingreso_carrera=date(2016, 3, 1),
            fecha_egreso_carrera=date(2020, 12, 15),
        )

        self.iniciar_sesion(self.admin)

        respuesta = self.client.get(reverse("generacion_analiticos"))
        self.assertContains(respuesta, '<option value="Buenos Aires">')

        respuesta = self.client.get(
            reverse("editar_graduado", args=[graduado.pk, carrera.pk])
        )
        self.assertContains(respuesta, '<option value="Buenos Aires">')


# ==========================================================
# VALIDACIONES EN CARGA EXCEL
# ==========================================================

class CargaDatosValidacionesTest(BasePrueba):
    def setUp(self):
        self.escuela = Escuela.objects.create(nombre_escuela="Escuela Excel")
        self.carrera = Carrera.objects.create(
            codigo_carrera="CEX1",
            nombre_carrera="Carrera Excel",
            id_escuela=self.escuela,
        )

    def _archivo(self, dni, ingreso_uarg, ingreso_carrera, egreso):
        """El DNI identifica al graduado; el legajo se deriva después."""

        from openpyxl import Workbook

        libro = Workbook()
        hoja = libro.active
        hoja.append(CargaDatos.COLUMNAS_REQUERIDAS)
        hoja.append([
            dni,
            "Ana",
            "Perez",
            8,
            7,
            ingreso_carrera,
            egreso,
            "CEX1",
            ingreso_uarg,
        ])

        buffer = BytesIO()
        libro.save(buffer)

        return SimpleUploadedFile(
            "graduados.xlsx",
            buffer.getvalue(),
            content_type=(
                "application/vnd.openxmlformats-officedocument."
                "spreadsheetml.sheet"
            ),
        )

    def test_acepta_datos_coherentes(self):
        resultado = CargaDatos.cargar_excel(
            self._archivo(
                41734713,
                "01/03/2017",
                "01/03/2018",
                "24/04/2024",
            )
        )

        self.assertEqual(resultado["filas_procesadas"], 1)
        graduado = Graduado.objects.get(pk="41734713")
        self.assertEqual(graduado.legajo, "1-41734713/17")

    def test_acepta_anio_suelto_en_excel(self):
        resultado = CargaDatos.cargar_excel(
            self._archivo(
                41734713,
                2017,
                "01/03/2018",
                "24/04/2024",
            )
        )

        self.assertEqual(resultado["filas_procesadas"], 1)
        graduado = Graduado.objects.get(pk="41734713")
        self.assertEqual(graduado.anio_ingreso_universidad, 2017)

    def test_acepta_fecha_y_conserva_solo_el_anio(self):
        resultado = CargaDatos.cargar_excel(
            self._archivo(
                41734713,
                date(2017, 5, 10),
                "01/03/2018",
                "24/04/2024",
            )
        )

        self.assertEqual(resultado["filas_procesadas"], 1)
        graduado = Graduado.objects.get(pk="41734713")
        self.assertEqual(graduado.anio_ingreso_universidad, 2017)

    def test_acepta_ingreso_uarg_vacio_sin_legajo(self):
        resultado = CargaDatos.cargar_excel(
            self._archivo(
                "41734713",
                None,
                "01/03/2018",
                "24/04/2024",
            )
        )

        self.assertEqual(resultado["filas_procesadas"], 1)
        graduado = Graduado.objects.get(pk="41734713")
        self.assertIsNone(graduado.anio_ingreso_universidad)
        self.assertIsNone(graduado.legajo)

    def test_rechaza_dni_invalido(self):
        with self.assertRaises(ValueError) as contexto:
            CargaDatos.cargar_excel(
                self._archivo(
                    "41.734.713",
                    "01/03/2017",
                    "01/03/2018",
                    "24/04/2024",
                )
            )

        mensaje = str(contexto.exception)
        self.assertIn("DNI", mensaje)
        self.assertNotIn("legajo", mensaje)

    def test_rechaza_anios_invertidos_y_egreso_anterior(self):
        with self.assertRaises(ValueError) as contexto:
            CargaDatos.cargar_excel(
                self._archivo(
                    "41734713",
                    "01/03/2019",
                    "01/03/2018",
                    "01/01/2017",
                )
            )

        mensaje = str(contexto.exception)
        self.assertIn("ingreso a la universidad", mensaje)
        self.assertIn("egreso", mensaje)
