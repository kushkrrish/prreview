"""Connect retrieval, specialist LLM review, and durable PR findings."""
from __future__ import annotations

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.agents.context_builder import ContextLimits, PatchFile, build_review_context, split_diff_by_file
from backend.agents.security_agent import review_cross_file_findings, review_security
from backend.models import AgentEvent, Finding as FindingRecord, PR
from backend.services.retrieval_service import RetrievalConfig, retrieve_context_for_patch


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
) -> list:
    """Review one PR and atomically replace its previous security findings."""
    chunks = split_diff_by_file([PatchFile(f.file_path, f.patch, f.status) for f in changed_files])
    findings = []
    skipped_paths = []
    reference_paths = []
    for chunk in chunks:
        retrieved = await retrieve_context_for_patch(
            session,
            repo_name=repo_name,
            patch_file=chunk,
            config=RetrievalConfig(neighbors_per_query=4, max_results=4),
        )
        context = build_review_context(
            repo=repo_name,
            pr_number=pr_number,
            head_sha=head_sha,
            title=title,
            description=description,
            files=[chunk],
            retrieved=retrieved,
            limits=ContextLimits(
                max_reference_chars=2_000,
                max_chars_per_reference=2_000,
                max_references=4,
            ),
        )
        findings.extend(await review_security(context))
        skipped_paths.extend(item.path for item in context.skipped)
        reference_paths.extend(context.reference_paths)

    unique_findings = {}
    for finding in findings:
        key = (finding.file_path, finding.line_start, finding.line_end, finding.category)
        unique_findings.setdefault(key, finding)
    findings = list(unique_findings.values())
    cross_file_review = await review_cross_file_findings(findings)

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
            "reference_paths": sorted(set(reference_paths)),
            "skipped_files": sorted(set(skipped_paths)),
            "cross_file_risk": cross_file_review.cross_file_risk,
            "cross_file_rationale": cross_file_review.rationale,
        },
    ))
    await session.commit()
    return findings
