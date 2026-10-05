from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion

TABLA_GRUPO = 'academico_grupo'
TABLA_PERIODO = 'academico_periodo'
FK_POR_DEFECTO = 'academico_grupo_periodo_nuevo_id_f7af4c63_fk_academico'
FK_NUEVA = 'academico_grupo_periodo_fk_periodo'
UNICO_GRUPO = 'unicidad_grupo_por_materia_periodo_horario_aula'
INDEX_MATERIA = 'academico_grupo_materia_id_provisional'


def _contar(schema_editor, sql, nombre):
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(sql, [TABLA_GRUPO, nombre])
        return cursor.fetchone()[0] > 0


def _tiene_constraint(schema_editor, nombre):
    return _contar(
        schema_editor,
        'SELECT COUNT(*) FROM information_schema.TABLE_CONSTRAINTS '
        'WHERE CONSTRAINT_SCHEMA = DATABASE() AND TABLE_NAME = %s '
        'AND CONSTRAINT_NAME = %s',
        nombre,
    )


def _tiene_columna(schema_editor, nombre):
    return _contar(
        schema_editor,
        'SELECT COUNT(*) FROM information_schema.COLUMNS '
        'WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = %s '
        'AND COLUMN_NAME = %s',
        nombre,
    )


def _tiene_indice(schema_editor, nombre):
    return _contar(
        schema_editor,
        'SELECT COUNT(*) FROM information_schema.STATISTICS '
        'WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = %s '
        'AND INDEX_NAME = %s',
        nombre,
    )


def _indice_por_materia(schema_editor):
    """True si ya hay algún índice que empiece por `materia_id`."""
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(
            'SELECT COUNT(*) FROM information_schema.STATISTICS '
            'WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = %s '
            "AND COLUMN_NAME = 'materia_id' AND SEQ_IN_INDEX = 1 "
            'AND INDEX_NAME <> %s',
            [TABLA_GRUPO, UNICO_GRUPO],
        )
        return cursor.fetchone()[0] > 0


def crea_periodos(apps, schema_editor):
    """Crea un registro de Periodo por cada texto usado en Grupo.periodo.

    Se usa get_or_create para que la migración pueda reintentarse: en MariaDB
    las sentencias DDL cierran la transacción y pueden dejar estos datos ya
    insertados si una operación posterior falla.
    """
    Grupo = apps.get_model('academico', 'Grupo')
    Periodo = apps.get_model('academico', 'Periodo')

    # Ojo: sin `order_by()` el orden del Meta de Grupo se convierte en un JOIN
    # con materia y `distinct()` devolvería un renglón por grupo, no por
    # periodo. Por eso los repetidos se filtran a mano.
    nombres = []
    for valor in Grupo.objects.values_list('periodo', flat=True).order_by():
        if valor and valor not in nombres:
            nombres.append(valor)

    if settings.PERIODO_ACTUAL and settings.PERIODO_ACTUAL not in nombres:
        nombres.append(settings.PERIODO_ACTUAL)

    inicial = settings.PERIODO_ACTUAL or (nombres[-1] if nombres else None)
    for nombre in nombres:
        Periodo.objects.get_or_create(
            nombre=nombre,
            defaults={'activo': nombre == inicial},
        )


def traslada_grupos(apps, schema_editor):
    """Pasa el texto del periodo de cada grupo a la nueva llave foránea."""
    Grupo = apps.get_model('academico', 'Grupo')
    Periodo = apps.get_model('academico', 'Periodo')

    periodos = {p.nombre: p.pk for p in Periodo.objects.all()}
    for grupo in Grupo.objects.all():
        Grupo.objects.filter(pk=grupo.pk).update(
            periodo_nuevo_id=periodos[grupo.periodo])


def finaliza_periodo(apps, schema_editor):
    """Deja `academico_grupo.periodo_id` como la columna definitiva.

    Se hace con SQL directo porque en MariaDB el orden automático de Django
    (borrar la columna de texto, renombrar y volverla NOT NULL) falla: la
    llave foránea sigue apuntando al nombre viejo de la columna y MySQL
    rechaza cualquier modificación de la tabla. Aquí se suelta la llave, se
    renombra la columna y se vuelve a crear todo con su nombre final.
    """
    grupo = schema_editor.quote_name(TABLA_GRUPO)
    periodo = schema_editor.quote_name(TABLA_PERIODO)
    texto = schema_editor.quote_name('periodo')
    fk_vieja = schema_editor.quote_name('periodo_nuevo_id')
    fk_final = schema_editor.quote_name('periodo_id')

    for llave in (FK_POR_DEFECTO, FK_NUEVA):
        if _tiene_constraint(schema_editor, llave):
            schema_editor.execute(
                f'ALTER TABLE {grupo} DROP FOREIGN KEY '
                f'{schema_editor.quote_name(llave)}')

    # La llave foránea de materia usa el índice único (su primera columna es
    # materia_id), así que MariaDB no deja borrarlo todavía. Se crea un
    # índice propio, se suelta el único y al final se elimina el provisional.
    indice_provisional = False
    if _tiene_indice(schema_editor, UNICO_GRUPO) and not _indice_por_materia(schema_editor):
        schema_editor.execute(
            f'CREATE INDEX {schema_editor.quote_name(INDEX_MATERIA)} '
            f'ON {grupo} (`materia_id`)')
        indice_provisional = True

    if _tiene_indice(schema_editor, UNICO_GRUPO):
        schema_editor.execute(
            f'ALTER TABLE {grupo} DROP INDEX '
            f'{schema_editor.quote_name(UNICO_GRUPO)}')

    if _tiene_columna(schema_editor, 'periodo'):
        schema_editor.execute(f'ALTER TABLE {grupo} DROP COLUMN {texto}')

    if _tiene_columna(schema_editor, 'periodo_nuevo_id'):
        schema_editor.execute(
            f'ALTER TABLE {grupo} RENAME COLUMN {fk_vieja} TO {fk_final}')

    schema_editor.execute(
        f'ALTER TABLE {grupo} MODIFY COLUMN {fk_final} bigint NOT NULL')

    if not _tiene_indice(schema_editor, UNICO_GRUPO):
        schema_editor.execute(
            f'ALTER TABLE {grupo} ADD CONSTRAINT '
            f'{schema_editor.quote_name(UNICO_GRUPO)} '
            'UNIQUE (`materia_id`, `periodo_id`, `horario`, `aula`)')

    schema_editor.execute(
        f'ALTER TABLE {grupo} ADD CONSTRAINT '
        f'{schema_editor.quote_name(FK_NUEVA)} '
        f'FOREIGN KEY (`periodo_id`) REFERENCES {periodo} (`id`)')

    if indice_provisional:
        schema_editor.execute(
            f'ALTER TABLE {grupo} DROP INDEX '
            f'{schema_editor.quote_name(INDEX_MATERIA)}')


class Migration(migrations.Migration):

    dependencies = [
        ('academico', '0004_alter_perfil_alumno'),
    ]

    operations = [
        migrations.CreateModel(
            name='Periodo',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True,
                                           serialize=False, verbose_name='ID')),
                ('nombre', models.CharField(max_length=20, unique=True)),
                ('activo', models.BooleanField(default=False)),
            ],
            options={
                'verbose_name': 'Periodo',
                'verbose_name_plural': 'Periodos',
                'ordering': ['nombre'],
            },
        ),
        migrations.RunPython(crea_periodos, migrations.RunPython.noop),
        migrations.AddField(
            model_name='grupo',
            name='periodo_nuevo',
            field=models.ForeignKey(
                null=True, on_delete=django.db.models.deletion.PROTECT,
                related_name='grupos', to='academico.periodo'),
        ),
        migrations.RunPython(traslada_grupos, migrations.RunPython.noop),
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunPython(finaliza_periodo, migrations.RunPython.noop),
            ],
            state_operations=[
                migrations.RemoveField(
                    model_name='grupo',
                    name='periodo',
                ),
                migrations.RenameField(
                    model_name='grupo',
                    old_name='periodo_nuevo',
                    new_name='periodo',
                ),
                migrations.AlterField(
                    model_name='grupo',
                    name='periodo',
                    field=models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name='grupos', to='academico.periodo'),
                ),
                migrations.AlterModelOptions(
                    name='grupo',
                    options={
                        'ordering': ['-periodo', 'materia'],
                        'verbose_name': 'Grupo',
                        'verbose_name_plural': 'Grupos',
                    },
                ),
            ],
        ),
    ]
