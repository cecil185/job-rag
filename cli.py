"""CLI interface using Typer."""
import logging
from typing import List
from typing import Optional

import typer
from sqlalchemy.orm import Session

from src.database import get_db
from src.database import init_db
from src.evidence_rag import EvidenceRAG
from src.workflow import Workflow

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger(__name__)

app = typer.Typer()


@app.command()
def init():
    """Initialize database."""
    logger.info("Initializing database")
    init_db()
    logger.info("Database initialized")
    typer.echo("Database initialized!")


@app.command()
def add_evidence(
    text: str = typer.Option(..., "--text", "-t", help="Evidence text"),
    source_id: str = typer.Option(..., "--id", help="Source ID"),
):
    """Add evidence to Evidence RAG."""
    logger.info("Adding evidence (source_id=%s)", source_id)
    db = next(get_db())
    evidence_rag = EvidenceRAG(db)
    evidence_rag.add_evidence(text, source_id)
    logger.info("Evidence added")
    typer.echo("Evidence added")


@app.command()
def process_jobs(
    urls: List[str] = typer.Argument(..., help="Job posting URLs"),
    role_tags: Optional[str] = typer.Option(None, "--tags", help="Role tags (comma-separated)"),
    reprocess: bool = typer.Option(False, "--reprocess", help="Overwrite existing jobs in database"),
):
    """Process job posting URLs."""
    logger.info("Processing %d job URL(s)", len(urls))
    db = next(get_db())
    workflow = Workflow(db)

    tags = [t.strip() for t in role_tags.split(",")] if role_tags else None

    typer.echo(f"Processing {len(urls)} job(s)...")
    results = workflow.process_job_links(urls, tags, reprocess=reprocess)
    logger.info("Process jobs finished: %d results", len(results))

    for result in results:
        if result["status"] == "success":
            typer.echo(f"✅ {result['url']} - Fit: {result['fit_score']:.2%}")
        elif result["status"] == "exists":
            typer.echo(f"ℹ️  {result['url']} - Already processed")
        else:
            typer.echo(f"❌ {result['url']} - Error: {result.get('error', 'Unknown')}")


@app.command()
def list_jobs():
    """List ranked jobs."""
    logger.info("Fetching ranked jobs")
    db = next(get_db())
    workflow = Workflow(db)

    ranked = workflow.get_ranked_jobs()
    logger.info("Ranked jobs: %d", len(ranked) if ranked else 0)

    if ranked:
        typer.echo("\nRanked Jobs by Fit Score:\n")
        for i, job in enumerate(ranked, 1):
            typer.echo(f"{i}. {job['url']}")
            typer.echo(f"   Fit: {job['fit_score']:.2%} | URL: {job['url']}")
            if job['gaps']:
                typer.echo(f"   Gaps: {len(job['gaps'])}")
            typer.echo()
    else:
        typer.echo("No jobs processed yet.")


@app.command()
def approve(
    edit_pack_id: int = typer.Argument(..., help="Edit pack ID to approve")
):
    """Approve an edit pack."""
    logger.info("Approving edit_pack_id=%s", edit_pack_id)
    db = next(get_db())
    workflow = Workflow(db)

    workflow.approve_edit_pack(edit_pack_id)
    logger.info("Edit pack %s approved", edit_pack_id)
    typer.echo(f"Edit pack {edit_pack_id} approved and added to Style RAG!")


if __name__ == "__main__":
    app()
