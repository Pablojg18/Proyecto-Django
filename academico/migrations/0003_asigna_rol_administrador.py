from django.db import migrations


def asigna_rol_administrador(apps, schema_editor):
    """Los superusuarios existentes quedan como administradores del sistema."""
    Perfil = apps.get_model('academico', 'Perfil')
    User = apps.get_model('auth', 'User')
    for usuario in User.objects.filter(is_superuser=True):
        Perfil.objects.get_or_create(
            usuario=usuario, defaults={'rol': 'ADMINISTRADOR'})


class Migration(migrations.Migration):

    dependencies = [
        ('academico', '0002_perfil'),
    ]

    operations = [
        migrations.RunPython(asigna_rol_administrador,
                             migrations.RunPython.noop),
    ]