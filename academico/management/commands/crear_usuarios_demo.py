"""Crea usuarios de demostración con los tres roles del sistema."""

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.db import transaction

from academico.models import Alumno, Perfil

PASSWORD_COORDINADOR = 'coordinador123'
PASSWORD_ESTUDIANTE = 'alumno123'


class Command(BaseCommand):
    help = ('Crea un usuario coordinador y un usuario por cada alumno, '
            'para poder probar los tres roles del sistema.')

    def add_arguments(self, parser):
        parser.add_argument('--password-coordinador',
                            default=PASSWORD_COORDINADOR)
        parser.add_argument('--password-alumno',
                            default=PASSWORD_ESTUDIANTE)

    @transaction.atomic
    def handle(self, *args, **opciones):
        total = 0
        total += self.crear_coordinador(opciones['password_coordinador'])
        total += self.crear_usuarios_alumno(opciones['password_alumno'])
        self.stdout.write(self.style.SUCCESS(
            f'Listo: {total} usuario(s) listos para iniciar sesión.'))
        self.stdout.write(
            f'  Administrador: usa el superusuario de /admin/ (admin).')
        self.stdout.write(
            f'  Coordinador:  coordinador / {opciones["password_coordinador"]}')
        self.stdout.write(
            f'  Estudiante:    <matrícula> / {opciones["password_alumno"]}')

    def crear_coordinador(self, password):
        usuario, creado = User.objects.get_or_create(
            username='coordinador',
            defaults={'first_name': 'Coordinador', 'is_staff': True},
        )
        Perfil.objects.update_or_create(
            usuario=usuario, defaults={'rol': 'COORDINADOR', 'alumno': None})
        if creado:
            usuario.set_password(password)
            usuario.save(update_fields=['password'])
            self.stdout.write(f'Usuario coordinador creado.')
        else:
            self.stdout.write('El usuario coordinador ya existía.')
        return 1 if creado else 0

    def crear_usuarios_alumno(self, password):
        creados = 0
        for alumno in Alumno.objects.all():
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
                creados += 1
        if creados:
            self.stdout.write(
                f'{creados} usuario(s) de estudiante creado(s).')
        else:
            self.stdout.write('Los usuarios de estudiante ya existían.')
        return creados