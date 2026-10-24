"""Command line: `fkp --help`."""

from __future__ import annotations

import json
import os
import time
from datetime import UTC, datetime
from pathlib import Path

import typer

from . import jobs as jobs_mod

app = typer.Typer(add_completion=False, help="WhatsApp-first hiring for skilled workers.")


def _store():  # type: ignore[no-untyped-def]
    from .store import Store

    dsn = os.environ.get("FKP_DATABASE_URL")
    if not dsn:
        typer.echo("FKP_DATABASE_URL is not set", err=True)
        raise typer.Exit(2)
    return Store(dsn)


@app.command()
def migrate() -> None:
    """Apply database migrations."""
    typer.echo(f"applied: {', '.join(_store().migrate()) or 'nothing new'}")


@app.command()
def seed(path: Path = typer.Option(None, help="jobs YAML; default config/jobs.example.yaml")) -> None:
    """Load jobs into the database (each one passes the AGG check first)."""
    store = _store()
    for j in jobs_mod.load(str(path) if path else None):
        blocking = [i for i in jobs_mod.check_agg(j) if i.severity == "block"]
        if blocking:
            typer.echo(f"{j.id}: not loaded, {', '.join(i.rule for i in blocking)}", err=True)
            continue
        store.upsert_job(j)
        typer.echo(f"{j.id}: {j.title}")


@app.command()
def lint(path: Path) -> None:
    """Check job texts for discriminating wording (AGG); exit 1 on a blocking issue."""
    bad = 0
    for j in jobs_mod.load(str(path)):
        for i in jobs_mod.check_agg(j):
            typer.echo(f"{j.id}: {i.severity:5} {i.rule}: “{i.quote}”. {i.advice}")
            bad += i.severity == "block"
    raise typer.Exit(1 if bad else 0)


@app.command()
def chat(job: str = typer.Option("", help="a job id the candidate asks about"), name: str = "Test Person") -> None:
    """Talk to the assistant in the terminal (no database, no WhatsApp)."""
    from .dialogue import Agent, Conversation, Inbound

    agent = Agent(jobs_mod.load())
    conv = Conversation(id="local", phone="0")
    first = True
    while True:
        try:
            text = input("you> ")
        except EOFError:
            break
        if first and job:
            text = f"{job} {text}"
        first = False
        button = text[1:] if text.startswith("@") else ""
        res = agent.handle(conv, Inbound(id=str(time.time_ns()), at=datetime.now(UTC), kind="button" if button else "text",
                                         text="" if button else text, button_id=button, profile_name=name))
        for o in res.outgoing:
            typer.echo(f"bot> {o.body}")
            for bid, title in o.buttons:
                typer.echo(f"     [@{bid}] {title}")
        if conv.stage in ("handed_over", "deleted", "pooled"):
            typer.echo(json.dumps({k: v.value for k, v in conv.profile.items()}, ensure_ascii=False, indent=1))


@app.command()
def worker(interval: float = typer.Option(2.0, help="seconds between outbox passes"),
           once: bool = typer.Option(False, help="one pass, then exit")) -> None:
    """Deliver the outbox, queue reminders and apply retention, in a loop."""
    from .api import app_from_env

    built = app_from_env()
    engine = built.state.engine
    last_tick = 0.0
    while True:
        now = datetime.now(UTC)
        stats = engine.deliver(now)
        if time.time() - last_tick > 60:
            stats["reminders"] = engine.tick(now)
            stats["purged"] = engine.purge(now)
            last_tick = time.time()
        if any(stats.values()):
            typer.echo(json.dumps({"at": now.isoformat(timespec="seconds"), **stats}))
        if once:
            break
        time.sleep(interval)


@app.command()
def serve(host: str = "0.0.0.0", port: int = 8000) -> None:  # noqa: S104
    """Run the API."""
    import uvicorn

    uvicorn.run("fkp.api:app_from_env", host=host, port=port, factory=True)


@app.command()
def demo(n: int = typer.Option(60, help="simulated candidates"), seed: int = 21) -> None:
    """Fill the database with simulated candidates (sandbox channel) for the web app."""
    from .engine import Engine
    from .sim import demo as demo_mod
    from .whatsapp import SandboxClient

    store = _store()
    store.migrate()
    for j in jobs_mod.load():
        store.upsert_job(j)
    stages = demo_mod.seed(store, Engine(store, {"sandbox": SandboxClient()}), n, datetime.now(UTC), seed)
    typer.echo(json.dumps(stages))


@app.command("eval")
def eval_cmd(out: Path = typer.Option(Path("reports"), help="where to write the reports")) -> None:
    """Simulated candidates with hidden truth: the assistant against a form bot and keyword matching."""
    from .sim import evaluate

    rep = evaluate.run()
    out.mkdir(parents=True, exist_ok=True)
    (out / "simulation.json").write_text(json.dumps(rep, indent=2, ensure_ascii=False) + "\n")
    (out / "SIMULATION.md").write_text(evaluate.markdown(rep))
    typer.echo(evaluate.markdown(rep))


@app.command()
def heldout(set_dir: Path) -> None:
    """Run a held-out set once; the first run is kept as the honest number."""
    from . import heldout as ho

    res = ho.run(set_dir)
    path, first = ho.record(res)
    typer.echo(res["markdown"])
    typer.echo(f"{'first run recorded' if first else 'latest run recorded'} in {path}")


def main() -> None:  # pragma: no cover
    app(prog_name="fkp")


if __name__ == "__main__":  # pragma: no cover
    main()
