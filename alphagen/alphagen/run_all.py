"""Runs every collection step. A failing step is recorded in data/STATUS.md and the rest carry on."""
import os
import sys

from . import (classification, fundamentals, indices_pe, macro, mutual_funds, nse, prices, results_history,
               shareholding, universe)
from .common import Status, log


def run_step(status, name, fn, *args):
    try:
        rows, note = fn(*args)
        status.record(name, True, rows, note)
    except Exception as e:
        log.exception("step %s failed", name)
        status.record(name, False, 0, f"{type(e).__name__}: {e}")


def main():
    max_tickers = int(os.environ.get("MAX_TICKERS", "0")) or None  # set for a quick test run
    status = Status()
    run_step(status, "universe", universe.collect)
    if not (universe.OUT.exists()):
        status.write()
        log.error("No universe available - stopping")
        return 0
    run_step(status, "prices", prices.collect)
    run_step(status, "nse_delivery", nse.delivery)
    run_step(status, "nse_fo", nse.fo)
    run_step(status, "nse_participant_oi", nse.participant_oi)
    run_step(status, "nse_fii_dii", nse.fii_dii)
    run_step(status, "nse_deals", nse.deals)
    run_step(status, "mutual_funds", mutual_funds.collect)
    run_step(status, "macro", macro.collect)
    run_step(status, "fundamentals", fundamentals.collect, max_tickers)
    run_step(status, "index_pe_history", indices_pe.collect)
    run_step(status, "classification", classification.collect)
    run_step(status, "shareholding", shareholding.collect, 40)
    run_step(status, "sast", shareholding.sast)
    run_step(status, "results_history", results_history.collect, int(os.environ.get("RESULTS_BUDGET_MIN", "60")))
    status.write()
    failed = [k for k, v in status.steps.items() if not v["ok"]]
    log.info("Done. Failed steps: %s", failed or "none")
    return 0  # always succeed so whatever was collected still gets saved


if __name__ == "__main__":
    sys.exit(main())
