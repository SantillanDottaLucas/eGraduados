"""
Formularios de la app academico.
"""

from django import forms

from .models import (
    Carrera,
    Escuela,
    GrupoOptativo,
    Materia,
    PlanEstudios,
    PlanEstudiosGrupoOptativo,
    PlanEstudiosMateria,
    Rol,
    Usuario,
    Resolucion,
)


# ==================================================
# AYUDAS
# ==================================================

def pk_compuesta_completa(instance):
    """
    True cuando la instancia tiene valor en TODAS las partes
    de su clave primaria (simple o compuesta).

    Una instancia nueva de un modelo con clave primaria
    compuesta (ej. «(None, None)») es "truthy", por lo que
    «if instance.pk» no alcanza.
    """

    pk = instance.pk

    if pk is None:
        return False

    if isinstance(pk, tuple):
        return all(valor is not None for valor in pk)

    return bool(pk)


def validar_email_gmail(email):
    """Exige una dirección de Gmail (@gmail.com)."""

    email = email.strip().lower()

    if not email.endswith("@gmail.com"):
        raise forms.ValidationError(
            "El email debe ser una cuenta de Gmail (@gmail.com)."
        )

    return email


# ==================================================
# USUARIOS Y ROLES
# ==================================================

class RolForm(forms.ModelForm):
    class Meta:
        model = Rol
        fields = ["nombre_rol", "puede_administrar"]
        labels = {
            "nombre_rol": "Nombre del rol",
            "puede_administrar": (
                "Puede administrar usuarios y roles"
            ),
        }
        widgets = {
            "nombre_rol": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Ejemplo: Consulta",
                }
            ),
        }

    def clean_nombre_rol(self):
        return self.cleaned_data["nombre_rol"].strip()


class UsuarioForm(forms.ModelForm):
    class Meta:
        model = Usuario
        fields = ["nombre_usuario", "email", "id_rol"]
        labels = {
            "nombre_usuario": "Nombre de usuario",
            "email": "Email de Gmail",
            "id_rol": "Rol",
        }
        widgets = {
            "nombre_usuario": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Nombre visible del usuario",
                }
            ),
            "email": forms.EmailInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "usuario@gmail.com",
                }
            ),
            "id_rol": forms.Select(attrs={"class": "form-select"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # El email ya no se modifica una vez creado el usuario.
        if self.instance and self.instance.pk:
            self.fields["email"].disabled = True

    def clean_nombre_usuario(self):
        return self.cleaned_data["nombre_usuario"].strip()

    def clean_email(self):
        return validar_email_gmail(self.cleaned_data["email"])


# ==================================================
# EDICIÓN DE GRADUADOS
# ==================================================

class CarreraModelChoiceField(forms.ModelChoiceField):
    """Muestra las carreras como «código — nombre»."""

    def label_from_instance(self, obj):
        return f"{obj.codigo_carrera} — {obj.nombre_carrera}"


class EdicionGraduadoForm(forms.Form):
    """
    Formulario de edición de los datos personales de un graduado
    y de su relación con una carrera (incluye la posibilidad de
    cambiar la carrera asociada).
    """

    codigo_carrera = CarreraModelChoiceField(
        queryset=Carrera.objects.select_related("id_escuela").order_by(
            "nombre_carrera"
        ),
        label="Carrera",
        empty_label=None,
        widget=forms.Select(attrs={"class": "form-select"}),
    )

    nombre = forms.CharField(
        max_length=100,
        label="Nombre",
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )

    apellido = forms.CharField(
        max_length=100,
        label="Apellido",
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )

    dni = forms.CharField(
        max_length=20,
        label="DNI",
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )

    fecha_ingreso_universidad = forms.DateField(
        label="Ingreso a la universidad",
        widget=forms.DateInput(
            attrs={"type": "date", "class": "form-control"},
            format="%Y-%m-%d",
        ),
    )

    fecha_ingreso_carrera = forms.DateField(
        label="Ingreso a la carrera",
        widget=forms.DateInput(
            attrs={"type": "date", "class": "form-control"},
            format="%Y-%m-%d",
        ),
    )

    fecha_egreso_carrera = forms.DateField(
        label="Egreso de la carrera",
        widget=forms.DateInput(
            attrs={"type": "date", "class": "form-control"},
            format="%Y-%m-%d",
        ),
    )

    promedio_sin_aplazo = forms.FloatField(
        label="Promedio sin aplazo",
        required=False,
        widget=forms.NumberInput(
            attrs={
                "class": "form-control",
                "step": "0.01",
                "min": 0,
                "max": 10,
            }
        ),
    )

    promedio_con_aplazo = forms.FloatField(
        label="Promedio con aplazo",
        required=False,
        widget=forms.NumberInput(
            attrs={
                "class": "form-control",
                "step": "0.01",
                "min": 0,
                "max": 10,
            }
        ),
    )

    fecha_nacimiento = forms.DateField(
        label="Fecha de nacimiento",
        required=False,
        widget=forms.DateInput(
            attrs={"type": "date", "class": "form-control"},
            format="%Y-%m-%d",
        ),
    )

    ciudad_nacimiento = forms.CharField(
        label="Ciudad de nacimiento",
        required=False,
        max_length=100,
        widget=forms.TextInput(attrs={"class": "form-control", "list": "ciudades"}),
    )

    provincia_nacimiento = forms.CharField(
        label="Provincia de nacimiento",
        required=False,
        max_length=100,
        widget=forms.TextInput(attrs={"class": "form-control", "list": "provincias"}),
    )

    nombre_secundario = forms.CharField(
        label="Nombre del secundario",
        required=False,
        max_length=200,
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )

    titulo_secundario = forms.CharField(
        label="Título del secundario",
        required=False,
        max_length=200,
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )

    ciudad_secundario = forms.CharField(
        label="Ciudad del secundario",
        required=False,
        max_length=100,
        widget=forms.TextInput(attrs={"class": "form-control", "list": "ciudades"}),
    )

    provincia_secundario = forms.CharField(
        label="Provincia del secundario",
        required=False,
        max_length=100,
        widget=forms.TextInput(attrs={"class": "form-control", "list": "provincias"}),
    )

    anio_egreso_secundario = forms.IntegerField(
        label="Año de egreso del secundario",
        required=False,
        min_value=1900,
        max_value=2100,
        widget=forms.NumberInput(attrs={"class": "form-control"}),
    )

    def clean(self):
        datos = super().clean()

        # Coherencia cronológica de las tres fechas.
        try:
            from .servicios.validaciones import (
                validar_cronologia_fechas,
            )

            validar_cronologia_fechas(
                datos.get("fecha_ingreso_universidad"),
                datos.get("fecha_ingreso_carrera"),
                datos.get("fecha_egreso_carrera"),
            )

        except ValueError as error:
            raise forms.ValidationError(str(error))

        return datos


# ==================================================
# ABM ACADÉMICO: ESCUELAS Y CARRERAS
# ==================================================

class EscuelaForm(forms.ModelForm):
    class Meta:
        model = Escuela
        fields = ["nombre_escuela"]
        labels = {"nombre_escuela": "Nombre de la escuela"}
        widgets = {
            "nombre_escuela": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Nombre de la escuela",
                }
            ),
        }

    def clean_nombre_escuela(self):
        return self.cleaned_data["nombre_escuela"].strip()


class CarreraForm(forms.ModelForm):
    class Meta:
        model = Carrera
        fields = ["codigo_carrera", "nombre_carrera", "id_escuela"]
        labels = {
            "codigo_carrera": "Código de carrera",
            "nombre_carrera": "Nombre de la carrera",
            "id_escuela": "Escuela",
        }
        widgets = {
            "codigo_carrera": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Código",
                }
            ),
            "nombre_carrera": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Nombre de la carrera",
                }
            ),
            "id_escuela": forms.Select(attrs={"class": "form-select"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # El código es la clave primaria: no se edita.
        if self.instance and self.instance.pk:
            self.fields["codigo_carrera"].disabled = True

    def clean_codigo_carrera(self):
        return self.cleaned_data["codigo_carrera"].strip()

    def clean_nombre_carrera(self):
        return self.cleaned_data["nombre_carrera"].strip()


# ==================================================
# ABM ACADÉMICO: PLANES Y MATERIAS
# ==================================================

class PlanEstudiosForm(forms.ModelForm):
    class Meta:
        model = PlanEstudios
        fields = ["codigo_plan", "codigo_carrera"]
        labels = {
            "codigo_plan": "Código de plan",
            "codigo_carrera": "Carrera",
        }
        widgets = {
            "codigo_plan": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Código del plan",
                }
            ),
            "codigo_carrera": forms.Select(
                attrs={"class": "form-select"}
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # El código es la clave primaria: no se edita.
        if self.instance and self.instance.pk:
            self.fields["codigo_plan"].disabled = True

        # Ordenar las carreras por nombre.
        self.fields["codigo_carrera"].queryset = (
            Carrera.objects.order_by("nombre_carrera")
        )

    def clean_codigo_plan(self):
        return self.cleaned_data["codigo_plan"].strip()


class MateriaForm(forms.ModelForm):
    class Meta:
        model = Materia
        fields = ["codigo_materia", "nombre_materia"]
        labels = {
            "codigo_materia": "Código de materia",
            "nombre_materia": "Nombre de la materia",
        }
        widgets = {
            "codigo_materia": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Código",
                }
            ),
            "nombre_materia": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Nombre de la materia",
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # El código es la clave primaria: no se edita.
        if self.instance and self.instance.pk:
            self.fields["codigo_materia"].disabled = True

    def clean_codigo_materia(self):
        return self.cleaned_data["codigo_materia"].strip()

    def clean_nombre_materia(self):
        return self.cleaned_data["nombre_materia"].strip()


class PlanEstudiosMateriaForm(forms.ModelForm):
    """
    Asociación entre un plan de estudios y una materia
    (clave primaria compuesta).

    Cuando se selecciona un grupo optativo, la materia pasa a ser
    «miembro» del grupo: año, cuatrimestre y orden se dejan en
    NULL y se heredan de la ubicación del grupo en el plan.
    """

    class Meta:
        model = PlanEstudiosMateria
        fields = [
            "codigo_plan",
            "codigo_materia",
            "anio_materia",
            "cuatrimestre_materia",
            "orden_materia",
            "materia_requisito",
            "id_grupo_optativo",
        ]
        labels = {
            "codigo_plan": "Plan de estudios",
            "codigo_materia": "Materia",
            "anio_materia": "Año de la materia",
            "cuatrimestre_materia": "Cuatrimestre",
            "orden_materia": "Orden",
            "materia_requisito": "Es materia requisito",
            "id_grupo_optativo": "Grupo optativo",
        }
        widgets = {
            "codigo_plan": forms.Select(attrs={"class": "form-select"}),
            "codigo_materia": forms.Select(attrs={"class": "form-select"}),
            "anio_materia": forms.NumberInput(
                attrs={"class": "form-control", "min": 1}
            ),
            "cuatrimestre_materia": forms.Select(attrs={"class": "form-select"}),
            "orden_materia": forms.NumberInput(
                attrs={"class": "form-control", "min": 1}
            ),
            "materia_requisito": forms.CheckboxInput(
                attrs={"class": "form-check-input"}
            ),
            "id_grupo_optativo": forms.Select(attrs={"class": "form-select"}),
        }

    def __init__(self, *args, plan_inicial=None, **kwargs):
        super().__init__(*args, **kwargs)

        # La clave primaria compuesta (plan + materia) no se edita.
        if self.instance is not None and pk_compuesta_completa(self.instance):
            self.fields["codigo_plan"].disabled = True
            self.fields["codigo_materia"].disabled = True

        self.fields["codigo_plan"].queryset = (
            PlanEstudios.objects.order_by("codigo_plan")
        )
        self.fields["codigo_materia"].queryset = (
            Materia.objects.order_by("nombre_materia")
        )

        # Año/cuatrimestre/orden solo son obligatorios para
        # materias comunes (no para miembros de un grupo optativo).
        self.fields["anio_materia"].required = False
        self.fields["cuatrimestre_materia"].required = False
        self.fields["orden_materia"].required = False

        # Precargar el plan cuando se agrega una materia a un plan.
        if plan_inicial and not (
            self.instance is not None
            and pk_compuesta_completa(self.instance)
        ):
            self.fields["codigo_plan"].initial = plan_inicial

        # El selector de grupos lista solo los del plan elegido.
        plan_codigo = self._plan_elegido(plan_inicial)
        if plan_codigo:
            grupos = GrupoOptativo.objects.filter(
                codigo_plan=plan_codigo,
            ).order_by("nombre_grupo")
        else:
            grupos = GrupoOptativo.objects.none()

        self.fields["id_grupo_optativo"].queryset = grupos
        self.fields["id_grupo_optativo"].required = False

    def _plan_elegido(self, plan_inicial):
        """
        Devuelve el código de plan elegido (desde la instancia,
        los datos enviados o el valor inicial).
        """

        if self.instance is not None and pk_compuesta_completa(
            self.instance
        ):
            return self.instance.codigo_plan_id

        if plan_inicial:
            return plan_inicial

        return (self.data.get("codigo_plan") or "").strip() or None

    def clean_anio_materia(self):
        anio = self.cleaned_data.get("anio_materia")

        if anio is not None and anio < 1:
            raise forms.ValidationError(
                "El año de la materia debe ser mayor o igual a 1."
            )

        return anio

    def clean_orden_materia(self):
        orden = self.cleaned_data.get("orden_materia")

        if orden is not None and orden < 1:
            raise forms.ValidationError(
                "El orden de la materia debe ser mayor o igual a 1."
            )

        return orden

    def clean(self):
        datos = super().clean()

        plan = datos.get("codigo_plan")
        grupo = datos.get("id_grupo_optativo")

        if grupo and plan:
            # El grupo elegido debe pertenecer al plan.
            if grupo.codigo_plan_id != plan.codigo_plan:
                self.add_error(
                    "id_grupo_optativo",
                    "El grupo optativo elegido no pertenece a este plan.",
                )
                return datos

            # Materia miembro: hereda año/cuatrimestre/orden
            # de la ubicación del grupo en el plan.
            datos["anio_materia"] = None
            datos["cuatrimestre_materia"] = None
            datos["orden_materia"] = None

            ubicacion = PlanEstudiosGrupoOptativo.objects.filter(
                codigo_plan=plan,
                id_grupo_optativo=grupo,
            ).first()

            if ubicacion is None:
                self.add_error(
                    "id_grupo_optativo",
                    (
                        "El grupo optativo todavía no está ubicado "
                        "en el cronograma del plan. Ubicalo primero "
                        "en la pestaña «Grupos optativos»."
                    ),
                )

            return datos

        # Materia común: año/cuatrimestre/orden obligatorios.
        if grupo is None:
            for campo in (
                "anio_materia",
                "cuatrimestre_materia",
                "orden_materia",
            ):
                if datos.get(campo) in (None, ""):
                    self.add_error(
                        campo,
                        "Este campo es obligatorio para una materia común.",
                    )

        return datos

# ==================================================
# ABM ACADÉMICO: GRUPOS OPTATIVOS
# ==================================================

class GrupoOptativoForm(forms.ModelForm):
    """
    Definición de un grupo optativo de un plan
    (nombre único dentro del plan).
    """

    class Meta:
        model = GrupoOptativo
        fields = ["nombre_grupo"]
        labels = {"nombre_grupo": "Nombre del grupo optativo"}
        widgets = {
            "nombre_grupo": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Ej.: Optativas de Inteligencia Artificial",
                }
            ),
        }

    def __init__(self, *args, plan=None, **kwargs):
        super().__init__(*args, **kwargs)
        self._plan = plan

    def clean_nombre_grupo(self):
        nombre = self.cleaned_data["nombre_grupo"].strip()

        if not nombre:
            raise forms.ValidationError(
                "El nombre del grupo es obligatorio."
            )

        if self._plan is not None:
            repetidos = GrupoOptativo.objects.filter(
                codigo_plan=self._plan,
                nombre_grupo__iexact=nombre,
            )

            if self.instance and self.instance.pk:
                repetidos = repetidos.exclude(
                    pk=self.instance.pk
                )

            if repetidos.exists():
                raise forms.ValidationError(
                    "Ya existe un grupo con ese nombre en este plan."
                )

        return nombre


class PlanEstudiosGrupoOptativoForm(forms.Form):
    """
    Ubicación de un grupo optativo dentro del cronograma
    de un plan de estudios (año, cuatrimestre y orden).
    """

    id_grupo_optativo = forms.ModelChoiceField(
        queryset=GrupoOptativo.objects.none(),
        label="Grupo optativo",
        empty_label=None,
        widget=forms.Select(attrs={"class": "form-select"}),
    )

    anio_materia = forms.IntegerField(
        min_value=1,
        label="Año",
        widget=forms.NumberInput(attrs={"class": "form-control"}),
    )

    cuatrimestre_materia = forms.ChoiceField(
        choices=[("1er", "1er"), ("2do", "2do"), ("A", "A")],
        label="Cuatrimestre",
        widget=forms.Select(attrs={"class": "form-select"}),
    )

    orden_materia = forms.IntegerField(
        min_value=1,
        label="Orden",
        widget=forms.NumberInput(attrs={"class": "form-control"}),
    )

    def __init__(self, *args, plan=None, **kwargs):
        super().__init__(*args, **kwargs)

        self._plan = plan

        if plan is not None:
            self.fields["id_grupo_optativo"].queryset = (
                GrupoOptativo.objects
                .filter(codigo_plan=plan)
                .order_by("nombre_grupo")
            )

    def clean(self):
        datos = super().clean()

        grupo = datos.get("id_grupo_optativo")

        if grupo and self._plan is not None:
            if grupo.codigo_plan_id != self._plan.codigo_plan:
                self.add_error(
                    "id_grupo_optativo",
                    "El grupo elegido no pertenece a este plan.",
                )

        return datos

class ResolucionForm(forms.ModelForm):
    """Alta de una resolución/instrumento legal (ABM Carrera)."""

    class Meta:
        model = Resolucion
        fields = ["resolucion", "tipo_resolucion"]
        labels = {
            "resolucion": "Resolución / instrumento",
            "tipo_resolucion": "Tipo",
        }
        widgets = {
            "resolucion": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Ej.: 1496/99",
                }
            ),
            "tipo_resolucion": forms.Select(
                attrs={"class": "form-select"}
            ),
        }

    def clean_resolucion(self):
        return self.cleaned_data["resolucion"].strip()
