"""Convenience launcher for the Operation Fogline dashboard.

Run:

    python dashboard.py

The command-line interface is also available through run_simulation.py.
"""

from run_simulation import MainDashboardConsole


if __name__ == "__main__":
    MainDashboardConsole().loop()
