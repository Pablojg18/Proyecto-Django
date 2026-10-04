from django.conf import settings
from django.contrib.auth.models import User
from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.core.exceptions import ValidationError
from decimal import Decimal


class Carrera(models.Model):
    codigo = models.CharField(max_length=10, primary_key=True)
    nombre = models.CharField(max_length=150, unique=True)
    duracion = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(20)]
    )
    creditos = models.PositiveIntegerField(validators=[MinValueValidator(1)])

    class Meta:
        verbose_name = 'Carrera'
        verbose_name_plural = 'Carreras'
        ordering = ['codigo']

    def __str__(self):
        return f'{self.codigo} – {self.nombre}'


class Materia(models.Model):
    codigo = models.CharField(max_length=10, primary_key=True)
    nombre = models.CharField(max_length=150)
    unidades = models.PositiveSmallIntegerField(validators=[MinValueValidator(1)])
    creditos = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    carrera = models.ForeignKey(Carrera, on_delete=models.PROTECT,
                                related_name='materias')

    class Meta:
        verbose_name = 'Materia'
        verbose_name_plural = 'Materias'
        ordering = ['codigo']
        constraints = [
            models.UniqueConstraint(
                fields=['nombre', 'carrera'],
                name='unicidad_materia_por_carrera'
            ),
        ]

    def __str__(self):
        return f'{self.codigo} – {self.nombre}'


class Grupo(models.Model):
    TURNO_CHOICES = [
        ('MAT', 'Matutino'),
        ('VES', 'Vespertino'),
        ('MIX', 'Mixto'),
    ]

    materia = models.ForeignKey(Materia, on_delete=models.PROTECT,
                                related_name='grupos')
    periodo = models.CharField(max_length=9)
    cupo = models.PositiveSmallIntegerField(validators=[MinValueValidator(1)])
    num_alumnos = models.PositiveSmallIntegerField(
        default=0, validators=[MinValueValidator(0)]
    )
    horario = models.CharField(max_length=100)
    aula = models.CharField(max_length=20, blank=True, default='')
    turno = models.CharField(max_length=3, choices=TURNO_CHOICES, default='MAT')

    class Meta:
        verbose_name = 'Grupo'
        verbose_name_plural = 'Grupos'
        ordering = ['periodo', 'materia']
        constraints = [
            models.UniqueConstraint(
                fields=['materia', 'periodo', 'horario', 'aula'],
                name='unicidad_grupo_por_materia_periodo_horario_aula'
            ),
        ]

    def clean(self):
        super().clean()
        if self.num_alumnos > self.cupo:
            raise ValidationError({
                'num_alumnos': 'El número de alumnos no puede exceder el cupo.'
            })

    @property
    def lugares_disponibles(self):
        return max(self.cupo - self.num_alumnos, 0)

    @property
    def esta_lleno(self):
        return self.num_alumnos >= self.cupo

    def __str__(self):
        return f'{self.materia} – {self.periodo}'


class Calificacion(models.Model):
    alumno = models.ForeignKey('Alumno', on_delete=models.CASCADE,
                               related_name='calificaciones')
    grupo = models.ForeignKey(Grupo, on_delete=models.CASCADE,
                              related_name='calificaciones')
    valor = models.DecimalField(
        max_digits=4, decimal_places=1, null=True, blank=True,
        validators=[MinValueValidator(Decimal('0')),
                    MaxValueValidator(Decimal('10'))]
    )
    fecha_inscripcion = models.DateField(auto_now_add=True)
    fecha_captura = models.DateField(null=True, blank=True)

    class Meta:
        verbose_name = 'Calificación'
        verbose_name_plural = 'Calificaciones'
        ordering = ['alumno', 'grupo']
        constraints = [
            models.UniqueConstraint(
                fields=['alumno', 'grupo'],
                name='unicidad_inscripcion_alumno_grupo'
            ),
        ]

    def __str__(self):
        return f'{self.alumno} en {self.grupo}'

    @property
    def es_aprobada(self):
        return (self.valor is not None
                and self.valor >= settings.CALIFICACION_APROBADA)


class Alumno(models.Model):
    ESTATUS_CHOICES = [
        ('ACTIVO', 'Activo'),
        ('BAJA_TEMP', 'Baja temporal'),
        ('BAJA_DEF', 'Baja definitiva'),
        ('EGRESADO', 'Egresado'),
        ('TITULADO', 'Titulado'),
    ]

    matricula = models.CharField(max_length=10, primary_key=True)
    nombre = models.CharField(max_length=150)
    semestre = models.PositiveSmallIntegerField(
        default=1, validators=[MinValueValidator(1), MaxValueValidator(20)]
    )
    especialidad = models.CharField(max_length=100, blank=True, default='')
    estatus = models.CharField(max_length=10, choices=ESTATUS_CHOICES,
                               default='ACTIVO')
    carrera = models.ForeignKey(Carrera, on_delete=models.PROTECT,
                                related_name='alumnos')
    grupos = models.ManyToManyField(Grupo, through='Calificacion', blank=True,
                                    related_name='alumnos')

    class Meta:
        verbose_name = 'Alumno'
        verbose_name_plural = 'Alumnos'
        ordering = ['matricula']

    def __str__(self):
        return f'{self.matricula} – {self.nombre}'

    def delete(self, *args, **kwargs):
        """Al borrar al alumno se borra también su usuario de acceso."""
        perfil = getattr(self, 'perfil_de_alumno', None)
        usuario = perfil.usuario if perfil else None
        resultado = super().delete(*args, **kwargs)
        if usuario is not None:
            usuario.delete()
        return resultado

    @property
    def materias_cursadas(self):
        return self.calificaciones.count()

    @property
    def promedio_general(self):
        valores = [c.valor for c in self.calificaciones.all()
                   if c.valor is not None]
        if not valores:
            return None
        return (sum(valores) / Decimal(len(valores))).quantize(Decimal('0.0'))

    def carga_academica(self, periodo=None):
        """Inscripciones del alumno en un periodo (el vigente si no se indica)."""
        if periodo is None:
            periodo = settings.PERIODO_ACTUAL
        return (self.calificaciones
                .filter(grupo__periodo=periodo)
                .select_related('grupo', 'grupo__materia')
                .order_by('grupo__materia__codigo'))

    @property
    def tiene_carga_activa(self):
        """True si ya tiene materias inscritas en el periodo vigente."""
        return self.calificaciones.filter(
            grupo__periodo=settings.PERIODO_ACTUAL).exists()

    def ha_cursado(self, materia):
        """True si el alumno ya tiene una inscripción (calificada o no) de la materia."""
        return self.calificaciones.filter(grupo__materia=materia).exists()

    @property
    def materias_aprobadas(self):
        return [c for c in self.calificaciones.all()
                if c.valor is not None
                and c.valor >= settings.CALIFICACION_APROBADA]

    @property
    def creditos_acumulados(self):
        return sum(c.grupo.materia.creditos for c in self.materias_aprobadas)

    @property
    def creditos_en_curso(self):
        return sum(c.grupo.materia.creditos for c in self.carga_academica())

    @property
    def avance_carrera(self):
        """Porcentaje de créditos acumulados respecto a los créditos de la carrera."""
        total = self.carrera.creditos
        if not total:
            return 0
        return round(self.creditos_acumulados * 100 / total)


class Perfil(models.Model):
    """Rol del usuario dentro del sistema escolar."""

    ROL_CHOICES = [
        ('ADMINISTRADOR', 'Administrador'),
        ('COORDINADOR', 'Coordinador'),
        ('ESTUDIANTE', 'Estudiante'),
    ]

    usuario = models.OneToOneField(User, on_delete=models.CASCADE,
                                   related_name='perfil')
    rol = models.CharField(max_length=15, choices=ROL_CHOICES)
    alumno = models.OneToOneField(Alumno, on_delete=models.SET_NULL,
                                  null=True, blank=True,
                                  related_name='perfil_de_alumno',
                                  verbose_name='Alumno asociado')

    class Meta:
        verbose_name = 'Perfil'
        verbose_name_plural = 'Perfiles'
        ordering = ['usuario__username']

    def clean(self):
        super().clean()
        if self.rol == 'ESTUDIANTE' and self.alumno_id is None:
            raise ValidationError({
                'alumno': 'Un usuario estudiante debe tener un alumno asociado.'
            })
        if self.rol != 'ESTUDIANTE' and self.alumno_id is not None:
            raise ValidationError({
                'alumno': 'Solo los usuarios estudiante tienen alumno asociado.'
            })

    def __str__(self):
        return f'{self.usuario.username} – {self.get_rol_display()}'

    @property
    def es_administrador(self):
        return self.rol == 'ADMINISTRADOR'

    @property
    def es_coordinador(self):
        return self.rol == 'COORDINADOR'

    @property
    def es_estudiante(self):
        return self.rol == 'ESTUDIANTE'