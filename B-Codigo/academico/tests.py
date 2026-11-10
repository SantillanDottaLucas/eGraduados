from datetime import date

from django.contrib.auth.hashers import make_password
from django.test import TestCase
from django.urls import reverse

from .autenticacion import CLAVE_SESION, generar_codigo_acceso
from .models import (
    Carrera,
    Escuela,
    Graduado,
    GraduadoCarrera,
    Rol,
    Usuario,
)
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
            legajo_graduado="LEG1",
            dni="12345678",
            fecha_ingreso_universidad=date(2015, 3, 1),
            nombre="Ana",
            apellido="Perez",
        )
        cls.registro = GraduadoCarrera.objects.create(
            legajo_graduado=cls.graduado,
            codigo_carrera=cls.carrera,
            fecha_ingreso_carrera=date(2016, 3, 1),
            fecha_egreso_carrera=date(2020, 12, 15),
            promedio_con_aplazo=7.5,
            promedio_sin_aplazo=8.0,
        )

    def test_editar_graduado_valido(self):
        self.iniciar_sesion(self.titulos)

        respuesta = self.client.post(
            reverse("editar_graduado", args=["LEG1", "CAR1"]),
            {
                "nombre": "Ana Maria",
                "apellido": "Perez",
                "dni": "12345678",
                "fecha_ingreso_universidad": "2015-03-01",
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
            reverse("editar_graduado", args=["LEG1", "CAR1"]),
            {
                "nombre": "Ana",
                "apellido": "Perez",
                "dni": "12345678",
                "fecha_ingreso_universidad": "2015-03-01",
                "fecha_ingreso_carrera": "2021-03-01",
                "fecha_egreso_carrera": "2020-12-15",
                "promedio_sin_aplazo": "8.0",
                "promedio_con_aplazo": "7.5",
            },
        )

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "egreso")

    def test_dni_duplicado_rechazado(self):
        Graduado.objects.create(
            legajo_graduado="LEG2",
            dni="99999999",
            fecha_ingreso_universidad=date(2014, 3, 1),
            nombre="Otro",
            apellido="Alumno",
        )

        self.iniciar_sesion(self.titulos)

        respuesta = self.client.post(
            reverse("editar_graduado", args=["LEG1", "CAR1"]),
            {
                "nombre": "Ana",
                "apellido": "Perez",
                "dni": "99999999",
                "fecha_ingreso_universidad": "2015-03-01",
                "fecha_ingreso_carrera": "2016-03-01",
                "fecha_egreso_carrera": "2020-12-15",
                "promedio_sin_aplazo": "8.0",
                "promedio_con_aplazo": "7.5",
            },
        )

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "DNI")


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
                legajo_graduado=f"L{i}",
                dni=f"1000000{i}",
                fecha_ingreso_universidad=date(2015, 1, 1),
                nombre="N",
                apellido="A",
            )
            GraduadoCarrera.objects.create(
                legajo_graduado=g,
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
