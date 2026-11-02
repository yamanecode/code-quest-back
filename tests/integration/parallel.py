"""Run requests at the same moment, each thread with its own client (and event loop)."""

from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import httpx
from fastapi import FastAPI
from fastapi.testclient import TestClient

Call = Callable[[TestClient], httpx.Response]


def run_parallel(app: FastAPI, calls: list[Call]) -> list[httpx.Response]:
    """The responses of `calls`, in order; the barrier makes them start together."""
    barrier = Barrier(len(calls))

    def run(call: Call) -> httpx.Response:
        with TestClient(app) as client:
            barrier.wait()
            return call(client)

    with ThreadPoolExecutor(max_workers=len(calls)) as pool:
        return list(pool.map(run, calls))
