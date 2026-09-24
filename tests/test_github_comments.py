import unittest
from unittest.mock import patch

from backend.core.contracts import AgentType, Finding, Severity
from backend.integrations.github_client import format_security_comment, publish_pr_review_comments


def finding() -> Finding:
    return Finding(
        agent_type=AgentType.SECURITY,
        severity=Severity.HIGH,
        category="command_injection",
        file_path="api/run.py",
        line_start=18,
        line_end=18,
        summary="Request input reaches a shell",
        rationale="An attacker can execute arbitrary commands through the command parameter.",
        suggestion="Pass a fixed argument list to subprocess.run with shell=False and allowlist valid commands.",
        confidence=0.95,
    )


class FakePullRequest:
    def __init__(self):
        self.created = []

    def get_review_comments(self):
        return []

    def create_review_comment(self, **kwargs):
        self.created.append(kwargs)


class GitHubCommentTests(unittest.TestCase):
    def test_formats_a_concise_actionable_comment(self):
        comment = format_security_comment(finding())

        self.assertIn("**HIGH | command injection**", comment)
        self.assertIn("**Suggested fix:**", comment)
        self.assertNotIn("Confidence", comment)

    @patch("backend.integrations.github_client._get_installation_client")
    def test_publishes_an_inline_comment_on_reviewed_commit(self, get_client):
        pull_request = FakePullRequest()
        get_client.return_value.get_repo.return_value.get_pull.return_value = pull_request

        published = publish_pr_review_comments(4, "acme/api", 8, "head-sha", [finding()])

        self.assertEqual(published, 1)
        self.assertEqual(pull_request.created[0]["commit"], "head-sha")
        self.assertEqual(pull_request.created[0]["path"], "api/run.py")
        self.assertEqual(pull_request.created[0]["line"], 18)
        self.assertEqual(pull_request.created[0]["side"], "RIGHT")


if __name__ == "__main__":
    unittest.main()
