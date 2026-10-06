# Proyecto escolar Django

Sistema de control escolar: catálogo de carreras, materias, grupos y periodos,
inscripción de materias por alumno, carga académica y cardex con calificación
por unidad.

## Requisitos

- Python 3.13 o superior
- MariaDB o MySQL 8 escuchando en `127.0.0.1:3307` (puedes cambiarlo en
  `escolar_project/settings.py`)

## Instalación

```bash
python -m venv entorno
.\entorno\Scripts\python.exe -m pip install -r requirements.txt
```

En `escolar_project/settings.py`, `DATABASES` debe apuntar a tu servidor con
las credenciales correctas y la base `escolar` creada:

```sql
CREATE DATABASE escolar CHARACTER SET utf8mb4;
```

## Puesta en marcha

```bash
.\entorno\Scripts\python.exe manage.py migrate
.\entorno\Scripts\python.exe manage.py createsuperuser
.\entorno\Scripts\python.exe manage.py runserver
```

Abre `http://127.0.0.1:8000/`.

## Datos de demostración (opcional)

Con al menos un alumno registrado, el siguiente comando crea el usuario
`coordinador`, un usuario por alumno (con la contraseña `alumno123`) y un
periodo nuevo con dos materias y tres grupos. Es idempotente:

```bash
.\entorno\Scripts\python.exe manage.py sembrar_demo --activar
```

## Roles

| Rol | Puede hacer |
|---|---|
| Administrador | Todo, con acceso a `/admin/`. |
| Coordinador | Catálogos, inscripción, carga y cardex de cualquier alumno. |
| Estudiante | Su inscripción, su carga académica y su cardex (solo lectura). |

## Estructura

| Ruta | Contenido |
|---|---|
| `academico/models.py` | Alumno, Carrera, Materia, Grupo, Periodo, Calificacion y sus unidades. |
| `academico/views/` | Vistas por responsabilidad: `alumno`, `catalogos`, `cuentas`, `usuarios`. |
| `academico/templates/academico/` | Plantillas HTML; los listados usan DataTables. |
| `academico/tests.py` | 114 pruebas del sistema. |

## Pruebas

```bash
.\entorno\Scripts\python.exe manage.py test
```
