"""Local web UI: traceforge-web, then http://127.0.0.1:8000."""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import re
from contextlib import asynccontextmanager
from importlib.resources import files
from urllib.parse import quote

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import HTMLResponse, Response
from starlette.concurrency import run_in_threadpool

from .ingest import MAX_BYTES, InputError
from .pipeline import KINDS, QUALITY, vectorize


@asynccontextmanager
async def lifespan(app):
    app.state.conversion_lock = asyncio.Lock()
    yield


app = FastAPI(title="TraceForge", version="0.1.1", lifespan=lifespan)


@app.get("/healthz")
def health():
    return {"status": "ok", "version": "0.1.1"}


@app.post("/api/vetorizar")
async def vetorizar(
    arquivo: UploadFile = File(...),
    preset: str = Form("auto"),
    qualidade: str = Form("balanced"),
    cores: int | None = Form(None),
    transparente: bool = Form(False),
):
    if preset not in KINDS or qualidade not in QUALITY:
        raise HTTPException(400, "Preset ou qualidade inválidos.")
    if cores is not None and not 2 <= cores <= 64:
        raise HTTPException(400, "Escolha entre 2 e 64 cores.")
    try:
        data = await arquivo.read(MAX_BYTES + 1)
    finally:
        await arquivo.close()
    if len(data) > MAX_BYTES:
        raise HTTPException(413, "Arquivo maior que 20 MB.")
    if not data:
        raise HTTPException(400, "O arquivo está vazio.")
    # CPU work runs outside the event loop. One conversion per worker bounds memory.
    lock = app.state.conversion_lock
    if lock.locked():
        raise HTTPException(503, "Há uma conversão em andamento. Tente novamente em instantes.", headers={"Retry-After": "5"})
    name = (arquivo.filename or "imagem").replace("\\", "/").split("/")[-1]
    stem = re.sub(r'[\x00-\x1f\x7f]', '', name.rsplit('.', 1)[0])[:120] or "imagem"
    async with lock:
        try:
            r = await run_in_threadpool(vectorize, data, preset=preset, quality=qualidade,
                                        colors=cores, transparent=transparente, title=stem)
        except InputError as exc:
            raise HTTPException(400, str(exc)) from exc
        except Exception as exc:
            logging.exception("Conversion failed")
            raise HTTPException(500, "Falha na conversão. Tente outro preset ou uma imagem menor.") from exc
    rep = {k: v for k, v in r.report().items() if k not in ("analise", "candidatos_testados")}
    fallback = re.sub(r'[^A-Za-z0-9._-]', '_', stem) or "imagem"
    report = json.dumps(rep, ensure_ascii=True)
    return Response(r.svg, media_type="image/svg+xml", headers={
        "Content-Disposition": f"attachment; filename=\"{fallback}.svg\"; filename*=UTF-8''{quote(stem + '.svg', safe='')}",
        "X-TraceForge-Report": report,
        "X-Traco-Relatorio": report,
        "X-Content-Type-Options": "nosniff",
        "Cache-Control": "no-store",
    })


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    return files("traco").joinpath("static/index.html").read_text(encoding="utf-8")


def main() -> None:
    import uvicorn
    parser = argparse.ArgumentParser(description="Interface local do TraceForge")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
