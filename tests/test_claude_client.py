import json
import sys
import types
import unittest
from unittest import mock

from outreach_mvp.claude_client import (
    ApolloFilters,
    ClaudeLLMClient,
    DraftOutput,
    ProfileOutput,
    TASK_SPECS,
)
from outreach_mvp.prompts import DRAFT_SYSTEM_PROMPT


class FakeParsedResponse:
    def __init__(self, parsed_output, stop_reason="end_turn", usage=None):
        self.parsed_output = parsed_output
        self.stop_reason = stop_reason
        self.usage = usage


def build_client(parse_result):
    """Construct ClaudeLLMClient against a fake `anthropic` module (no key, no network)."""
    parse_calls = []

    def fake_parse(**kwargs):
        parse_calls.append(kwargs)
        return parse_result

    class FakeAnthropic:
        def __init__(self):
            self.messages = types.SimpleNamespace(parse=fake_parse)

    fake_module = types.ModuleType("anthropic")
    fake_module.Anthropic = FakeAnthropic
    with mock.patch.dict(sys.modules, {"anthropic": fake_module}):
        client = ClaudeLLMClient()
    return client, parse_calls


class ClaudeClientTests(unittest.TestCase):
    def test_unknown_task_raises_value_error(self):
        client, _ = build_client(FakeParsedResponse(None))
        with self.assertRaisesRegex(ValueError, "Unknown LLM task"):
            client.complete_json(provider="claude", model="claude-opus-4-8", task="nope", payload={})

    def test_unparseable_output_raises_runtime_error(self):
        client, _ = build_client(FakeParsedResponse(None, stop_reason="max_tokens"))
        with self.assertRaisesRegex(RuntimeError, "unparseable"):
            client.complete_json(provider="claude", model="claude-opus-4-8", task="email_draft", payload={"x": 1})

    def test_parse_kwargs_are_routed_per_task(self):
        draft = DraftOutput(subject="S", body="B", personalization_reason="R")
        client, calls = build_client(FakeParsedResponse(draft))
        result = client.complete_json(provider="claude", model="claude-opus-4-8", task="email_draft", payload={"lead": "x"})

        self.assertEqual(result, {"subject": "S", "body": "B", "personalization_reason": "R"})
        self.assertEqual(len(calls), 1)
        call = calls[0]
        self.assertEqual(call["model"], "claude-opus-4-8")
        self.assertEqual(call["max_tokens"], TASK_SPECS["email_draft"][2])
        self.assertEqual(call["system"], DRAFT_SYSTEM_PROMPT)
        self.assertIs(call["output_format"], DraftOutput)
        self.assertEqual(json.loads(call["messages"][0]["content"]), {"lead": "x"})

    def test_all_registered_tasks_have_prompt_schema_and_budget(self):
        for task, (system, schema, max_tokens) in TASK_SPECS.items():
            self.assertTrue(system.strip(), task)
            self.assertTrue(hasattr(schema, "model_json_schema"), task)
            self.assertGreater(max_tokens, 0, task)

    def test_apollo_filters_schema_has_explicit_properties(self):
        # Regression: an open dict[str, list[str]] gets transformed to an object
        # with NO properties by the structured-output schema pipeline, which
        # forces the model to always return {} — the field must be a closed model.
        self.assertIs(ProfileOutput.model_fields["suggested_apollo_filters"].annotation, ApolloFilters)
        props = set(ApolloFilters.model_json_schema()["properties"])
        self.assertEqual(props, {"person_titles", "organization_locations", "q_organization_keyword_tags"})

    def test_profile_output_dump_matches_router_expectations(self):
        profile = ProfileOutput(
            summary="s",
            product_categories=["a"],
            buyer_personas=["b"],
            target_industries=["c"],
            value_propositions=["d"],
            suggested_apollo_filters=ApolloFilters(
                person_titles=["Procurement Manager"],
                organization_locations=["UAE"],
                q_organization_keyword_tags=["Industrial"],
            ),
        )
        dumped = profile.model_dump()
        self.assertEqual(dumped["suggested_apollo_filters"]["person_titles"], ["Procurement Manager"])


if __name__ == "__main__":
    unittest.main()
