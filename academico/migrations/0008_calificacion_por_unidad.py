"""Calificación por unidad: la calificación final es el promedio de las unidades.

`Calificacion` pasa a ser solo la inscripción del alumno al grupo y su
calificación final se calcula como el promedio de `CalificacionUnidad`, una
fila por cada unidad declarada en `Materia.unidades`. La escala cambia de 0 a
10 a 0 a 100, con 70 como mínimo aprobado.

Los datos existentes se conservan: por cada inscripción se crean sus filas de
unidad en blanco y, si traía calificación, se reparte en todas las unidades
multiplicada por diez para que el promedio resultante sea el mismo valor en la
escala nueva.
"""

from decimal import Decimal

import django.core.validators
import django.db.models.deletion
from django.db import migrations, models

ESCALA = Decimal('10')


def crea_unidades(apps, schema_editor):
    """Crea una fila de unidad por cada inscripción existente."""
    Calificacion = apps.get_model('academico', 'Calificacion')
    CalificacionUnidad = apps.get_model('academico', 'CalificacionUnidad')

    for calificacion in Calificacion.objects.all().order_by('pk'):
        unidades = calificacion.grupo.materia.unidades
        # La calificación vieja iba de 0 a 10: al pasarla a las unidades el
        # promedio tiene que quedar igual, así que se repite en todas.
        valor = getattr(calificacion, 'valor', None)
        valor_escalado = None if valor is None else valor * ESCALA
        CalificacionUnidad.objects.bulk_create([
            CalificacionUnidad(calificacion_id=calificacion.pk,
                               numero_unidad=numero, valor=valor_escalado)
            for numero in range(1, unidades + 1)
        ])


def reverse_unidades(apps, schema_editor):
    """Deja las calificaciones sin unidades (se revierte el RemoveField)."""
    apps.get_model('academico', 'CalificacionUnidad').objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ('academico', '0007_alter_calificacion_grupo'),
    ]

    operations = [
        migrations.CreateModel(
            name='CalificacionUnidad',
            fields=[
                ('id', models.BigAutoField(auto_created=True,
                                           primary_key=True,
                                           serialize=False,
                                           verbose_name='ID')),
                ('numero_unidad', models.PositiveSmallIntegerField(validators=[
                    django.core.validators.MinValueValidator(1),
                    django.core.validators.MaxValueValidator(20)])),
                ('valor', models.DecimalField(
                    blank=True, decimal_places=1, max_digits=5, null=True,
                    validators=[
                        django.core.validators.MinValueValidator(Decimal('0')),
                        django.core.validators.MaxValueValidator(
                            Decimal('100'))])),
                ('calificacion', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='calificaciones_unidad',
                    to='academico.calificacion')),
            ],
            options={
                'verbose_name': 'Calificación de unidad',
                'verbose_name_plural': 'Calificaciones de unidad',
                'ordering': ['calificacion', 'numero_unidad'],
                'constraints': [models.UniqueConstraint(
                    fields=('calificacion', 'numero_unidad'),
                    name='unicidad_calificacion_numero_unidad')],
            },
        ),
        migrations.RunPython(crea_unidades, reverse_unidades),
        migrations.RemoveField(
            model_name='calificacion',
            name='valor',
        ),
    ]
