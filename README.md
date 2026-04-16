# MiniOS Simulado - Gestión de Recursos y Planificación

Este proyecto implementa un **mini sistema operativo educativo** en Python para simular:

- Gestión de procesos (creación, estados y finalización).
- Planificación con **prioridades dinámicas + Round Robin**.
- Mecanismo de **aging** para evitar inanición.
- Gestión de recursos:
  - CPU (por el planificador)
  - Memoria RAM simulada
  - E/S con cola **FIFO**
- Interacción por línea de comandos (CLI).

## Requisitos

- Python 3.10+

## Ejecutar

```bash
python access_management_os.py
```

## Parámetros por defecto de la simulación

- Quantum Round Robin: `2`
- Aging threshold: `4` ticks
- Memoria total: `512`
- Dispositivos de E/S: `1`

## Estados de proceso

- `Nuevo`
- `Listo`
- `Ejecutando`
- `Bloqueado`
- `Terminado`

## Comandos CLI

- `create <nombre> <prioridad> <cpu_total> <memoria> [io_freq io_duracion]`
- `tick`
- `run <n>`
- `status`
- `queues`
- `help`
- `exit`

## Ejemplo rápido

```text
os> create editor 3 6 100
os> create backup 3 6 100
os> create reporte 5 4 150 2 2
os> queues
os> run 8
os> status
```

## Ejemplo de prueba por consola (no interactivo)

Puedes ejecutar un flujo automatizado con `printf`:

```bash
printf "create p1 3 6 100\ncreate p2 3 6 100\ncreate p3 5 4 120 2 2\nqueues\nrun 10\nstatus\nexit\n" | python access_management_os.py
```
