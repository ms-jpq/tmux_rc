#!/usr/bin/env python3

from psutil import cpu_percent

cpu = cpu_percent(interval=1)

print()
