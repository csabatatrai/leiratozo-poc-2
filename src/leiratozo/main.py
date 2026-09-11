"""Folyamat-belépési pont: `python -m leiratozo.main`, vagy a Docker CMD-ből.

2. fázisban (skeleton) a configolt alapértelmezett adapterek (faster_whisper,
pyannote, ...) még NotImplementedError-t dobnak (3. fázisos stubok) — a
skeleton végponttól-végpontig futtatásához állítsd:
    CONFIG_PATH=config/config.fake.yaml
"""
from __future__ import annotations

import uvicorn

from leiratozo.api.app import create_app
from leiratozo.api.deps import get_config

app = create_app()

if __name__ == "__main__":
    cfg = get_config()
    uvicorn.run("leiratozo.main:app", host=cfg.server.host, port=cfg.server.port)
