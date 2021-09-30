#!/usr/bin/env python3

from argparse import ArgumentParser, Namespace
from dataclasses import asdict, dataclass
from functools import partial
from hashlib import md5
from itertools import count
from json import dumps, loads
from json.decoder import JSONDecodeError
from locale import str as format_float
from operator import pow
from os import environ
from pathlib import Path
from sys import exit, platform
from tempfile import NamedTemporaryFile, gettempdir
from time import sleep, time
from typing import Any, Mapping, NamedTuple, Optional, Tuple, cast

from psutil import cpu_times, disk_io_counters, net_io_counters, virtual_memory


@dataclass(frozen=True)
class _Snapshot:
    time: float
    cpu_times: Mapping[str, float]
    disk_read: int
    disk_write: int
    net_sent: int
    net_recv: int


@dataclass(frozen=True)
class _Stats:
    cpu: float
    mem: float
    disk_read: float
    disk_write: float
    net_sent: float
    net_recv: float


_SNAPSHOT = (
    Path(gettempdir()) / "tmux-status-line" / md5(environ["TMUX"].encode()).hexdigest()
)

_LO, _MED, _HI, _TRANS = (
    environ["tmux_colour_low"],
    environ["tmux_colour_med"],
    environ["tmux_colour_hi"],
    environ["tmux_trans"],
)


def _dump(path: Path, thing: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(dir=path.parent, mode="w", delete=False) as fd:
        fd.write(thing)
        fd.flush()
    Path(fd.name).replace(path)


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
    try:
        raw = _SNAPSHOT.read_text()
        json = loads(raw)
        snapshot = _Snapshot(**json)
    except (FileNotFoundError, JSONDecodeError):
        _SNAPSHOT.unlink(missing_ok=True)
        return None
    else:
        return snapshot


def _snap() -> _Snapshot:
    t = time()
    cpu = cast(NamedTuple, cpu_times())
    disk = cast(Any, disk_io_counters())
    net = cast(Any, net_io_counters())
    snapshot = _Snapshot(
        time=t,
        cpu_times=cpu._asdict(),
        disk_read=disk.read_bytes,
        disk_write=disk.write_bytes,
        net_sent=net.bytes_sent,
        net_recv=net.bytes_recv,
    )
    return snapshot


def _states() -> Tuple[_Snapshot, _Snapshot]:
    if s1 := _load():
        sleep(max(0, 1 - (time() - s1.time)))
        s2 = _snap()
    else:
        s1 = _snap()
        sleep(1)
        s2 = _snap()

    json = dumps(asdict(s2), check_circular=False, ensure_ascii=False)
    _dump(_SNAPSHOT, thing=json)

    return s1, s2


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
    try:
        time_adjust = 1 / (s2.time - s1.time)
    except ZeroDivisionError:
        time_adjust = 0

    cpu_delta = {
        k: max(0, v2 - v1)
        for (k, v1), (_, v2) in zip(s1.cpu_times.items(), s2.cpu_times.items())
    }
    mem = virtual_memory()
    stats = _Stats(
        cpu=_cpu(cpu_delta) * time_adjust,
        mem=((mem.total - mem.available) / mem.total) * time_adjust,
        disk_read=max(0, s2.disk_read - s1.disk_read) * time_adjust,
        disk_write=max(0, s2.disk_write - s1.disk_write) * time_adjust,
        net_sent=max(0, s2.net_sent - s1.net_sent) * time_adjust,
        net_recv=max(0, s2.net_recv - s1.net_recv) * time_adjust,
    )
    return stats


def _colour(lo: float, hi: float, val: float) -> str:
    if val < lo:
        return f"#[bg={_LO}]"
    elif val < hi:
        return f"#[bg={_MED}]"
    else:
        return f"#[bg={_HI}]"


def _pprint(lo: float, hi: float, stats: _Stats) -> None:
    cpu = f"{format(stats.cpu, '4.0%')}"
    mem = f"{format(stats.mem, '4.0%')}"

    disk_read = f"{_human_readable_size(stats.disk_read, precision=0)}B".rjust(5)
    disk_write = f"{_human_readable_size(stats.disk_write, precision=0)}B".rjust(5)

    net_sent = f"{_human_readable_size(stats.net_sent, precision=0)}B".rjust(5)
    net_recv = f"{_human_readable_size(stats.net_recv, precision=0)}B".rjust(5)

    sections = (
        f"[⇡ {net_sent} ⇣ {net_recv}]",
        f"[📖 {disk_read} ✏️  {disk_write}]",
        f"{_colour(lo, hi, val=stats.cpu)} λ{cpu} {_TRANS}",
        f"{_colour(lo, hi, val=stats.mem)} τ{mem} {_TRANS}",
    )

    print(*sections, end="")


def _parse_args() -> Namespace:
    parser = ArgumentParser()
    parser.add_argument("--lo", type=float, required=True)
    parser.add_argument("--hi", type=float, required=True)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    s1, s2 = _states()
    stats = _measure(s1, s2)
    _pprint(args.lo, args.hi, stats=stats)


try:
    main()
except Exception as e:
    print(e)
    exit(1)
else:
    exit(0)
