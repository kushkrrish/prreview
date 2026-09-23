import unittest

from backend.agents.context_builder import PatchFile, build_review_context
from backend.agents.security_agent import SecurityReview, _parse_security_review, count_review_tokens, review_security
from backend.core.contracts import AgentType, Finding, Severity


class FakeCompletions:
    def __init__(self, parsed):
        self.parsed = parsed
        self.called_with = None

    async def parse(self, **kwargs):
        self.called_with = kwargs
        message = type("Message", (), {"parsed": self.parsed})()
        choice = type("Choice", (), {"message": message})()
        return type("Response", (), {"choices": [choice]})()


class FakeClient:
    def __init__(self, parsed):
        completions = FakeCompletions(parsed)
        self.beta = type("Beta", (), {"chat": type("Chat", (), {"completions": completions})()})()
        self.completions = completions


def finding(*, path="app.py", start=3, end=3):
    return Finding(
        agent_type=AgentType.QUALITY,  # proves the agent normalizes its own type
        severity=Severity.HIGH,
        category="injection",
        file_path=path,
        line_start=start,
        line_end=end,
        summary="Unsafe shell command",
        rationale="Untrusted input reaches the shell.",
        suggestion="Use an argument array and validate the input.",
        confidence=0.9,
    )


class SecurityAgentTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.context = build_review_context(
            repo="acme/api",
            pr_number=7,
            head_sha="abc",
            title="Run task",
            description=None,
            files=[PatchFile("app.py", "@@ -1,2 +1,3 @@\n old = 1\n+user = request.args['cmd']\n+os.system(user)")],
            nonce="fixed",
        )

    async def test_returns_structured_security_findings_on_added_lines(self):
        client = FakeClient(SecurityReview(findings=[finding()]))

        result = await review_security(self.context, client=client, model="test-model")

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].agent_type, AgentType.SECURITY)
        self.assertEqual(client.completions.called_with["model"], "test-model")
        self.assertIs(client.completions.called_with["response_format"], SecurityReview)

    async def test_discards_hallucinated_paths_and_unchanged_lines(self):
        client = FakeClient(SecurityReview(findings=[finding(path="other.py"), finding(start=1, end=1)]))

        result = await review_security(self.context, client=client)

        self.assertEqual(result, [])

    def test_counts_complete_review_payload(self):
        token_count = count_review_tokens(self.context)

        self.assertGreater(token_count, len(self.context.shared_prompt) // 5)

    def test_normalizes_provider_confidence_from_five_point_scale(self):
        review = _parse_security_review(
            '{"findings": [{"agent_type": "security", "severity": "high", '
            '"category": "injection", "file_path": "app.py", "line_start": 3, '
            '"line_end": 3, "summary": "Unsafe shell command", '
            '"suggestion": "Avoid shell execution", "confidence": 3, '
            '"rationale": "Input reaches a shell."}]}'
        )

        self.assertEqual(review.findings[0].confidence, 0.6)


if __name__ == "__main__":
    unittest.main()
