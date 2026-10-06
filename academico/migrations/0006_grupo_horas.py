"""Horarios de grupo como horas: `hora_inicio` / `hora_fin` entre 07:00 y 20:00.

Sustituye el texto libre `horario` (por ejemplo ``L-V 08:00-09:30``) y el campo
`turno`, que ya no hacía falta porque el turno se deduce de la hora de inicio.
Los datos existentes se conservan: se lee la hora del texto y se guarda en las
columnas nuevas.
"""

import re
from datetime import time

from django.db import migrations, models

TABLA_GRUPO = 'academico_grupo'
UNICO_VIEJO = 'unicidad_grupo_por_materia_periodo_horario_aula'
UNICO_NUEVO = 'unicidad_grupo_por_materia_periodo_hora_aula'
INDEX_MATERIA = 'academico_grupo_materia_id_horas'

HORAS = re.compile(r'(\d{1,2}):(\d{2})')
INICIO_POR_DEFECTO = time(7, 0)
FIN_POR_DEFECTO = time(8, 0)


def _hora(encontrada, por_defecto):
    """Convierte el texto ``'08:00'`` en ``time(8, 0)``."""
    if not encontrada:
        return por_defecto
    horas, minutos = encontrada
    return time(min(int(horas), 20), min(int(minutos), 59))


def convierte_horarios(apps, schema_editor):
    """Pasa el texto `horario` a las columnas de hora."""
    Grupo = apps.get_model('academico', 'Grupo')
    for grupo in Grupo.objects.all().order_by():
        encontrados = HORAS.findall(grupo.horario or '')
        inicio = _hora(encontrados[0] if len(encontrados) > 0 else None,
                       INICIO_POR_DEFECTO)
        fin = _hora(encontrados[1] if len(encontrados) > 1 else None,
                    FIN_POR_DEFECTO)
        if fin <= inicio:
            # Si el texto no se entiende (o la hora final no es posterior) se
            # deja el grupo en el bloque matutino en vez de inventar un horario.
            inicio, fin = INICIO_POR_DEFECTO, FIN_POR_DEFECTO
        Grupo.objects.filter(pk=grupo.pk).update(hora_inicio=inicio,
                                                 hora_fin=fin)


def _existe_indice(schema_editor, nombre):
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(
            'SELECT COUNT(*) FROM information_schema.STATISTICS '
            'WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = %s '
            'AND INDEX_NAME = %s',
            [TABLA_GRUPO, nombre],
        )
        return cursor.fetchone()[0] > 0


def _indice_de_materia(schema_editor):
    """True si algún índice (salvo el único viejo) empieza por `materia_id`."""
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(
            'SELECT COUNT(*) FROM information_schema.STATISTICS '
            'WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = %s '
            "AND COLUMN_NAME = 'materia_id' AND SEQ_IN_INDEX = 1 "
            'AND INDEX_NAME <> %s',
            [TABLA_GRUPO, UNICO_VIEJO],
        )
        return cursor.fetchone()[0] > 0


def cambia_restriccion(apps, schema_editor):
    """Cambia la unicidad de (materia, periodo, horario, aula) a las horas.

    Va con SQL directo porque en MariaDB la llave foránea de `materia_id` usa el
    índice único viejo como único índice: si se suelta sin más, MySQL rechaza la
    tabla. Se crea un índice propio, se suelta el viejo y al final se elimina el
    provisional, igual que en la migración 0005.
    """
    grupo = schema_editor.quote_name(TABLA_GRUPO)
    provisional = False

    if _existe_indice(schema_editor, UNICO_VIEJO) \
            and not _indice_de_materia(schema_editor):
        schema_editor.execute(
            f'CREATE INDEX {schema_editor.quote_name(INDEX_MATERIA)} '
            f'ON {grupo} (`materia_id`)')
        provisional = True

    if _existe_indice(schema_editor, UNICO_VIEJO):
        schema_editor.execute(
            f'ALTER TABLE {grupo} DROP INDEX '
            f'{schema_editor.quote_name(UNICO_VIEJO)}')

    if not _existe_indice(schema_editor, UNICO_NUEVO):
        schema_editor.execute(
            f'ALTER TABLE {grupo} ADD CONSTRAINT '
            f'{schema_editor.quote_name(UNICO_NUEVO)} '
            'UNIQUE (`materia_id`, `periodo_id`, `hora_inicio`, `hora_fin`, '
            '`aula`)')

    if provisional and _existe_indice(schema_editor, INDEX_MATERIA):
        schema_editor.execute(
            f'ALTER TABLE {grupo} DROP INDEX '
            f'{schema_editor.quote_name(INDEX_MATERIA)}')


class Migration(migrations.Migration):

    dependencies = [
        ('academico', '0005_periodo'),
    ]

    operations = [
        migrations.AddField(
            model_name='grupo',
            name='hora_inicio',
            field=models.TimeField(null=True),
        ),
        migrations.AddField(
            model_name='grupo',
            name='hora_fin',
            field=models.TimeField(null=True),
        ),
        migrations.RunPython(convierte_horarios, migrations.RunPython.noop),
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunPython(cambia_restriccion,
                                     migrations.RunPython.noop),
            ],
            state_operations=[
                migrations.RemoveConstraint(
                    model_name='grupo',
                    name=UNICO_VIEJO,
                ),
                migrations.AddConstraint(
                    model_name='grupo',
                    constraint=models.UniqueConstraint(
                        fields=('materia', 'periodo', 'hora_inicio',
                                'hora_fin', 'aula'),
                        name=UNICO_NUEVO,
                    ),
                ),
            ],
        ),
        migrations.RemoveField(
            model_name='grupo',
            name='turno',
        ),
        migrations.RemoveField(
            model_name='grupo',
            name='horario',
        ),
        migrations.AlterField(
            model_name='grupo',
            name='hora_inicio',
            field=models.TimeField(default=time(7, 0)),
        ),
        migrations.AlterField(
            model_name='grupo',
            name='hora_fin',
            field=models.TimeField(default=time(20, 0)),
        ),
        migrations.AlterModelOptions(
            name='grupo',
            options={
                'ordering': ['-periodo', 'materia', 'hora_inicio'],
                'verbose_name': 'Grupo',
                'verbose_name_plural': 'Grupos',
            },
        ),
    ]
