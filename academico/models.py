from datetime import time
from decimal import Decimal

from django.conf import settings
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

# Las clases se pueden agendar solo dentro de este rango.
HORA_MAS_TEMPRANA = time(7, 0)
HORA_MAS_TARDE = time(20, 0)


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


class Periodo(models.Model):
    """Periodo académico: solo uno puede estar activo a la vez."""

    nombre = models.CharField(max_length=20, unique=True)
    activo = models.BooleanField(default=False)

    class Meta:
        verbose_name = 'Periodo'
        verbose_name_plural = 'Periodos'
        ordering = ['nombre']

    def __str__(self):
        return self.nombre

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if self.activo:
            self.desactivar_otros()

    def delete(self, *args, **kwargs):
        if self.activo:
            self.activo = False
            self.save(update_fields=['activo'])
        return super().delete(*args, **kwargs)

    def desactivar_otros(self):
        Periodo.objects.exclude(pk=self.pk).filter(activo=True).update(
            activo=False)

    def activar(self):
        """Deja este periodo como el vigente."""
        if not self.activo:
            self.activo = True
            self.save(update_fields=['activo'])

    @classmethod
    def actual(cls):
        """Periodo vigente; si no hay ninguno marcado, el más reciente."""
        return (cls.objects.filter(activo=True).first()
                or cls.objects.order_by('nombre').last())


class Grupo(models.Model):
    """Un grupo es una materia abierta en un periodo, con hora y aula."""

    materia = models.ForeignKey(Materia, on_delete=models.PROTECT,
                                related_name='grupos')
    periodo = models.ForeignKey(Periodo, on_delete=models.PROTECT,
                                related_name='grupos')
    hora_inicio = models.TimeField(default=HORA_MAS_TEMPRANA)
    hora_fin = models.TimeField(default=HORA_MAS_TARDE)
    aula = models.CharField(max_length=20, blank=True, default='')
    cupo = models.PositiveSmallIntegerField(validators=[MinValueValidator(1)])
    num_alumnos = models.PositiveSmallIntegerField(
        default=0, validators=[MinValueValidator(0)]
    )

    class Meta:
        verbose_name = 'Grupo'
        verbose_name_plural = 'Grupos'
        ordering = ['-periodo', 'materia', 'hora_inicio']
        constraints = [
            models.UniqueConstraint(
                fields=['materia', 'periodo', 'hora_inicio', 'hora_fin', 'aula'],
                name='unicidad_grupo_por_materia_periodo_hora_aula'
            ),
        ]

    def clean(self):
        super().clean()
        errores = {}
        if self.num_alumnos > self.cupo:
            errores['num_alumnos'] = 'El número de alumnos no puede exceder el cupo.'
        if not (HORA_MAS_TEMPRANA <= self.hora_inicio
                and self.hora_fin <= HORA_MAS_TARDE):
            errores['hora_inicio'] = (
                f'El horario debe estar entre las 07:00 y las 20:00.')
        if self.hora_fin <= self.hora_inicio:
            errores['hora_fin'] = 'La hora final debe ser posterior a la inicial.'
        if errores:
            raise ValidationError(errores)

    @property
    def lugares_disponibles(self):
        return max(self.cupo - self.num_alumnos, 0)

    @property
    def esta_lleno(self):
        return self.num_alumnos >= self.cupo

    @property
    def horario(self):
        """Horario legible, por ejemplo ``07:00 - 08:30``."""
        return f'{self.hora_inicio:%H:%M} - {self.hora_fin:%H:%M}'

    @property
    def turno_display(self):
        """El turno se deduce de la hora de inicio."""
        return 'Matutino' if self.hora_inicio.hour < 14 else 'Vespertino'

    def se_choca_con(self, otro):
        """True si ambos grupos se imparten al mismo tiempo."""
        return not (self.hora_fin <= otro.hora_inicio
                    or otro.hora_fin <= self.hora_inicio)

    def __str__(self):
        return f'{self.materia} – {self.periodo.nombre} – {self.horario}'


class Calificacion(models.Model):
    """Inscripción de un alumno en un grupo.

    La calificación final no se guarda aquí: es el promedio de las
    calificaciones de sus unidades (ver ``CalificacionUnidad.valor_promedio``).
    """

    alumno = models.ForeignKey('Alumno', on_delete=models.CASCADE,
                               related_name='calificaciones')
    # PROTECT y no CASCADE: borrar un grupo con alumnos no debe borrar en
    # silencio las inscripciones; primero hay que darlas de baja.
    grupo = models.ForeignKey(Grupo, on_delete=models.PROTECT,
                              related_name='calificaciones')
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
    def unidades(self):
        return self.calificaciones_unidad.order_by('numero_unidad')

    @property
    def valor_promedio(self):
        valores = [u.valor for u in self.unidades if u.valor is not None]
        if not valores:
            return None
        return (sum(valores) / Decimal(len(valores))).quantize(Decimal('0.0'))

    @property
    def unidades_completas(self):
        """True cuando ya se capturaron todas las unidades de la materia."""
        return (self.calificaciones_unidad.filter(valor__isnull=False).count()
                == self.grupo.materia.unidades)

    @property
    def es_aprobada(self):
        """True solo con promedio final dentro del rango de aprobado."""
        return (self.valor_promedio is not None
                and self.valor_promedio >= settings.CALIFICACION_APROBADA
                and self.valor_promedio <= settings.CALIFICACION_MAXIMA)

    @property
    def es_reprobada(self):
        valor = self.valor_promedio
        return valor is not None and valor < settings.CALIFICACION_APROBADA

    @property
    def esta_calificada(self):
        return self.valor_promedio is not None


class CalificacionUnidad(models.Model):
    """Calificación de una unidad de la materia.

    La materia define cuántas unidades tiene (``Materia.unidades``) y la
    calificación final es el promedio de las unidades capturadas.
    """

    calificacion = models.ForeignKey(Calificacion, on_delete=models.CASCADE,
                                     related_name='calificaciones_unidad')
    numero_unidad = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(20)]
    )
    valor = models.DecimalField(
        max_digits=5, decimal_places=1, null=True, blank=True,
        validators=[MinValueValidator(Decimal('0')),
                    MaxValueValidator(Decimal('100'))]
    )

    class Meta:
        verbose_name = 'Calificación de unidad'
        verbose_name_plural = 'Calificaciones de unidad'
        ordering = ['calificacion', 'numero_unidad']
        constraints = [
            models.UniqueConstraint(
                fields=['calificacion', 'numero_unidad'],
                name='unicidad_calificacion_numero_unidad'
            ),
        ]

    def __str__(self):
        unidad = f'Unidad {self.numero_unidad}'
        return f'{self.calificacion} · {unidad}'


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
        valores = [c.valor_promedio for c in self.calificaciones.all()
                   if c.valor_promedio is not None]
        if not valores:
            return None
        return (sum(valores) / Decimal(len(valores))).quantize(Decimal('0.0'))

    def carga_academica(self, periodo=None):
        """Inscripciones del alumno en un periodo (el activo si no se indica)."""
        periodo = periodo or Periodo.actual()
        return (self.calificaciones
                .filter(grupo__periodo=periodo)
                .select_related('grupo', 'grupo__materia')
                .prefetch_related('calificaciones_unidad')
                .order_by('grupo__materia__codigo'))

    @property
    def tiene_carga_activa(self):
        """True si ya tiene materias inscritas en el periodo vigente."""
        return self.calificaciones.filter(
            grupo__periodo=Periodo.actual()).exists()

    def ha_cursado(self, materia):
        """True si el alumno ya tiene una inscripción (calificada o no) de la materia."""
        return self.calificaciones.filter(grupo__materia=materia).exists()

    def choca_con_sus_grupos(self, grupos, periodo=None):
        """Devuelve el grupo propio que se cruza con ``grupos``, o None."""
        propios = (self.calificaciones
                   .filter(grupo__periodo=periodo or Periodo.actual())
                   .select_related('grupo'))
        for nuevo in grupos:
            for inscripcion in propios:
                if inscripcion.grupo.se_choca_con(nuevo):
                    return inscripcion.grupo
        return None

    @property
    def materias_aprobadas(self):
        return [c for c in self.calificaciones.all() if c.es_aprobada]

    @property
    def materias_reprobadas(self):
        return [c for c in self.calificaciones.all() if c.es_reprobada]

    @property
    def historial_academico(self):
        """Inscripciones del alumno ordenadas del periodo más reciente al más antiguo."""
        return (self.calificaciones
                .select_related('grupo', 'grupo__materia', 'grupo__periodo')
                .prefetch_related('calificaciones_unidad')
                .order_by('-grupo__periodo__nombre', 'grupo__materia__codigo'))

    @property
    def creditos_acumulados(self):
        return sum(c.grupo.materia.creditos for c in self.materias_aprobadas)

    @property
    def creditos_en_curso(self):
        return sum(c.grupo.materia.creditos for c in self.carga_academica())


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