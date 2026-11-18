"""Catch-up job for the slow, one-off history downloads (results since 2019, shareholding,
classification, index P/E). Runs daily until everything is filled, then becomes a no-op."""
import os
import sys

from . import classification, index_archive, indices_pe, results_history, shareholding, universe
from .common import Status, log
from .run_all import run_step


def main():
    budget = int(os.environ.get("BUDGET_MIN", "200"))
    status = Status()
    if not universe.OUT.exists():
        run_step(status, "universe", universe.collect)
    run_step(status, "index_pe_history", indices_pe.collect)
    run_step(status, "index_archive", index_archive.collect, 45)
    run_step(status, "classification", classification.collect)
    run_step(status, "shareholding", shareholding.collect, int(budget * 0.3))
    run_step(status, "results_history", results_history.collect, int(budget * 0.7))
    status.write()
    log.info("backfill done: %s", {k: v["note"] for k, v in status.steps.items()})
    return 0


if __name__ == "__main__":
    sys.exit(main())
