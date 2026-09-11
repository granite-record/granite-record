#!/usr/bin/env python3
"""
A pause in the General Court lane: python3 watchers/rest.py SECONDS [label]

The house pace is a bounded run and then a rest, not one long crawl: a run
of 800 requests at fifteen seconds is three and a half hours, and the
calendar drain met two 403s eight hours into an unbroken one. The label is
ignored; it is there so the lane, which runs each queue line once, can be
given the same pause more than once.
"""
import sys
import time

secs = int(sys.argv[1]) if len(sys.argv) > 1 else 3600
print(f"resting {secs // 60} minutes before the next request to the General "
      f"Court", flush=True)
time.sleep(secs)
print("rested", flush=True)
