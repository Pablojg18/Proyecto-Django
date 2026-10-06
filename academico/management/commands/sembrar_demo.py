"""Deja datos de demostración para probar el sistema completo.

Crea un usuario coordinador, un usuario por cada alumno existente y abre un
periodo nuevo con dos materias y sus grupos. Es idempotente: se puede volver
a ejecutar sin duplicar nada.

    manage.py sembrar_demo --activar
"""

from datetime import time

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.db import transaction

from academico.models import (Alumno, Carrera, Grupo, Materia, Perfil,
                              Periodo)

PERIODO_DEMO = '2026-2'
PASSWORD_COORDINADOR = 'coordinador123'
PASSWORD_ESTUDIANTE = 'alumno123'

MATERIAS_DEMO = [
    {
        'codigo': 'MAT103',
        'nombre': 'Cálculo Diferencial',
        'unidades': 5, 'creditos': 5,
        'grupos': [
            {'inicio': time(8, 0), 'fin': time(9, 30), 'aula': 'A-101',
             'cupo': 30},
            {'inicio': time(18, 0), 'fin': time(19, 30), 'aula': 'A-204',
             'cupo': 25},
        ],
    },
    {
        'codigo': 'MAT104',
        'nombre': 'Estructuras de Datos',
        'unidades': 5, 'creditos': 5,
        'grupos': [
            {'inicio': time(10, 0), 'fin': time(11, 30), 'aula': 'B-3',
             'cupo': 28},
        ],
    },
]


class Command(BaseCommand):
    help = ('Crea usuarios de los tres roles y un periodo nuevo con materias y '
            'grupos para poder probar el sistema de principio a fin.')

    def add_arguments(self, parser):
        parser.add_argument(
            '--activar', action='store_true',
            help=f'Deja {PERIODO_DEMO} como periodo vigente (no se activa por '
                 'defecto).')
        parser.add_argument('--carrera', default='ISC',
                            help='Código de la carrera de las materias nuevas.')
        parser.add_argument('--password-coordinador',
                            default=PASSWORD_COORDINADOR)
        parser.add_argument('--password-alumno', default=PASSWORD_ESTUDIANTE)

    @transaction.atomic
    def handle(self, *args, **opciones):
        if not Alumno.objects.exists():
            self.stderr.write(self.style.ERROR(
                'No hay alumnos registrados: da de alta al menos uno desde el '
                'sistema antes de sembrar los datos de demostración.'))
            raise SystemExit(1)

        self._usuarios(opciones)
        self._periodo(opciones)

        self.stdout.write(self.style.SUCCESS(
            'Listo. Para entrar: el superusuario de /admin/ como '
            'administrador; "coordinador" como coordinador; y cualquier '
            'matrícula como estudiante.'))

    # --- Usuarios ---------------------------------------------------------

    def _usuarios(self, opciones):
        self.stdout.write(
            f'Coordinador: {self._coordinador(opciones["password_coordinador"])}')
        for alumno in Alumno.objects.all():
            self._usuario_alumno(alumno, opciones['password_alumno'])

    def _coordinador(self, password):
        usuario, creado = User.objects.get_or_create(
            username='coordinador',
            defaults={'first_name': 'Coordinador', 'is_staff': True},
        )
        Perfil.objects.update_or_create(
            usuario=usuario, defaults={'rol': 'COORDINADOR', 'alumno': None})
        if creado:
            usuario.set_password(password)
            usuario.save(update_fields=['password'])
        estado = 'creado' if creado else 'ya existía'
        return f'"coordinador" {estado}'

    def _usuario_alumno(self, alumno, password):
        usuario, creado = User.objects.get_or_create(
            username=alumno.matricula,
            defaults={'first_name': alumno.nombre},
        )
        Perfil.objects.update_or_create(
            usuario=usuario,
            defaults={'rol': 'ESTUDIANTE', 'alumno': alumno},
        )
        if creado:
            usuario.set_password(password)
            usuario.save(update_fields=['password'])

    # --- Periodo con materias y grupos ------------------------------------

    def _periodo(self, opciones):
        carrera = (Carrera.objects.filter(pk=opciones['carrera']).first()
                   or Carrera.objects.first())
        if carrera is None:
            self.stderr.write(self.style.ERROR(
                'No hay carreras registradas: crea una antes de sembrar.'))
            raise SystemExit(1)

        periodo, creado = Periodo.objects.get_or_create(
            nombre=PERIODO_DEMO, defaults={'activo': False})
        self.stdout.write(
            f'Periodo {periodo}: {"creado" if creado else "ya existía"}.')

        for datos in MATERIAS_DEMO:
            materia, _ = Materia.objects.get_or_create(
                codigo=datos['codigo'],
                defaults={'nombre': datos['nombre'],
                          'unidades': datos['unidades'],
                          'creditos': datos['creditos'],
                          'carrera': carrera},
            )
            for grupo in datos['grupos']:
                grupo, nuevo = Grupo.objects.get_or_create(
                    materia=materia, periodo=periodo,
                    hora_inicio=grupo['inicio'], hora_fin=grupo['fin'],
                    aula=grupo['aula'],
                    defaults={'cupo': grupo['cupo'], 'num_alumnos': 0},
                )
                estado = 'creado' if nuevo else 'ya existía'
                self.stdout.write(f'  {grupo} ({estado})')

        if opciones['activar']:
            periodo.activar()
        self.stdout.write(f'Periodo vigente: {Periodo.actual()}.')
