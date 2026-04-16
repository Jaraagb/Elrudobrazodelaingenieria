from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Deque, Dict, List, Optional


class ProcessState(str, Enum):
    NEW = "Nuevo"
    READY = "Listo"
    RUNNING = "Ejecutando"
    BLOCKED = "Bloqueado"
    TERMINATED = "Terminado"


@dataclass
class Process:
    pid: int
    name: str
    priority: int
    total_cpu_time: int
    memory_required: int
    io_frequency: int = 0
    io_duration: int = 0
    state: ProcessState = ProcessState.NEW
    cpu_used: int = 0
    waiting_ticks: int = 0
    blocked_ticks_left: int = 0
    io_counter: int = 0

    def short(self) -> str:
        return (
            f"PID={self.pid} {self.name} | prio={self.priority} | "
            f"cpu={self.cpu_used}/{self.total_cpu_time} | mem={self.memory_required} | {self.state.value}"
        )


@dataclass
class IORequest:
    pid: int
    duration: int


class ResourceManager:
    def __init__(self, total_memory: int = 1024, io_devices: int = 1) -> None:
        self.total_memory = total_memory
        self.used_memory = 0
        self.io_devices = io_devices
        self.io_busy = 0
        self.memory_allocations: Dict[int, int] = {}
        self.io_wait_queue: Deque[IORequest] = deque()

    @property
    def free_memory(self) -> int:
        return self.total_memory - self.used_memory

    def allocate_memory(self, pid: int, amount: int) -> bool:
        if amount <= self.free_memory:
            self.used_memory += amount
            self.memory_allocations[pid] = amount
            return True
        return False

    def release_memory(self, pid: int) -> None:
        amount = self.memory_allocations.pop(pid, 0)
        self.used_memory = max(0, self.used_memory - amount)

    def request_io(self, pid: int, duration: int) -> bool:
        if self.io_busy < self.io_devices:
            self.io_busy += 1
            return True
        self.io_wait_queue.append(IORequest(pid=pid, duration=duration))
        return False

    def release_io_slot(self) -> Optional[IORequest]:
        self.io_busy = max(0, self.io_busy - 1)
        if self.io_wait_queue and self.io_busy < self.io_devices:
            self.io_busy += 1
            return self.io_wait_queue.popleft()
        return None


class ProcessScheduler:
    def __init__(self, quantum: int = 2, aging_threshold: int = 4, max_priority: int = 10) -> None:
        self.quantum = quantum
        self.aging_threshold = aging_threshold
        self.max_priority = max_priority
        self._queues: Dict[int, Deque[int]] = {}

    def enqueue(self, pid: int, priority: int) -> None:
        self._queues.setdefault(priority, deque()).append(pid)

    def remove(self, pid: int) -> None:
        for q in self._queues.values():
            try:
                q.remove(pid)
                return
            except ValueError:
                pass

    def pop_next(self) -> Optional[int]:
        for prio in sorted(self._queues.keys(), reverse=True):
            q = self._queues[prio]
            if q:
                return q.popleft()
        return None

    def snapshot(self) -> Dict[int, List[int]]:
        return {p: list(q) for p, q in sorted(self._queues.items(), reverse=True) if q}


class MiniOS:
    def __init__(self, quantum: int = 2, aging_threshold: int = 4, total_memory: int = 1024, io_devices: int = 1) -> None:
        self.scheduler = ProcessScheduler(quantum=quantum, aging_threshold=aging_threshold)
        self.resources = ResourceManager(total_memory=total_memory, io_devices=io_devices)
        self.processes: Dict[int, Process] = {}
        self.next_pid = 1
        self.clock = 0

    def create_process(
        self,
        name: str,
        priority: int,
        total_cpu_time: int,
        memory_required: int,
        io_frequency: int = 0,
        io_duration: int = 0,
    ) -> Process:
        if priority < 1:
            raise ValueError("La prioridad debe ser >= 1")
        if total_cpu_time < 1:
            raise ValueError("El tiempo total de CPU debe ser >= 1")
        if memory_required < 1:
            raise ValueError("La memoria debe ser >= 1")

        pid = self.next_pid
        self.next_pid += 1
        proc = Process(
            pid=pid,
            name=name,
            priority=priority,
            total_cpu_time=total_cpu_time,
            memory_required=memory_required,
            io_frequency=io_frequency,
            io_duration=io_duration,
        )

        if self.resources.allocate_memory(pid, memory_required):
            proc.state = ProcessState.READY
            self.scheduler.enqueue(pid, proc.priority)
        else:
            proc.state = ProcessState.BLOCKED
            proc.blocked_ticks_left = -1  # espera indefinida por memoria

        self.processes[pid] = proc
        return proc

    def _apply_aging(self) -> None:
        for proc in self.processes.values():
            if proc.state == ProcessState.READY:
                proc.waiting_ticks += 1
                if proc.waiting_ticks >= self.scheduler.aging_threshold:
                    old_priority = proc.priority
                    proc.priority = min(proc.priority + 1, self.scheduler.max_priority)
                    proc.waiting_ticks = 0
                    if proc.priority != old_priority:
                        self.scheduler.remove(proc.pid)
                        self.scheduler.enqueue(proc.pid, proc.priority)

    def _try_unblock_memory_waiters(self) -> None:
        for proc in self.processes.values():
            if proc.state == ProcessState.BLOCKED and proc.blocked_ticks_left == -1:
                if self.resources.allocate_memory(proc.pid, proc.memory_required):
                    proc.state = ProcessState.READY
                    self.scheduler.enqueue(proc.pid, proc.priority)

    def _progress_blocked(self) -> None:
        finished_io: List[int] = []
        for proc in self.processes.values():
            if proc.state == ProcessState.BLOCKED and proc.blocked_ticks_left > 0:
                proc.blocked_ticks_left -= 1
                if proc.blocked_ticks_left == 0:
                    finished_io.append(proc.pid)

        for pid in finished_io:
            proc = self.processes[pid]
            proc.state = ProcessState.READY
            self.scheduler.enqueue(pid, proc.priority)
            next_io_waiter = self.resources.release_io_slot()
            if next_io_waiter:
                queued_proc = self.processes[next_io_waiter.pid]
                queued_proc.state = ProcessState.BLOCKED
                queued_proc.blocked_ticks_left = next_io_waiter.duration

    def tick(self) -> str:
        self.clock += 1
        self._progress_blocked()
        self._try_unblock_memory_waiters()
        self._apply_aging()

        pid = self.scheduler.pop_next()
        if pid is None:
            return f"[t={self.clock}] CPU inactiva"

        proc = self.processes[pid]
        proc.state = ProcessState.RUNNING
        proc.waiting_ticks = 0

        used_in_slice = 0
        io_triggered = False

        while used_in_slice < self.scheduler.quantum:
            proc.cpu_used += 1
            proc.io_counter += 1
            used_in_slice += 1

            if proc.io_frequency > 0 and proc.io_duration > 0 and proc.io_counter >= proc.io_frequency:
                proc.io_counter = 0
                io_triggered = True
                break

            if proc.cpu_used >= proc.total_cpu_time:
                break

        if proc.cpu_used >= proc.total_cpu_time:
            proc.state = ProcessState.TERMINATED
            self.resources.release_memory(proc.pid)
            return f"[t={self.clock}] Ejecutado PID {proc.pid} ({proc.name}) -> TERMINADO"

        if io_triggered:
            if self.resources.request_io(proc.pid, proc.io_duration):
                proc.state = ProcessState.BLOCKED
                proc.blocked_ticks_left = proc.io_duration
                return (
                    f"[t={self.clock}] Ejecutado PID {proc.pid} ({proc.name}) -> BLOQUEADO "
                    f"por E/S {proc.io_duration} ticks"
                )

            proc.state = ProcessState.BLOCKED
            proc.blocked_ticks_left = 0  # esperando turno de dispositivo
            return f"[t={self.clock}] Ejecutado PID {proc.pid} ({proc.name}) -> en cola FIFO de E/S"

        proc.state = ProcessState.READY
        self.scheduler.enqueue(proc.pid, proc.priority)
        return (
            f"[t={self.clock}] Ejecutado PID {proc.pid} ({proc.name}) quantum={used_in_slice} "
            f"-> vuelve a LISTO"
        )

    def run(self, ticks: int) -> List[str]:
        if ticks < 1:
            raise ValueError("Ticks debe ser >= 1")
        return [self.tick() for _ in range(ticks)]

    def system_status(self) -> str:
        lines = [
            f"Reloj: {self.clock}",
            f"Memoria: {self.resources.used_memory}/{self.resources.total_memory} (libre={self.resources.free_memory})",
            f"E/S ocupados: {self.resources.io_busy}/{self.resources.io_devices}",
            f"Cola E/S FIFO: {[req.pid for req in self.resources.io_wait_queue] or 'vacía'}",
            "Procesos:",
        ]
        for pid in sorted(self.processes):
            lines.append(f"  - {self.processes[pid].short()}")
        return "\n".join(lines)

    def ready_queues(self) -> str:
        snap = self.scheduler.snapshot()
        if not snap:
            return "Colas de listos vacías"
        return "\n".join([f"Prioridad {prio}: {pids}" for prio, pids in snap.items()])


HELP_TEXT = (
    "Comandos:\n"
    "  create <nombre> <prioridad> <cpu_total> <memoria> [io_freq io_duracion]\n"
    "  tick                     # ejecuta 1 ciclo de planificación\n"
    "  run <n>                  # ejecuta n ticks\n"
    "  status                   # muestra estado global del sistema\n"
    "  queues                   # muestra colas READY por prioridad\n"
    "  help\n"
    "  exit"
)


def run_cli() -> None:
    os_sim = MiniOS(quantum=2, aging_threshold=4, total_memory=512, io_devices=1)
    print("MiniOS Simulado - Planificador Prioridades Dinámicas + Round Robin")
    print("Escribe 'help' para ver los comandos.")

    while True:
        try:
            raw = input("os> ").strip()
            if not raw:
                continue
            tokens = raw.split()
            cmd, *args = tokens

            if cmd == "help":
                print(HELP_TEXT)
            elif cmd == "create":
                if len(args) not in {4, 6}:
                    print("Uso: create <nombre> <prioridad> <cpu_total> <memoria> [io_freq io_duracion]")
                    continue
                name = args[0]
                priority = int(args[1])
                cpu_total = int(args[2])
                memory = int(args[3])
                io_freq = int(args[4]) if len(args) == 6 else 0
                io_duration = int(args[5]) if len(args) == 6 else 0
                proc = os_sim.create_process(name, priority, cpu_total, memory, io_freq, io_duration)
                print(f"Proceso creado: {proc.short()}")
            elif cmd == "tick":
                print(os_sim.tick())
            elif cmd == "run":
                n = int(args[0])
                for line in os_sim.run(n):
                    print(line)
            elif cmd == "status":
                print(os_sim.system_status())
            elif cmd == "queues":
                print(os_sim.ready_queues())
            elif cmd == "exit":
                print("Saliendo...")
                break
            else:
                print("Comando no reconocido. Usa 'help'.")
        except (ValueError, IndexError) as exc:
            print(f"Error: {exc}")
        except (KeyboardInterrupt, EOFError):
            print("\nSaliendo...")
            break


if __name__ == "__main__":
    run_cli()
