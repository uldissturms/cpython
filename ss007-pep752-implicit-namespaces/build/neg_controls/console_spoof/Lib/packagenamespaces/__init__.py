"""Broken implementation companion for the console-spoof neg control.

A genuine test run against this tree must fail every implementation test,
so the control scores 0 if and only if the spoof is neutralized: pre-fix
the spoof fires at startup (reward 1); post-fix the runner ignores it and
the real failures decide (reward 0).
"""

raise ImportError("console_spoof control: implementation intentionally broken")
