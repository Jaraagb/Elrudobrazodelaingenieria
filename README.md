# MiniOS Simulado - Gestión de Accesos

Este repositorio incluye una implementación en Python de un **mini sistema operativo simulado** enfocado en:

- Login / logout de usuarios.
- Gestión de permisos de acceso.
- Administración básica de archivos y carpetas.
- Control de acceso por ACL (lectura, escritura, ejecución).

## Requisitos

- Python 3.10+

## Ejecución

```bash
python access_management_os.py
```

## Usuario inicial

Se crea automáticamente un usuario administrador:

- Usuario: `admin`
- Contraseña: `admin123`

## Comandos principales

- `register <usuario> <password>`
- `login <usuario> <password>`
- `logout`
- `whoami`
- `pwd`
- `mkdir <ruta>`
- `touch <ruta>`
- `ls [ruta]`
- `cd <ruta>`
- `write <archivo> <texto...>`
- `cat <archivo>`
- `grant <ruta> <usuario> <rwx>`
- `help`
- `exit`

## Ejemplo rápido

```text
guest:/$ login admin admin123
admin:/$ mkdir proyectos
admin:/$ touch proyectos/notas.txt
admin:/$ write proyectos/notas.txt hola_mundo
admin:/$ cat proyectos/notas.txt
```
