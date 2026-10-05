"""Deja datos listos para demostrar la inscripción en un periodo nuevo.

Crea el periodo 2026-2 (sin activarlo), las materias MAT103 y MAT104 con sus
grupos, y opcionalmente deja 2026-2 como vigente. Los alumnos que ya tienen
calificaciones en 2026-1 sí pueden inscribirse en estas materias, porque no las
han cursado antes.
"""

from django.core.management.base import BaseCommand
from django.db import transaction

from academico.models import Carrera, Grupo, Materia, Periodo

PERIODO_DEMO = '2026-2'

MATERIAS_DEMO = [
    {
        'codigo': 'MAT103',
        'nombre': 'Cálculo Diferencial',
        'unidades': 5, 'creditos': 5,
        'grupos': [
            {'turno': 'MAT', 'horario': 'L-V 08:00-09:30', 'aula': 'A-101', 'cupo': 30},
            {'turno': 'VES', 'horario': 'L-V 18:00-19:30', 'aula': 'A-204', 'cupo': 25},
        ],
    },
    {
        'codigo': 'MAT104',
        'nombre': 'Estructuras de Datos',
        'unidades': 5, 'creditos': 5,
        'grupos': [
            {'turno': 'MAT', 'horario': 'M-J 10:00-11:30', 'aula': 'B-3', 'cupo': 28},
        ],
    },
]


class Command(BaseCommand):
    help = ('Crea el periodo 2026-2 con las materias MAT103 y MAT104 para '
            'practicar la inscripción de alumnos.')

    def add_arguments(self, parser):
        parser.add_argument(
            '--activar', action='store_true',
            help='Deja 2026-2 como periodo vigente (no se activa por defecto).')
        parser.add_argument(
            '--carrera', default='ISC',
            help='Código de la carrera a la que se asignan las materias.')

    @transaction.atomic
    def handle(self, *args, **opciones):
        carrera = self._carrera(opciones['carrera'])

        periodo, creado = Periodo.objects.get_or_create(
            nombre=PERIODO_DEMO, defaults={'activo': False})
        self.stdout.write(
            f'Periodo {periodo}: {"creado" if creado else "ya existía"}.')
        for grupo in self._grupos(carrera, periodo):
            self.stdout.write(f'  {grupo}')

        if opciones['activar']:
            periodo.activar()
            self.stdout.write(self.style.WARNING(
                f'Ahora el periodo vigente es {Periodo.actual()}.'))
        else:
            actual = Periodo.actual()
            self.stdout.write(
                f'Periodo vigente sin cambios: {actual or "ninguno"}.')
            self.stdout.write(
                'Para cambiarlo usa:  manage.py shell -> '
                'from academico.models import Periodo; '
                f'Periodo.objects.get(nombre="{PERIODO_DEMO}").activar()')
            self.stdout.write(
                'o la pantalla Periodos desde el sistema.')

        self.stdout.write(self.style.SUCCESS(
            f'Listo: los alumnos que no cursaron MAT103/MAT104 ya pueden '
            f'inscribirse en {PERIODO_DEMO}.'))

    def _carrera(self, codigo):
        carrera = Carrera.objects.filter(pk=codigo).first()
        if carrera is None:
            carrera = Carrera.objects.first()
        if carrera is None:
            self.stderr.write(self.style.ERROR(
                'No hay carreras registradas: crea una antes de sembrar.'))
            raise SystemExit(1)
        return carrera

    def _grupos(self, carrera, periodo):
        for datos in MATERIAS_DEMO:
            materia, _ = Materia.objects.get_or_create(
                codigo=datos['codigo'],
                defaults={
                    'nombre': datos['nombre'],
                    'unidades': datos['unidades'],
                    'creditos': datos['creditos'],
                    'carrera': carrera,
                },
            )
            for grupo in datos['grupos']:
                grupo, creado = Grupo.objects.get_or_create(
                    materia=materia,
                    periodo=periodo,
                    horario=grupo['horario'],
                    aula=grupo['aula'],
                    defaults={
                        'turno': grupo['turno'],
                        'cupo': grupo['cupo'],
                        'num_alumnos': 0,
                    },
                )
                estado = 'creado' if creado else 'ya existía'
                yield f'{grupo} ({estado})'
