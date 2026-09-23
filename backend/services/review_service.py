"""Connect retrieval, specialist LLM review, and durable PR findings."""
from __future__ import annotations

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.agents.context_builder import PatchFile, build_review_context
from backend.agents.security_agent import review_security
from backend.models import AgentEvent, Finding as FindingRecord, PR
from backend.services.retrieval_service import retrieve_context


async def run_security_review(
    session: AsyncSession,
    *,
    repo_name: str,
    pr_number: int,
    title: str,
    description: str | None,
    head_sha: str,
    author: str,
    changed_files: list,
) -> int:
    """Review one PR and atomically replace its previous security findings."""
    retrieved = await retrieve_context(session, repo_name=repo_name, changed_files=changed_files)
    context = build_review_context(
        repo=repo_name,
        pr_number=pr_number,
        head_sha=head_sha,
        title=title,
        description=description,
        files=[PatchFile(f.file_path, f.patch, f.status) for f in changed_files],
        retrieved=retrieved,
    )
    findings = await review_security(context)

    result = await session.execute(select(PR).where(PR.github_pr_id == pr_number))
    pr = result.scalar_one_or_none()
    if pr is None:
        pr = PR(github_pr_id=pr_number, repo_name=repo_name, title=title, author=author, status="analyzed")
        session.add(pr)
        await session.flush()
    else:
        pr.repo_name, pr.title, pr.author, pr.status = repo_name, title, author, "analyzed"
        await session.execute(delete(FindingRecord).where(FindingRecord.pr_id == pr.id))

    for finding in findings:
        session.add(FindingRecord(
            pr_id=pr.id,
            file_path=finding.file_path,
            line_number=finding.line_start,
            severity=str(finding.severity.value if hasattr(finding.severity, "value") else finding.severity),
            category=finding.category,
            comment=f"{finding.summary}\n\n{finding.rationale}\n\nSuggestion: {finding.suggestion}",
        ))
    session.add(AgentEvent(
        pr_id=pr.id,
        event_type="security_review_completed",
        payload={
            "finding_count": len(findings),
            "reference_paths": context.reference_paths,
            "skipped_files": [item.path for item in context.skipped],
        },
    ))
    await session.commit()
    return len(findings)
