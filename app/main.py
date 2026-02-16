from __future__ import annotations

import os

import uvicorn


def run() -> None:
    port = int(os.getenv("PORT", os.getenv("DATABRICKS_APP_PORT", "8000")))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False)


if __name__ == "__main__":
    run()
