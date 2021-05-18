#!/usr/bin/env python3

from dataclasses import asdict, dataclass
from functools import partial
from itertools import count
from json import dumps, loads
from locale import str as format_float
from operator import pow
from os import environ
from pathlib import Path
from sys import platform
from tempfile import gettempdir
from typing import Any, Mapping, NamedTuple, Optional, cast

from psutil import cpu_times, disk_io_counters, net_io_counters, virtual_memory

_LO_TIDE = 0.4
_HI_TIDE = 0.8

_TMP = Path(gettempdir())
_TMUX = Path(environ["TMUX"])
_SNAPSHOT = _TMP / "tmux-status-line" / _TMUX.name

_LO, _MED, _HI, _TRANS = (
    environ["tmux_colour_low"],
    environ["tmux_colour_med"],
    environ["tmux_colour_hi"],
    environ["tmux_trans"],
)


@dataclass(frozen=True)
class _Snapshot:
    cpu_times: Mapping[str, float]
    disk_read: int
    disk_write: int
    net_sent: int
    net_recv: int


@dataclass(frozen=True)
class _Stats:
    cpu: float
    mem: float
    disk_read: int
    disk_write: int
    net_sent: int
    net_recv: int


def _human_readable_size(size: float, precision: int = 3) -> str:
    units = ("", "K", "M", "G", "T", "P", "E", "Z", "Y")
    step = partial(pow, 10)
    steps = zip(map(step, count(0, step=3)), units)
    for factor, unit in steps:
        divided = size / factor
        if abs(divided) < 1000:
            fmt = format_float(round(divided, precision))
            return f"{fmt}{unit}"
    else:
        raise ValueError(f"unit over flow: {size}")


def _load() -> Optional[_Snapshot]:
    _SNAPSHOT.parent.mkdir(parents=True, exist_ok=True)
    try:
        raw = _SNAPSHOT.read_text()
    except FileNotFoundError:
        return None
    else:
        json = loads(raw)
        snapshot = _Snapshot(**json)
        return snapshot


def _snap() -> _Snapshot:
    cpu = cast(NamedTuple, cpu_times())
    disk = cast(Any, disk_io_counters())
    net = cast(Any, net_io_counters())
    snapshot = _Snapshot(
        cpu_times=cpu._asdict(),
        disk_read=disk.read_bytes,
        disk_write=disk.write_bytes,
        net_sent=net.bytes_sent,
        net_recv=net.bytes_recv,
    )
    return snapshot


def _cpu(delta: Mapping[str, float]) -> float:
    tot = sum(delta.values())
    if platform.startswith("linux"):
        tot -= delta.get("guest", 0)
        tot -= delta.get("guest_nice", 0)

    busy = tot
    busy -= delta["idle"]
    busy -= delta.get("iowait", 0)

    try:
        return busy / tot
    except ZeroDivisionError:
        return 0


def _measure(s1: _Snapshot, s2: _Snapshot) -> _Stats:
    cpu_delta = {
        k: max(0, v2 - v1)
        for (k, v1), (_, v2) in zip(s1.cpu_times.items(), s2.cpu_times.items())
    }
    mem = virtual_memory()
    stats = _Stats(
        cpu=_cpu(cpu_delta),
        mem=(mem.total - mem.available) / mem.total,
        disk_read=s2.disk_read - s1.disk_read,
        disk_write=s2.disk_write - s1.disk_write,
        net_sent=s2.net_sent - s1.net_sent,
        net_recv=s2.net_recv - s1.net_recv,
    )
    return stats


def _colour(val: float) -> str:
    if val < _LO_TIDE:
        return f"#[bg={_LO}]"
    elif val < _HI_TIDE:
        return f"#[bg={_MED}]"
    else:
        return f"#[bg={_HI}]"


def main() -> None:
    s1, s2 = _load() or _snap(), _snap()
    json = dumps(asdict(s2), check_circular=False, ensure_ascii=False)
    _SNAPSHOT.write_text(json)

    stats = _measure(s1, s2)

    cpu = f"{format(stats.cpu, '4.0%')}"
    mem = f"{format(stats.mem, '4.0%')}"

    disk_read = f"{_human_readable_size(stats.disk_read,precision=0)}B"
    disk_write = f"{_human_readable_size(stats.disk_write,precision=0)}B"

    net_sent = f"{_human_readable_size(stats.net_sent,precision=0)}B"
    net_recv = f"{_human_readable_size(stats.net_recv,precision=0)}B"

    line = (
        f"[⇡ {net_sent} ⇣ {net_recv}] "
        f"[📖 {disk_read} ✏️  {disk_write}] "
        f"{_colour(stats.cpu)} λ{cpu} {_TRANS} "
        f"{_colour(stats.mem)} τ{mem} {_TRANS}"
    )
    print(line)


main()
