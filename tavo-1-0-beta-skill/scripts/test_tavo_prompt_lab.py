#!/usr/bin/env python3
from __future__ import annotations

import contextlib
import io
import json
import os
import re
import stat
import sys
import tempfile
import threading
import unittest
from unittest import mock
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS))

import tavo_prompt_lab as lab  # noqa: E402
import tavo_virtual_provider as provider  # noqa: E402


CLIENT_KEY = "prompt-lab-fixture-secret"


def base_preset(*extra: dict) -> dict:
    return {
        "name": "Lab preset",
        "basicPrompts": {
            "persona": "Persona: {{persona}}",
            "description": "Description: {{description}}",
            "personality": "Personality: {{personality}}",
            "scenario": "Scenario: {{scenario}}",
            "exampleMessageStart": "[Example dialogue]",
            "chatStart": "[Start of current chat]",
            "lorebook": "{0}",
        },
        "entries": [
            {
                "identifier": "main-custom",
                "content": "MAIN {{char}} / {{user}}",
                "role": "system",
                "type": "custom",
                "injectionPosition": "relative",
                "enabled": True,
                "active": True,
            },
            *extra,
        ],
    }


def marker(identifier: str) -> dict:
    return {
        "identifier": identifier,
        "content": "",
        "role": "system",
        "type": "marker",
        "injectionPosition": "relative",
        "enabled": True,
        "active": True,
    }


def character(**overrides: object) -> dict:
    value: dict[str, object] = {
        "spec": "chara_card_v2",
        "spec_version": "2.0",
        "data": {
            "name": "Mira",
            "description": "A careful cartographer.",
            "personality": "Precise.",
            "scenario": "Mira maps a dragon valley with {{user}}.",
            "first_mes": "Welcome, {{user}}.",
            "alternate_greetings": ["Alternate for {{user}}."],
            "mes_example": "<START>\n{{user}}: Where?\n{{char}}: North.",
        },
    }
    value["data"].update(overrides)  # type: ignore[union-attr]
    return value


def worldbook(entries: list[dict], name: str = "Lab lore") -> dict:
    return {"name": name, "entries": entries}


def constant(identifier: str, content: str, position: str, **extra: object) -> dict:
    return {
        "identifier": identifier,
        "name": identifier,
        "content": content,
        "enabled": True,
        "strategy": "constant",
        "injectionPosition": position,
        "injectionDepth": 1,
        "injectionRole": "system",
        "probability": 100,
        "sticky": 0,
        "cooldown": 0,
        "delay": 0,
        **extra,
    }


def regex_entry(
    identifier: str,
    find_regex: str,
    replacement: str,
    *,
    placements: list[str],
    timing: str,
    substitution: str = "none",
    min_depth: int | None = None,
    max_depth: int | None = None,
) -> dict:
    return {
        "identifier": identifier,
        "name": identifier,
        "findRegex": find_regex,
        "replaceString": replacement,
        "trimStrings": [],
        "placements": placements,
        "timing": timing,
        "substitution": substitution,
        "minDepth": min_depth,
        "maxDepth": max_depth,
        "enabled": True,
    }


def regex_group(name: str, *entries: dict) -> dict:
    return {"name": name, "entries": list(entries)}


def request_text(result: dict) -> str:
    return "\n".join(item["content"] for item in result["request"]["messages"])


class PromptLabCompileTests(unittest.TestCase):
    def test_native_tavo_10_role_adapter_keeps_only_leading_system_role(self) -> None:
        post = {
            "identifier": "post",
            "content": "POST",
            "role": "system",
            "type": "custom",
            "injectionPosition": "relative",
            "enabled": True,
            "active": True,
        }
        result = lab.compile_case(
            {
                "preset": base_preset(
                    marker("personaDescription"),
                    marker("chatHistory"),
                    post,
                ),
                "character": character(),
                "persona": {"name": "Rin", "description": "Tester."},
                "userInput": "GO",
            },
            Path.cwd(),
        )

        self.assertEqual(
            [item["role"] for item in result["request"]["messages"]],
            ["system", "user", "assistant", "user"],
        )
        self.assertEqual(result["request"]["messages"][0]["content"], "MAIN Mira / Rin")
        self.assertEqual(
            result["request"]["messages"][1]["content"],
            "Persona: Tester.\n\n[Start of current chat]",
        )
        self.assertEqual(result["request"]["messages"][3]["content"], "GO\n\nPOST")
        self.assertEqual(
            [item["coerced"] for item in result["adapterTrace"]],
            [False, True, True, False, False, True],
        )

    def test_relative_order_examples_greeting_worldbook_positions_and_hidden_history(self) -> None:
        preset = base_preset(
            marker("worldInfoBefore"),
            marker("personaDescription"),
            marker("charDescription"),
            marker("charPersonality"),
            marker("scenario"),
            marker("worldInfoAfter"),
            marker("dialogueExamples"),
            marker("chatHistory"),
        )
        lore = worldbook(
            [
                constant("before", "BEFORE", "lorebookBefore"),
                {
                    **constant("after", "AFTER {{char}}", "lorebookAfter"),
                    "strategy": "keyword",
                    "keywords": ["dragon"],
                    "scanDepth": 2,
                    "caseSensitive": False,
                    "matchWholeWord": False,
                },
                constant("top", "TOP", "topOfExampleMessages"),
                constant("bottom", "BOTTOM", "bottomOfExampleMessages"),
                constant("depth", "AT DEPTH", "atDepth", injectionRole="assistant"),
                {
                    **constant("miss", "NEVER", "lorebookAfter"),
                    "strategy": "keyword",
                    "keywords": ["unseen"],
                    "scanDepth": 2,
                    "matchWholeWord": False,
                },
            ]
        )
        case = {
            "preset": preset,
            "character": character(),
            "persona": {"name": "Rin", "description": "A patient tester."},
            "worldbooks": [lore],
            "history": [{"role": "assistant", "content": "HIDDEN", "hidden": True}],
            "userInput": "The dragon is here.",
            "model": "fixture-model",
        }

        result = lab.compile_case(case, Path.cwd())

        self.assertEqual(
            [item["role"] for item in result["request"]["messages"]],
            ["system", "user", "assistant", "user"],
        )
        expected_context = "\n\n".join(
            [
                "BEFORE\n",
                "Persona: A patient tester.",
                "Description: A careful cartographer.",
                "Personality: Precise.",
                "Scenario: Mira maps a dragon valley with Rin.",
                "AFTER Mira\n",
                "[Example dialogue]\n\nMira: TOP\n\n[Example dialogue]\n\nRin: Where?\n\nMira: North.\n\n[Example dialogue]\n\nMira: BOTTOM",
                "[Start of current chat]",
            ]
        )
        self.assertEqual(result["request"]["messages"][0]["content"], "MAIN Mira / Rin")
        self.assertEqual(result["request"]["messages"][1]["content"], expected_context)
        self.assertEqual(
            result["request"]["messages"][2]["content"],
            "Welcome, Rin.\n\nAT DEPTH",
        )
        self.assertEqual(result["request"]["messages"][3]["content"], "The dragon is here.")
        self.assertEqual(len(result["triggeredWorldbooks"]), 5)
        decisions = {item["entry"]: item["status"] for item in result["worldbookDecisions"]}
        self.assertEqual(decisions["miss"], "keyword_miss")
        warning_codes = {item["code"] for item in result["warnings"]}
        self.assertIn("hidden_history_omitted", warning_codes)
        self.assertIn("scan_depth_policy", warning_codes)
        self.assertNotIn("HIDDEN", json.dumps(result))

    def test_lorebook_wrapper_without_zero_slot_drops_activated_content(self) -> None:
        preset = base_preset(marker("worldInfoAfter"), marker("chatHistory"))
        preset["basicPrompts"]["lorebook"] = "[WRAPPER-WITHOUT-SLOT]"
        result = lab.compile_case(
            {
                "preset": preset,
                "character": character(),
                "worldbooks": [
                    worldbook(
                        [constant("constant-after", "SECRET-LORE-CONTENT", "lorebookAfter")]
                    )
                ],
                "greeting": False,
                "userInput": "go",
            },
            Path.cwd(),
        )

        joined = request_text(result)
        self.assertIn("[WRAPPER-WITHOUT-SLOT]", joined)
        self.assertNotIn("SECRET-LORE-CONTENT", joined)
        self.assertEqual(result["worldbookDecisions"][0]["status"], "triggered")
        self.assertIn(
            "lorebook_wrapper_missing_slot",
            {item["code"] for item in result["warnings"]},
        )

    def test_single_chat_preserves_name_and_warns_for_unconsumed_character_fields(self) -> None:
        preset = base_preset(marker("dialogueExamples"), marker("chatHistory"))
        preset["active"] = False
        preset["basicPrompts"].update(
            {
                "groupChatStart": "GROUP",
                "groupNudge": "GROUP NUDGE",
                "continueNudge": "CONTINUE",
                "impersonation": "IMPERSONATE",
            }
        )
        lore = worldbook([constant("top", "TOP", "topOfExampleMessages")])
        case = {
            "preset": preset,
            "character": character(
                nickname="Northstar",
                group_only_greetings=["Group hello"],
                character_book={
                    "token_budget": 100,
                    "recursive_scanning": True,
                    "entries": [],
                },
            ),
            "persona": {"name": "Rin", "description": ""},
            "worldbooks": [lore],
            "userInput": "Hello, {{char}}.",
            "model": "fixture-model",
        }

        result = lab.compile_case(case, Path.cwd())
        joined = "\n".join(item["content"] for item in result["request"]["messages"])

        self.assertIn("MAIN Mira / Rin", joined)
        self.assertIn("[Example dialogue]\n\nMira: TOP", joined)
        self.assertIn("Mira: North.", joined)
        self.assertIn("Welcome, Rin.", joined)
        self.assertIn("Hello, Mira.", joined)
        self.assertNotIn("Northstar", joined)
        warning_codes = {item["code"] for item in result["warnings"]}
        self.assertIn("inactive_preset_explicitly_compiled", warning_codes)
        self.assertIn("nickname_single_chat_not_applied", warning_codes)
        self.assertIn("group_greetings_not_consumed", warning_codes)
        self.assertIn("character_book_budget_recursion_not_simulated", warning_codes)
        self.assertIn("single_chat_templates_not_consumed", warning_codes)

    def test_non_string_character_nickname_fails_closed(self) -> None:
        case = {
            "preset": base_preset(marker("chatHistory")),
            "character": character(nickname=123),
            "userInput": "Hello.",
            "model": "fixture-model",
        }

        with self.assertRaisesRegex(lab.LabError, "nickname must be a string"):
            lab.compile_case(case, Path.cwd())

    def test_preset_absolute_matches_retained_depth_zero_and_three_adapter_shape(self) -> None:
        absolute_zero = {
            "identifier": "absolute-zero",
            "content": "ABS ZERO",
            "role": "system",
            "type": "custom",
            "injectionPosition": "absolute",
            "injectionDepth": 0,
            "enabled": True,
            "active": True,
        }
        absolute_three = {**absolute_zero, "identifier": "absolute-three", "content": "ABS THREE", "injectionDepth": 3}
        case = {
            "preset": base_preset(marker("chatHistory"), absolute_zero, absolute_three),
            "character": character(),
            "history": [
                {"role": "user", "content": "u1"},
                {"role": "assistant", "content": "a1"},
                {"role": "user", "content": "u2"},
                {"role": "assistant", "content": "a2"},
            ],
            "userInput": "current",
        }

        result = lab.compile_case(case, Path.cwd())
        messages = result["request"]["messages"]
        self.assertEqual([item["role"] for item in messages], ["system", "user", "assistant", "user", "assistant", "user"])
        self.assertEqual(messages[3]["content"], "ABS THREE\n\nu2")
        self.assertEqual(messages[-1]["content"], "current\n\nABS ZERO")
        self.assertEqual(
            sum(item["code"] == "preset_absolute_adapter_merge" for item in result["warnings"]),
            2,
        )

    def test_secondary_probability_disabled_and_stateful_decisions_are_reported(self) -> None:
        entries = [
            {
                **constant("and-any", "YES", "lorebookAfter"),
                "strategy": "keyword",
                "keywords": ["gate"],
                "secondaryKeywords": ["blue"],
                "secondaryKeywordStrategy": "andAny",
                "scanDepth": 0,
                "matchWholeWord": False,
            },
            {
                **constant("and-all-miss", "NO", "lorebookAfter"),
                "strategy": "keyword",
                "keywords": ["gate"],
                "secondaryKeywords": ["blue", "red"],
                "secondaryKeywordStrategy": "andAll",
                "scanDepth": 0,
                "matchWholeWord": False,
            },
            {**constant("probability-zero", "NO", "lorebookAfter"), "probability": 0},
            {**constant("disabled", "NO", "lorebookAfter"), "enabled": False},
            {**constant("sticky", "STATE", "lorebookAfter"), "sticky": 2},
        ]
        case = {
            "preset": base_preset(marker("worldInfoAfter"), marker("chatHistory")),
            "character": character(),
            "worldbooks": [worldbook(entries)],
            "greeting": False,
            "userInput": "blue gate",
        }
        result = lab.compile_case(case, Path.cwd())
        decisions = {item["entry"]: item["status"] for item in result["worldbookDecisions"]}
        self.assertEqual(
            decisions,
            {
                "and-any": "triggered",
                "and-all-miss": "secondary_miss",
                "probability-zero": "probability_miss",
                "disabled": "disabled",
                "sticky": "triggered",
            },
        )
        self.assertIn("stateful_timing_approximated", {item["code"] for item in result["warnings"]})

    def test_primary_miss_is_not_misreported_as_secondary_miss(self) -> None:
        entry = {
            **constant("primary-miss", "NO", "lorebookAfter"),
            "strategy": "keyword",
            "keywords": ["missing-primary"],
            "secondaryKeywords": ["blue"],
            "secondaryKeywordStrategy": "andAny",
            "scanDepth": 0,
            "matchWholeWord": False,
        }
        result = lab.compile_case(
            {
                "preset": base_preset(marker("worldInfoAfter"), marker("chatHistory")),
                "character": character(),
                "worldbooks": [worldbook([entry])],
                "greeting": False,
                "userInput": "blue only",
            },
            Path.cwd(),
        )
        self.assertEqual(result["worldbookDecisions"][0]["status"], "keyword_miss")

    def test_camel_case_character_card_original_override_and_variable_macro(self) -> None:
        main = {
            "identifier": "main",
            "content": "ORIGINAL",
            "role": "system",
            "type": "builtin",
            "injectionPosition": "relative",
            "forbidOverrides": False,
            "enabled": True,
            "active": True,
        }
        card = {
            "name": "Camel",
            "description": "Desc",
            "firstMes": "Hello {{user}}",
            "mesExample": "",
            "systemPrompt": "OVERRIDE {{original}} {{getvar::tone}}",
        }
        case = {
            "preset": {**base_preset(marker("chatHistory")), "entries": [main, marker("chatHistory")]},
            "character": card,
            "persona": {"name": "Person", "description": ""},
            "userInput": "go",
        }
        result = lab.compile_case(case, Path.cwd())
        self.assertEqual(result["selectedGreeting"]["sourceContent"], "Hello {{user}}")
        self.assertEqual(result["selectedGreeting"]["renderedContent"], "Hello Person")
        self.assertIn("OVERRIDE ORIGINAL", result["request"]["messages"][0]["content"])
        self.assertNotIn("{{getvar::tone}}", result["request"]["messages"][0]["content"])
        self.assertNotIn("unresolved_macros", {item["code"] for item in result["warnings"]})
        self.assertIn("card_prompt_override_approximation", {item["code"] for item in result["warnings"]})

    def test_ejs_condition_loop_constants_and_emitted_macro_render_in_order(self) -> None:
        prompt = {
            "identifier": "ejs-main",
            "content": (
                '<% const mode = getvar("mode", "alpha"); setvar("mode", mode); incvar("turn"); %>'
                '<% if (mode === "alpha") { %>ALPHA:<%- "{{char}}" %>/<%- userName %>:'
                '<% for (let i = 1; i <= 3; i++) { print(i); } %><% } %>'
            ),
            "role": "system",
            "type": "custom",
            "injectionPosition": "relative",
            "enabled": True,
            "active": True,
        }
        result = lab.compile_case(
            {
                "preset": base_preset(prompt, marker("chatHistory")),
                "character": character(),
                "persona": {"name": "Rin", "description": ""},
                "greeting": False,
                "userInput": "hello",
                "ejs": {"variables": {"chat": {}, "global": {}}},
            },
            Path.cwd(),
        )
        content = request_text(result)
        self.assertIn("ALPHA:Mira/Rin:123", content)
        self.assertNotIn("<%", content)
        self.assertNotIn("{{char}}", content)
        self.assertEqual(result["ejs"]["variables"]["final"]["chat"], {"mode": "alpha", "turn": 1})
        self.assertEqual(result["ejs"]["fieldsRendered"], 1)
        self.assertEqual(result["ejs"]["unresolvedSources"], [])

    def test_ejs_and_variable_macros_share_chat_and_global_state(self) -> None:
        first = {
            "identifier": "seed",
            "content": '<% setvar("player.hp", 40); setvar("score", 2, {scope: "global"}); %>seed',
            "role": "system",
            "type": "custom",
            "injectionPosition": "relative",
            "enabled": True,
            "active": True,
        }
        second = {
            **first,
            "identifier": "macros",
            "content": "{{incvar::player.hp}}{{addglobalvar::score::3}}HP={{getvar::player.hp}} G={{getglobalvar::score}}",
        }
        third = {
            **first,
            "identifier": "read-back",
            "content": '<%- getvar("player.hp") %>/<%- getvar("score") %>',
        }
        result = lab.compile_case(
            {
                "preset": base_preset(first, second, third, marker("chatHistory")),
                "character": character(),
                "greeting": False,
                "userInput": "go",
            },
            Path.cwd(),
        )
        joined = request_text(result)
        self.assertIn("HP=41 G=5", joined)
        self.assertIn("41/5", joined)
        self.assertEqual(result["ejs"]["variables"]["final"], {"chat": {"player": {"hp": 41}}, "global": {"score": 5}})
        self.assertTrue(result["ejs"]["macroVariableTrace"])

    def test_persona_character_fields_examples_and_selected_greeting_execute_ejs(self) -> None:
        card = character(
            description='<% setvar("card_ready", true) %>Card <%- charName %> / <%- "{{user}}" %>',
            personality='<% if (getvar("card_ready") === true) { %>Ready<% } %>',
            mes_example='<START>\n<%- "{{char}}" %>: Example rendered',
            first_mes='<% if (getvar("card_ready") === true) { %>Greeting <%- userName %><% } %>',
        )
        result = lab.compile_case(
            {
                "preset": base_preset(
                    marker("personaDescription"),
                    marker("charDescription"),
                    marker("charPersonality"),
                    marker("dialogueExamples"),
                    marker("chatHistory"),
                ),
                "character": card,
                "persona": {
                    "name": "Rin",
                    "description": '<% print("Persona ") %><%- "{{user}}" %>',
                },
                "userInput": "go",
            },
            Path.cwd(),
        )
        prompt = request_text(result)
        self.assertIn("Persona: Persona Rin", prompt)
        self.assertIn("Description: Card Mira / Rin", prompt)
        self.assertIn("Personality: Ready", prompt)
        self.assertIn("Mira: Example rendered", prompt)
        self.assertEqual(result["selectedGreeting"]["renderedContent"], "Greeting Rin")
        self.assertFalse(any("<%" in item["content"] for item in result["request"]["messages"]))
        sources = {item["source"] for item in result["ejs"]["fieldTrace"]}
        self.assertTrue(
            {
                "persona.description",
                "character.description",
                "character.personality",
                "character.mes_example",
                "character.greeting",
            }.issubset(sources)
        )

    def test_ejs_tags_escaping_literal_regions_and_newline_trim(self) -> None:
        prompt = {
            "identifier": "syntax",
            "content": (
                'A<%- "1<2" %>|<%= "1<2" %>|<%# hidden %>'
                '<%% raw %%>|<#escape-ejs><% untouched %></#escape-ejs>\n'
                '<% print("B") -%>\nC'
            ),
            "role": "system",
            "type": "custom",
            "injectionPosition": "relative",
            "enabled": True,
            "active": True,
        }
        result = lab.compile_case(
            {
                "preset": base_preset(prompt, marker("chatHistory")),
                "character": character(),
                "greeting": False,
                "userInput": "go",
            },
            Path.cwd(),
        )
        content = request_text(result)
        self.assertIn("A1<2|1&lt;2|<% raw %>|<% untouched %>\nBC", content)

    def test_ejs_error_falls_back_whole_field_and_rolls_back_state(self) -> None:
        source = '<% setvar("kept", 1); missingFunction(); %>BROKEN {{char}}'
        prompt = {
            "identifier": "broken",
            "content": source,
            "role": "system",
            "type": "custom",
            "injectionPosition": "relative",
            "enabled": True,
            "active": True,
        }
        result = lab.compile_case(
            {
                "preset": base_preset(prompt, marker("chatHistory")),
                "character": character(),
                "greeting": False,
                "userInput": "go",
            },
            Path.cwd(),
        )
        rendered = request_text(result)
        self.assertIn(
            '<% setvar("kept", 1); missingFunction(); %>BROKEN Mira',
            rendered,
        )
        self.assertNotIn("BROKEN {{char}}", rendered)
        self.assertEqual(result["ejs"]["variables"]["final"]["chat"], {})
        self.assertEqual(result["ejs"]["unresolvedSources"], ["preset:broken"])
        self.assertIn("ejs_render_error_fallback", {item["code"] for item in result["warnings"]})

    def test_worldbook_ejs_keyword_and_content_are_rendered(self) -> None:
        entry = {
            **constant("ejs-lore", '<% if (/dragon/i.test(lastUserMessage)) { %>LORE <%- "{{user}}" %><% } %>', "lorebookAfter"),
            "strategy": "keyword",
            "keywords": ['<%- "dragon" %>'],
            "scanDepth": 0,
            "matchWholeWord": False,
        }
        result = lab.compile_case(
            {
                "preset": base_preset(marker("worldInfoAfter"), marker("chatHistory")),
                "character": character(),
                "persona": {"name": "Rin", "description": ""},
                "worldbooks": [worldbook([entry])],
                "greeting": False,
                "userInput": "A dragon arrives",
            },
            Path.cwd(),
        )
        self.assertEqual(result["worldbookDecisions"][0]["matchedKeywords"], ["dragon"])
        self.assertIn("LORE Rin", request_text(result))
        self.assertEqual(result["ejs"]["fieldsRendered"], 2)

    def test_complex_prompt_javascript_subset_and_lodash_helpers(self) -> None:
        prompt = {
            "identifier": "complex",
            "content": (
                '<% const cfg = JSON.parse(getvar("control", "{\\"style\\":\\"film\\"}")); '
                'const rain = /rain/i.test(lastUserMessage); const year = new Date("2020-01-02T00:00:00Z").getUTCFullYear(); '
                'function label(value) { return value.toUpperCase(); } '
                'const data = {shots: [{name: "wide"}]}; _.set(data, "shots[0].year", year); %>'
                '<% if (rain && cfg.style === "film" && _.has(data, "shots.0.year")) { %>'
                '<%- label(_.get(data, "shots.0.name")) %>:<%- _.get(data, "shots[0].year") %><% } %>'
            ),
            "role": "system",
            "type": "custom",
            "injectionPosition": "relative",
            "enabled": True,
            "active": True,
        }
        result = lab.compile_case(
            {
                "preset": base_preset(prompt, marker("chatHistory")),
                "character": character(),
                "greeting": False,
                "userInput": "rain on glass",
            },
            Path.cwd(),
        )
        self.assertIn("WIDE:2020", request_text(result))

    def test_ejs_policy_and_timeout_fail_closed(self) -> None:
        for identifier, source in (
            ("policy", "<%- process.env.HOME %>"),
            ("worker-internal", "<%- __tavoLabState.chat %>"),
            ("timeout", "<% while (true) {} %>"),
        ):
            with self.subTest(identifier=identifier):
                prompt = {
                    "identifier": identifier,
                    "content": source,
                    "role": "system",
                    "type": "custom",
                    "injectionPosition": "relative",
                    "enabled": True,
                    "active": True,
                }
                result = lab.compile_case(
                    {
                        "preset": base_preset(prompt, marker("chatHistory")),
                        "character": character(),
                        "greeting": False,
                        "userInput": "go",
                        "ejs": {"timeoutMs": 25},
                    },
                    Path.cwd(),
                )
                self.assertIn(source, request_text(result))
                self.assertEqual(result["ejs"]["unresolvedSources"], [f"preset:{identifier}"])

    def test_runtime_chat_ejs_is_literal_but_macros_still_run(self) -> None:
        runtime = '<% setvar("unsafe", 1); %>{{setvar::safe::2}}hello'
        result = lab.compile_case(
            {
                "preset": base_preset(marker("chatHistory")),
                "character": character(),
                "greeting": False,
                "userInput": runtime,
            },
            Path.cwd(),
        )
        self.assertEqual(
            result["request"]["messages"][-1]["content"],
            '[Start of current chat]\n\n<% setvar("unsafe", 1); %>hello',
        )
        self.assertEqual(result["ejs"]["variables"]["final"]["chat"], {"safe": 2})
        self.assertEqual(result["ejs"]["unresolvedSources"], [])
        self.assertIn("runtime_ejs_literal", {item["code"] for item in result["warnings"]})

    def test_out_of_range_at_depth_is_omitted(self) -> None:
        case = {
            "preset": base_preset(marker("chatHistory")),
            "character": character(),
            "worldbooks": [worldbook([constant("too-deep", "OMIT", "atDepth", injectionDepth=3)])],
            "greeting": False,
            "userInput": "one message",
        }
        result = lab.compile_case(case, Path.cwd())
        self.assertNotIn("OMIT", json.dumps(result["request"]))
        self.assertIn("absolute_depth_out_of_range", {item["code"] for item in result["warnings"]})
        final_trace = [item for item in result["assemblyTrace"] if item["source"].endswith(":too-deep")][-1]
        self.assertEqual(final_trace["status"], "absolute-omitted")

    def test_tavo_exported_prompt_order_matches_retained_relative_role_shape(self) -> None:
        raw_preset = {
            "new_chat_prompt": "[Start a new Chat]",
            "new_example_chat_prompt": "[Example Chat]",
            "personality_format": "{{personality}}",
            "scenario_format": "{{scenario}}",
            "wi_format": "{0}",
            "prompts": [
                {
                    "identifier": "main",
                    "name": "Main Prompt",
                    "content": "MAIN {{char}} / {{user}}",
                    "system_prompt": True,
                    "marker": False,
                    "role": "system",
                    "injection_position": 0,
                    "injection_depth": 4,
                    "forbid_overrides": False,
                },
                {"identifier": "personaDescription", "name": "Persona", "content": "", "system_prompt": True, "marker": True},
                {"identifier": "charDescription", "name": "Character", "content": "", "system_prompt": True, "marker": True},
                {"identifier": "chatHistory", "name": "History", "content": "", "system_prompt": True, "marker": True},
                {
                    "identifier": "style",
                    "name": "Style",
                    "content": "STYLE {{user}}",
                    "system_prompt": False,
                    "marker": False,
                    "role": "system",
                    "injection_position": 0,
                    "injection_depth": 4,
                    "forbid_overrides": False,
                },
            ],
            "prompt_order": [
                {
                    "character_id": 100001,
                    "order": [
                        {"identifier": "main", "enabled": True},
                        {"identifier": "personaDescription", "enabled": True},
                        {"identifier": "charDescription", "enabled": True},
                        {"identifier": "chatHistory", "enabled": True},
                        {"identifier": "style", "enabled": True},
                    ],
                }
            ],
        }
        case = {
            "preset": raw_preset,
            "character": character(),
            "persona": {"name": "Rin", "description": "A patient tester."},
            "userInput": "hello",
        }
        result = lab.compile_case(case, Path.cwd())

        self.assertEqual(
            [item["role"] for item in result["request"]["messages"]],
            ["system", "assistant", "user"],
        )
        self.assertEqual(
            result["request"]["messages"][0]["content"],
            "MAIN Mira / Rin\n\nA patient tester.\n\nA careful cartographer.\n\n[Start a new Chat]",
        )
        self.assertEqual(result["request"]["messages"][1]["content"], "Welcome, Rin.")
        self.assertEqual(result["request"]["messages"][2]["content"], "hello\n\nSTYLE Rin")
        self.assertEqual(
            result["compatibility"]["presetInput"],
            "tavo-exported-prompts-prompt_order-relative-v1",
        )
        self.assertIn(
            "tavo_exported_preset_normalized",
            {item["code"] for item in result["warnings"]},
        )

    def test_ambiguous_prompt_order_preset_fails_closed(self) -> None:
        case = {
            "preset": {"prompts": [], "prompt_order": []},
            "character": character(),
            "userInput": "go",
        }
        with self.assertRaises(lab.LabError) as raised:
            lab.compile_case(case, Path.cwd())
        self.assertEqual(raised.exception.code, "ambiguous_prompt_order")

    def test_non_relative_prompt_order_entry_fails_closed(self) -> None:
        case = {
            "preset": {
                "prompts": [
                    {
                        "identifier": "absolute",
                        "content": "ABS",
                        "system_prompt": False,
                        "marker": False,
                        "role": "system",
                        "injection_position": 1,
                        "injection_depth": 1,
                        "forbid_overrides": False,
                    }
                ],
                "prompt_order": [
                    {"character_id": 100001, "order": [{"identifier": "absolute", "enabled": True}]}
                ],
            },
            "character": character(),
            "userInput": "go",
        }
        with self.assertRaises(lab.LabError) as raised:
            lab.compile_case(case, Path.cwd())
        self.assertEqual(raised.exception.code, "unsupported_prompt_order_injection")

    def test_sensitive_model_parameters_are_rejected(self) -> None:
        sensitive_key = "api" + "_key"
        case = {
            "preset": base_preset(marker("chatHistory")),
            "character": character(),
            "userInput": "go",
            "model": {"id": "x", "parameters": {sensitive_key: "must-not-enter-body"}},
        }
        with self.assertRaises(lab.LabError) as raised:
            lab.compile_case(case, Path.cwd())
        self.assertEqual(raised.exception.code, "sensitive_parameter")

    def test_normalized_sensitive_parameter_names_are_rejected(self) -> None:
        for key in ("api-key", "API Key", "x.api key", "client.secret"):
            with self.subTest(key=key), self.assertRaises(lab.LabError) as raised:
                lab.compile_case(
                    {
                        "preset": base_preset(marker("chatHistory")),
                        "character": character(),
                        "greeting": False,
                        "userInput": "hello",
                        "model": {"id": "x", "parameters": {key: "secret"}},
                    },
                    Path.cwd(),
                )
            self.assertEqual(raised.exception.code, "sensitive_parameter")

    def test_nonfinite_json_values_and_unknown_schema_fail_closed(self) -> None:
        with self.assertRaises(lab.LabError) as raised:
            lab.compile_case(
                {
                    "schemaVersion": "9.9",
                    "preset": base_preset(marker("chatHistory")),
                    "character": character(),
                    "greeting": False,
                    "userInput": "hello",
                },
                Path.cwd(),
            )
        self.assertEqual(raised.exception.code, "unsupported_schema_version")
        with self.assertRaises(lab.LabError) as raised:
            lab.compile_case(
                {
                    "schemaVersion": "2.3",
                    "preset": base_preset(marker("chatHistory")),
                    "character": character(),
                    "greeting": False,
                    "userInput": "hello",
                    "model": {"id": "x", "parameters": {"temperature": float("nan")}},
                },
                Path.cwd(),
            )
        self.assertEqual(raised.exception.code, "invalid_json_value")

    def test_javascript_replacement_supports_prefix_suffix_and_named_groups(self) -> None:
        match = re.search(r"(?P<word>b)", "abc")
        self.assertIsNotNone(match)
        assert match is not None
        self.assertEqual(
            lab.javascript_replacement(match, "$$|$&|$`|$'|$1|$<word>"),
            "$|b|a|c|b|b",
        )

    def test_javascript_named_capture_syntax_is_translated_for_replacement(self) -> None:
        pattern, _global = lab.parse_regex_pattern(r"/(?<word>b)/g", "test")
        match = pattern.search("abc")
        self.assertIsNotNone(match)
        assert match is not None
        self.assertEqual(lab.javascript_replacement(match, "$<word>"), "b")

    def test_nested_sensitive_model_parameters_are_rejected(self) -> None:
        sensitive_key = "api" + "_key"
        case = {
            "preset": base_preset(marker("chatHistory")),
            "character": character(),
            "userInput": "go",
            "model": {
                "id": "x",
                "parameters": {"extra_body": {sensitive_key: "must-not-enter-body"}},
            },
        }
        with self.assertRaises(lab.LabError) as raised:
            lab.compile_case(case, Path.cwd())
        self.assertEqual(raised.exception.code, "sensitive_parameter")

    def test_invalid_preset_entry_type_is_rejected(self) -> None:
        invalid = {
            "identifier": "invalid-type",
            "content": "must not be injected",
            "role": "system",
            "type": "banana",
            "injectionPosition": "relative",
            "enabled": True,
            "active": True,
        }
        case = {
            "preset": base_preset(invalid, marker("chatHistory")),
            "character": character(),
            "userInput": "go",
        }
        with self.assertRaises(lab.LabError) as raised:
            lab.compile_case(case, Path.cwd())
        self.assertEqual(raised.exception.code, "invalid_preset")

    def test_string_boolean_does_not_enable_preset_or_worldbook_entries(self) -> None:
        bad_preset = base_preset(marker("chatHistory"))
        bad_preset["entries"][0]["enabled"] = "false"
        with self.assertRaises(lab.LabError) as preset_error:
            lab.compile_case(
                {"preset": bad_preset, "character": character(), "userInput": "go"},
                Path.cwd(),
            )
        self.assertEqual(preset_error.exception.code, "invalid_boolean")

        bad_world = constant("bad-bool", "NO", "lorebookAfter")
        bad_world["enabled"] = "false"
        with self.assertRaises(lab.LabError) as world_error:
            lab.compile_case(
                {
                    "preset": base_preset(marker("worldInfoAfter"), marker("chatHistory")),
                    "character": character(),
                    "worldbooks": [worldbook([bad_world])],
                    "userInput": "go",
                },
                Path.cwd(),
            )
        self.assertEqual(world_error.exception.code, "invalid_boolean")

    def test_unknown_worldbook_position_warns_instead_of_claiming_exact_mapping(self) -> None:
        entry = constant("legacy-position", "LEGACY", "lorebookAfter")
        entry.pop("injectionPosition")
        entry["position"] = 4
        result = lab.compile_case(
            {
                "preset": base_preset(marker("worldInfoAfter"), marker("chatHistory")),
                "character": character(),
                "worldbooks": [worldbook([entry])],
                "greeting": False,
                "userInput": "go",
            },
            Path.cwd(),
        )
        self.assertIn("unsupported_worldbook_position", {item["code"] for item in result["warnings"]})
        self.assertIn("LEGACY", request_text(result))

    def test_multiturn_compile_carries_history_ejs_state_and_keyword_window(self) -> None:
        counter_prompt = {
            "identifier": "turn-counter",
            "content": '<% incvar("turn") %>TURN=<%- getvar("turn") %>',
            "role": "system",
            "type": "custom",
            "injectionPosition": "relative",
            "enabled": True,
            "active": True,
        }
        keyword_entry = {
            **constant("window-keyword", "WINDOW_HIT", "lorebookAfter"),
            "strategy": "keyword",
            "keywords": ["window-key"],
            "secondaryKeywords": [],
            "secondaryKeywordStrategy": "none",
            "scanDepth": 2,
            "caseSensitive": False,
            "matchWholeWord": False,
        }
        case = {
            "preset": base_preset(
                counter_prompt,
                marker("worldInfoAfter"),
                marker("chatHistory"),
            ),
            "character": character(),
            "worldbooks": [worldbook([keyword_entry])],
            "greeting": False,
            "turns": [
                {
                    "label": "trigger",
                    "userInput": "window-key first",
                    "assistantResponse": "assistant-one",
                },
                {
                    "label": "carry",
                    "userInput": "second",
                    "assistantResponse": "assistant-two",
                },
                {"label": "expire", "userInput": "third"},
            ],
        }

        result = lab.compile_session(case, Path.cwd())

        self.assertEqual(result["mode"], "compile-session")
        self.assertEqual(result["status"], "compiled")
        self.assertEqual(result["session"]["turnCount"], 3)
        self.assertEqual(
            [turn["worldbookDecisions"][0]["status"] for turn in result["turns"]],
            ["triggered", "keyword_miss", "keyword_miss"],
        )
        for index, turn in enumerate(result["turns"], start=1):
            body = json.dumps(turn["request"], ensure_ascii=False)
            self.assertIn(f"TURN={index}", body)
            self.assertEqual(turn["ejs"]["variables"]["final"]["chat"]["turn"], index)
        second_body = json.dumps(result["turns"][1]["request"], ensure_ascii=False)
        third_body = json.dumps(result["turns"][2]["request"], ensure_ascii=False)
        self.assertIn("window-key first", second_body)
        self.assertIn("assistant-one", second_body)
        self.assertIn("assistant-two", third_body)
        self.assertEqual(result["finalEjsVariables"]["chat"]["turn"], 3)
        self.assertEqual(
            [item["role"] for item in result["finalHistory"]],
            ["user", "assistant", "user", "assistant", "user"],
        )

    def test_multiturn_fallback_rolls_back_field_state_and_checker_persists(self) -> None:
        failing = constant(
            "fallback",
            '<% setvar("mustRollback", "LEAKED"); missingFunction(); %>RAW_FALLBACK',
            "lorebookAfter",
        )
        checker = constant(
            "checker",
            (
                '<% incvar("checkerTurn") %>'
                'ROLLBACK=<%- getvar("mustRollback", "ROLLED_BACK") %> '
                'CHECKER=<%- getvar("checkerTurn") %>'
            ),
            "lorebookAfter",
        )
        case = {
            "preset": base_preset(marker("worldInfoAfter"), marker("chatHistory")),
            "character": character(),
            "worldbooks": [worldbook([failing, checker])],
            "greeting": False,
            "turns": [
                {"userInput": "one", "assistantResponse": "reply-one"},
                {"userInput": "two"},
            ],
        }

        result = lab.compile_session(case, Path.cwd())

        self.assertEqual(result["status"], "compiled")
        for index, turn in enumerate(result["turns"], start=1):
            text = json.dumps(turn["request"], ensure_ascii=False)
            self.assertIn("RAW_FALLBACK", text)
            self.assertIn("ROLLBACK=ROLLED_BACK", text)
            self.assertIn(f"CHECKER={index}", text)
            self.assertTrue(turn["ejs"]["unresolvedSources"])
        self.assertNotIn("mustRollback", result["finalEjsVariables"]["chat"])
        self.assertEqual(result["finalEjsVariables"]["chat"]["checkerTurn"], 2)

    def test_multiturn_compile_requires_assistant_fixture_before_next_turn(self) -> None:
        case = {
            "preset": base_preset(marker("chatHistory")),
            "character": character(),
            "greeting": False,
            "turns": [
                {"userInput": "one"},
                {"userInput": "two"},
            ],
        }
        with self.assertRaises(lab.LabError) as raised:
            lab.compile_session(case, Path.cwd())
        self.assertEqual(raised.exception.code, "missing_assistant_response")

    def test_regex_send_and_display_keep_provider_persistent_visible_surfaces_separate(self) -> None:
        rules = regex_group(
            "surface split",
            regex_entry(
                "user-send",
                "/SEND_RAW/g",
                "SEND_MODEL",
                placements=["user"],
                timing="send",
            ),
            regex_entry(
                "char-display",
                "/DISPLAY_RAW/g",
                "DISPLAY_VISIBLE",
                placements=["char"],
                timing="display",
            ),
        )
        result = lab.compile_case(
            {
                "preset": base_preset(marker("chatHistory")),
                "character": character(),
                "greeting": False,
                "history": [{"role": "assistant", "content": "DISPLAY_RAW"}],
                "userInput": "SEND_RAW",
                "regexes": [rules],
            },
            Path.cwd(),
        )

        self.assertEqual(result["persistentHistory"][-1]["content"], "DISPLAY_RAW")
        self.assertEqual(result["visibleHistory"][-1]["content"], "DISPLAY_VISIBLE")
        self.assertEqual(result["persistentUserInput"], "SEND_RAW")
        self.assertIn("SEND_MODEL", request_text(result))
        self.assertNotIn("SEND_RAW", request_text(result))
        self.assertIn("DISPLAY_RAW", request_text(result))
        self.assertNotIn("DISPLAY_VISIBLE", request_text(result))
        self.assertEqual(len(result["regex"]["sendTrace"]), 1)
        self.assertEqual(len(result["regex"]["displayTrace"]), 1)

    def test_regex_receive_persists_then_display_changes_only_visible_response(self) -> None:
        rules = regex_group(
            "receive display",
            regex_entry(
                "receive",
                "/RESPONSE_RAW/g",
                "RESPONSE_PERSIST",
                placements=["char"],
                timing="receive",
            ),
            regex_entry(
                "display",
                "/RESPONSE_PERSIST/g",
                "RESPONSE_VISIBLE",
                placements=["char"],
                timing="display",
            ),
        )
        result = lab.compile_session(
            {
                "preset": base_preset(marker("chatHistory")),
                "character": character(),
                "greeting": False,
                "regexes": [rules],
                "turns": [
                    {"userInput": "one", "assistantResponse": "RESPONSE_RAW"},
                    {"userInput": "two"},
                ],
            },
            Path.cwd(),
        )

        first = result["turns"][0]
        second_request = json.dumps(result["turns"][1]["request"], ensure_ascii=False)
        self.assertEqual(first["assistantResponse"], "RESPONSE_RAW")
        self.assertEqual(first["persistentAssistantResponse"], "RESPONSE_PERSIST")
        self.assertEqual(first["visibleAssistantResponse"], "RESPONSE_VISIBLE")
        self.assertIn("RESPONSE_PERSIST", second_request)
        self.assertNotIn("RESPONSE_RAW", second_request)
        self.assertNotIn("RESPONSE_VISIBLE", second_request)
        self.assertEqual(result["finalHistory"][-2]["content"], "RESPONSE_PERSIST")

    def test_regex_lorebook_ejs_macro_and_entry_order_compile_in_runtime_order(self) -> None:
        rules = regex_group(
            "ejs order lore",
            regex_entry(
                "ejs-raw-to-mid",
                '<%- "/EJS_RAW/g" %>',
                '<%- "EJS_MID={{char}}|{{user}}" %>',
                placements=["user"],
                timing="send",
                substitution="raw",
            ),
            regex_entry(
                "mid-to-final",
                "/EJS_MID=Mira\\|Rin/g",
                "EJS_FINAL",
                placements=["user"],
                timing="send",
            ),
            regex_entry(
                "lore-send",
                "/LORE_RAW/g",
                "LORE_MODEL",
                placements=["lorebook"],
                timing="send",
            ),
        )
        result = lab.compile_case(
            {
                "preset": base_preset(marker("worldInfoAfter"), marker("chatHistory")),
                "character": character(),
                "persona": {"name": "Rin", "description": ""},
                "worldbooks": [worldbook([constant("lore", "LORE_RAW", "lorebookAfter")])],
                "greeting": False,
                "userInput": "EJS_RAW",
                "regexes": [rules],
            },
            Path.cwd(),
        )

        prompt = request_text(result)
        self.assertIn("EJS_FINAL", prompt)
        self.assertNotIn("EJS_RAW", prompt)
        self.assertNotIn("EJS_MID", prompt)
        self.assertIn("LORE_MODEL", prompt)
        self.assertNotIn("LORE_RAW", prompt)
        self.assertNotIn("<%", prompt)
        self.assertNotIn("{{char}}", prompt)
        self.assertEqual([item["entry"] for item in result["regex"]["sendTrace"]], ["ejs-raw-to-mid", "mid-to-final"])
        self.assertEqual(result["regex"]["lorebookSendTrace"][0]["entry"], "lore-send")

    def test_regex_depth_zero_through_six_is_inclusive_and_counts_newest_first(self) -> None:
        history = [
            {"role": "user", "content": "RAW_6"},
            {"role": "assistant", "content": "RAW_5"},
            {"role": "user", "content": "RAW_4"},
            {"role": "assistant", "content": "RAW_3"},
            {"role": "user", "content": "RAW_2"},
            {"role": "assistant", "content": "RAW_1"},
        ]
        entries = [
            regex_entry(
                f"depth-{depth}",
                f"/RAW_{depth}/g",
                f"HIT_{depth}",
                placements=["user" if depth % 2 == 0 else "char"],
                timing="send",
                min_depth=depth,
                max_depth=depth,
            )
            for depth in range(7)
        ]
        result = lab.compile_case(
            {
                "preset": base_preset(marker("chatHistory")),
                "character": character(),
                "greeting": False,
                "history": history,
                "userInput": "RAW_0",
                "regexes": [regex_group("depth", *entries)],
            },
            Path.cwd(),
        )

        prompt = request_text(result)
        for depth in range(7):
            self.assertIn(f"HIT_{depth}", prompt)
            self.assertNotIn(f"RAW_{depth}", prompt)
        self.assertEqual(
            sorted(item["depth"] for item in result["regex"]["sendTrace"]),
            list(range(7)),
        )

    def test_regex_unverified_reasoning_trim_escaped_and_lore_depth_fail_closed(self) -> None:
        invalid_entries = [
            (
                regex_entry("reasoning", "/x/g", "y", placements=["reasoning"], timing="send"),
                "unsupported_regex_reasoning",
            ),
            (
                {**regex_entry("trim", "/x/g", "y", placements=["user"], timing="send"), "trimStrings": ["x"]},
                "unsupported_regex_trim_strings",
            ),
            (
                regex_entry("escaped", "/x/g", "y", placements=["user"], timing="send", substitution="escaped"),
                "unsupported_regex_escaped_substitution",
            ),
            (
                regex_entry("lore-depth", "/x/g", "y", placements=["lorebook"], timing="send", min_depth=0, max_depth=0),
                "unsupported_regex_lorebook_depth",
            ),
        ]
        for entry, expected_code in invalid_entries:
            with self.subTest(expected_code=expected_code):
                with self.assertRaises(lab.LabError) as raised:
                    lab.compile_case(
                        {
                            "preset": base_preset(marker("chatHistory")),
                            "character": character(),
                            "greeting": False,
                            "userInput": "x",
                            "regexes": [regex_group("invalid", entry)],
                        },
                        Path.cwd(),
                    )
                self.assertEqual(raised.exception.code, expected_code)


class PromptLabProviderAdapterTests(unittest.TestCase):
    def test_supported_json_response_shapes_extract_text(self) -> None:
        fixtures = [
            ({"choices": [{"message": {"content": "chat"}}]}, "chat"),
            (
                {"choices": [{"message": {"content": [{"type": "text", "text": "array"}]}}]},
                "array",
            ),
            ({"choices": [{"text": "completion"}]}, "completion"),
            ({"output_text": "responses-shortcut"}, "responses-shortcut"),
            (
                {"output": [{"type": "message", "content": [{"type": "output_text", "text": "responses"}]}]},
                "responses",
            ),
            ({"content": [{"type": "text", "text": "anthropic"}]}, "anthropic"),
        ]
        for body, expected in fixtures:
            with self.subTest(body=body):
                text, source, seen = lab.extract_json_response_text(body)
                self.assertEqual(text, expected)
                self.assertIsNotNone(source)
                self.assertTrue(seen)

    def test_sse_and_malformed_json_recovery_are_conservative(self) -> None:
        text, count, seen, error_seen = lab.extract_sse_response_text(
            'data: {"choices":[{"delta":{"content":"one"}}]}\n\n'
            'data: {"type":"response.output_text.delta","delta":" two"}\n\n'
            "data: [DONE]\n"
        )
        self.assertEqual(text, "one two")
        self.assertEqual(count, 2)
        self.assertTrue(seen)
        self.assertFalse(error_seen)
        self.assertEqual(
            lab.extract_malformed_json_text(
                '{"choices":[{"message":{"content":"recovered"}}] trailing'
            ),
            "recovered",
        )
        self.assertIsNone(
            lab.extract_malformed_json_text('{"error":{"text":"do not accept"}')
        )
        self.assertIsNone(
            lab.extract_malformed_json_text(
                '{"request":{"messages":[{"content":"PROMPT_ECHO"}]},"choices":['
            )
        )
        text, _count, seen, error_seen = lab.extract_sse_response_text(
            'data: {"error":"rate limit"\n\ndata: [DONE]\n'
        )
        self.assertIsNone(text)
        self.assertFalse(seen)
        self.assertFalse(error_seen)
        text, _count, seen, error_seen = lab.extract_sse_response_text(
            'data: {"choices":[{"delta":{"content":"partial"}}]}\n\n'
            'data: {"error":{"message":"upstream reset"}}\n\n'
            'data: [DONE]\n'
        )
        self.assertEqual(text, "partial")
        self.assertTrue(seen)
        self.assertTrue(error_seen)
        for error_event in (
            'data: {"choices":[{"delta":{"content":"partial"}}]}\n\n'
            'event: error\ndata: upstream reset\n\n',
            'data: {"choices":[{"delta":{"content":"partial"}}]}\n\n'
            'data: {"type":"error","message":"upstream reset"}\n\n',
        ):
            with self.subTest(error_event=error_event):
                text, _count, seen, error_seen = lab.extract_sse_response_text(error_event)
                self.assertEqual(text, "partial")
                self.assertTrue(seen)
                self.assertTrue(error_seen)

    def test_provider_diagnostic_redacts_normalized_credential_keys(self) -> None:
        sensitive_key = "api" + "-key"
        fixture_value = "private-fixture-value"
        diagnostic = lab.provider_diagnostic(
            status=200,
            content_type="application/json",
            raw=json.dumps({sensitive_key: fixture_value, "message": "safe"}).encode(),
            api_key=None,
        )
        serialized = json.dumps(diagnostic)
        self.assertNotIn(fixture_value, serialized)
        self.assertIn("<redacted>", serialized)

    def test_run_one_turn_failure_does_not_commit_history_or_state(self) -> None:
        case = {
            "schemaVersion": "2.3",
            "preset": base_preset(marker("chatHistory")),
            "character": character(),
            "greeting": False,
            "userInput": "must-not-persist",
            "model": "x",
        }
        failure = lab.ProviderResponseError(
            "empty_provider_response",
            "empty",
            {
                "httpStatus": 200,
                "contentType": "application/json",
                "responseBytes": 2,
                "responseSha256": "x",
                "preview": "{}",
            },
        )
        with mock.patch.object(lab, "call_model", side_effect=failure):
            result, next_state = lab.run_one_turn(
                case,
                Path.cwd(),
                model_override=None,
                base_url="http://127.0.0.1:1",
                api_key=None,
                timeout=2,
                allow_insecure_http=False,
                allow_unrendered_ejs=False,
                state=None,
                user_input_override=None,
            )
        self.assertEqual(result["status"], "provider-failed")
        self.assertEqual(result["error"]["code"], "empty_provider_response")
        self.assertFalse(result["stateCommitted"])
        self.assertIsNone(next_state)

    def test_batch_failure_does_not_append_failed_user_message(self) -> None:
        initial_history = [{"role": "assistant", "content": "already committed"}]
        case = {
            "schemaVersion": "2.3",
            "preset": base_preset(marker("chatHistory")),
            "character": character(),
            "greeting": False,
            "history": initial_history,
            "turns": [
                {"userInput": "must-not-persist"},
                {"userInput": "must-not-run"},
            ],
            "model": "x",
        }
        failure = lab.ProviderResponseError(
            "empty_provider_response",
            "empty",
            {
                "httpStatus": 200,
                "contentType": "application/json",
                "responseBytes": 2,
                "responseSha256": "x",
                "preview": "{}",
            },
        )
        with mock.patch.object(lab, "call_model", side_effect=failure):
            result = lab.run_session(
                case,
                Path.cwd(),
                model_override=None,
                base_url="http://127.0.0.1:1",
                api_key=None,
                timeout=2,
                allow_insecure_http=False,
                allow_unrendered_ejs=False,
            )
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["error"]["code"], "empty_provider_response")
        self.assertEqual(result["finalHistory"], initial_history)

    def test_run_one_turn_commits_exactly_one_turn_for_agent_review(self) -> None:
        case = {
            "schemaVersion": "2.3",
            "preset": base_preset(marker("chatHistory")),
            "character": character(),
            "greeting": False,
            "userInput": "first",
            "model": "x",
        }
        replies = iter(("reply-one", "reply-two"))

        def fake_call(*_args: object, **_kwargs: object) -> tuple[dict, str, str, dict]:
            reply = next(replies)
            return (
                {"choices": [{"message": {"content": reply}}]},
                reply,
                "HTTP 200",
                {
                    "source": "choices[0].message.content",
                    "contentType": "application/json",
                    "responseBytes": len(reply),
                    "warnings": [],
                },
            )

        with mock.patch.object(lab, "call_model", side_effect=fake_call):
            first, state = lab.run_one_turn(
                case,
                Path.cwd(),
                model_override=None,
                base_url="http://127.0.0.1:1",
                api_key=None,
                timeout=2,
                allow_insecure_http=False,
                allow_unrendered_ejs=False,
                state=None,
                user_input_override=None,
            )
            self.assertIsNotNone(state)
            assert state is not None
            second, next_state = lab.run_one_turn(
                case,
                Path.cwd(),
                model_override=None,
                base_url="http://127.0.0.1:1",
                api_key=None,
                timeout=2,
                allow_insecure_http=False,
                allow_unrendered_ejs=False,
                state=state,
                user_input_override="second",
            )
        self.assertEqual(first["turnIndex"], 1)
        self.assertEqual(second["turnIndex"], 2)
        self.assertIsNotNone(next_state)
        self.assertIn("reply-one", json.dumps(second["request"]))
        self.assertIn("second", json.dumps(second["request"]))

    def test_continued_run_turn_requires_explicit_next_input(self) -> None:
        case = {
            "schemaVersion": "2.3",
            "preset": base_preset(marker("chatHistory")),
            "character": character(),
            "greeting": False,
            "userInput": "first",
            "model": "x",
        }
        state = lab.make_turn_state(
            case_fingerprint=lab.resolved_case_fingerprint(case, Path.cwd()),
            turn_index=1,
            history=[
                {"role": "user", "content": "first"},
                {"role": "assistant", "content": "reply"},
            ],
            ejs_variables={"chat": {}, "global": {}},
            budget_limit=lab.MAX_SESSION_BUDGET_BYTES,
            budget_used=10,
        )
        with self.assertRaises(lab.LabError) as raised:
            lab.run_one_turn(
                case,
                Path.cwd(),
                model_override=None,
                base_url="http://127.0.0.1:1",
                api_key=None,
                timeout=2,
                allow_insecure_http=False,
                allow_unrendered_ejs=False,
                state=state,
                user_input_override=None,
            )
        self.assertEqual(raised.exception.code, "missing_turn_input")

    def test_run_turn_cli_writes_private_credential_free_state(self) -> None:
        with tempfile.TemporaryDirectory() as working:
            root = Path(working)
            case_path = root / "case.json"
            case_path.write_text(
                json.dumps(
                    {
                        "schemaVersion": "2.3",
                        "preset": base_preset(marker("chatHistory")),
                        "character": character(),
                        "greeting": False,
                        "userInput": "first",
                        "model": "x",
                    }
                ),
                encoding="utf-8",
            )
            state_out = root / "state-1.json"
            result_out = root / "result.json"
            fake = (
                {"choices": [{"message": {"content": "safe reply"}}]},
                "safe reply",
                "HTTP 200",
                {
                    "source": "choices[0].message.content",
                    "contentType": "application/json",
                    "responseBytes": 10,
                    "warnings": [],
                },
            )
            with mock.patch.object(lab, "call_model", return_value=fake):
                code = lab.main(
                    [
                        "run-turn",
                        "--case",
                        str(case_path),
                        "--base-url",
                        "http://127.0.0.1:1",
                        "--no-auth",
                        "--state-out",
                        str(state_out),
                        "--output",
                        str(result_out),
                    ]
                )
            self.assertEqual(code, 0)
            self.assertEqual(stat.S_IMODE(state_out.stat().st_mode), 0o600)
            state = json.loads(state_out.read_text())
            serialized = json.dumps(state).lower()
            self.assertNotIn("api_key", serialized)
            self.assertNotIn("authorization", serialized)
            self.assertNotIn("baseurl", serialized)
            self.assertEqual(state["turnIndex"], 1)

    def test_run_turn_cli_failure_writes_no_state_file(self) -> None:
        with tempfile.TemporaryDirectory() as working:
            root = Path(working)
            case_path = root / "case.json"
            case_path.write_text(
                json.dumps(
                    {
                        "schemaVersion": "2.3",
                        "preset": base_preset(marker("chatHistory")),
                        "character": character(),
                        "greeting": False,
                        "userInput": "must-not-persist",
                        "model": "x",
                    }
                ),
                encoding="utf-8",
            )
            state_out = root / "failed.state.json"
            result_out = root / "failed.result.json"
            failure = lab.ProviderResponseError(
                "empty_provider_response",
                "empty",
                {
                    "httpStatus": 200,
                    "contentType": "application/json",
                    "responseBytes": 2,
                    "responseSha256": "x",
                    "preview": "{}",
                },
            )
            with mock.patch.object(lab, "call_model", side_effect=failure):
                code = lab.main(
                    [
                        "run-turn",
                        "--case",
                        str(case_path),
                        "--base-url",
                        "http://127.0.0.1:1",
                        "--no-auth",
                        "--state-out",
                        str(state_out),
                        "--output",
                        str(result_out),
                    ]
                )
            self.assertEqual(code, 2)
            self.assertFalse(state_out.exists())
            result = json.loads(result_out.read_text())
            self.assertFalse(result["stateCommitted"])
            self.assertEqual(result["error"]["code"], "empty_provider_response")

    def test_state_input_requires_mode_0600(self) -> None:
        with tempfile.TemporaryDirectory() as working:
            path = Path(working) / "state.json"
            path.write_text("{}", encoding="utf-8")
            path.chmod(0o644)
            with self.assertRaises(lab.LabError) as raised:
                lab.load_turn_state(path, "fingerprint")
            self.assertEqual(raised.exception.code, "insecure_private_file")

    def test_state_input_rejects_extra_credential_like_keys(self) -> None:
        with tempfile.TemporaryDirectory() as working:
            path = Path(working) / "state.json"
            path.write_text(
                json.dumps({"api" + "-key": "must-not-be-ignored"}),
                encoding="utf-8",
            )
            path.chmod(0o600)
            with self.assertRaises(lab.LabError) as raised:
                lab.load_turn_state(path, "fingerprint")
            self.assertEqual(raised.exception.code, "state_contains_sensitive_field")


class PromptLabCliTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.case = {
            "preset": base_preset(marker("chatHistory")),
            "character": character(),
            "greeting": False,
            "userInput": "hello",
            "model": "tavo-virtual-test",
        }
        self.case_path = self.root / "case.json"
        self.case_path.write_text(json.dumps(self.case), encoding="utf-8")

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_compile_cli_writes_private_output(self) -> None:
        output = self.root / "result.json"
        self.assertEqual(lab.main(["compile", "--case", str(self.case_path), "--output", str(output)]), 0)
        self.assertEqual(stat.S_IMODE(output.stat().st_mode), 0o600)
        self.assertEqual(json.loads(output.read_text())["mode"], "compile")

    def test_http_200_response_adapter_distinguishes_empty_tool_and_unsupported(self) -> None:
        fixtures = [
            (b"", "application/json", "empty_provider_response"),
            (
                b'{"choices":[{"message":{"content":""}}]}',
                "application/json",
                "empty_provider_response",
            ),
            (
                b'{"choices":[{"message":{"tool_calls":[{"id":"1"}],"content":null}}]}',
                "application/json",
                "tool_call_only_response",
            ),
            (b'{"unexpected":true}', "application/json", "unsupported_provider_response_shape"),
            (
                b'data: {"choices":[{"delta":{"content":"partial"}}]}\n\n'
                b'data: {"error":{"message":"upstream reset"}}\n\n',
                "text/event-stream",
                "provider_error_body",
            ),
            (
                b'data: {"choices":[{"delta":{"content":"partial"}}]}\n\n'
                b'event: error\ndata: upstream reset\n\n',
                "text/event-stream",
                "provider_error_body",
            ),
            (b"<html>gateway error</html>", "text/html", "provider_error_document"),
        ]

        for payload, content_type, expected in fixtures:
            class ResponseHandler(BaseHTTPRequestHandler):
                def do_POST(self) -> None:  # noqa: N802
                    self.send_response(200)
                    self.send_header("Content-Type", content_type)
                    self.send_header("Content-Length", str(len(payload)))
                    self.end_headers()
                    self.wfile.write(payload)

                def log_message(self, _format: str, *_args: object) -> None:
                    return

            server = ThreadingHTTPServer(("127.0.0.1", 0), ResponseHandler)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                with self.subTest(expected=expected), self.assertRaises(lab.ProviderResponseError) as raised:
                    lab.call_model(
                        {"model": "x", "messages": [], "stream": False},
                        base_url=f"http://127.0.0.1:{server.server_address[1]}",
                        api_key=None,
                        timeout=2,
                        allow_insecure_http=False,
                    )
                self.assertEqual(raised.exception.code, expected)
                self.assertEqual(raised.exception.diagnostic["httpStatus"], 200)
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=2)

    def test_http_200_adapter_accepts_plain_sse_and_malformed_explicit_text(self) -> None:
        fixtures = [
            (b"plain reply", "text/plain", "plain reply", "text/plain", False),
            (
                b'data: {"choices":[{"delta":{"content":"stream"}}]}\n\ndata: [DONE]\n',
                "text/event-stream",
                "stream",
                "sse.data",
                False,
            ),
            (
                b'{"choices":[{"message":{"content":"recovered"}}] trailing',
                "application/json",
                "recovered",
                "malformed-json-explicit-text-field",
                True,
            ),
        ]
        for payload, content_type, expected_text, expected_source, warned in fixtures:
            class ResponseHandler(BaseHTTPRequestHandler):
                def do_POST(self) -> None:  # noqa: N802
                    self.send_response(200)
                    self.send_header("Content-Type", content_type)
                    self.send_header("Content-Length", str(len(payload)))
                    self.end_headers()
                    self.wfile.write(payload)

                def log_message(self, _format: str, *_args: object) -> None:
                    return

            server = ThreadingHTTPServer(("127.0.0.1", 0), ResponseHandler)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                _body, text, _status, extraction = lab.call_model(
                    {"model": "x", "messages": [], "stream": False},
                    base_url=f"http://127.0.0.1:{server.server_address[1]}",
                    api_key=None,
                    timeout=2,
                    allow_insecure_http=False,
                )
                self.assertEqual(text, expected_text)
                self.assertEqual(extraction["source"], expected_source)
                self.assertEqual(bool(extraction["warnings"]), warned)
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=2)

    def test_output_cannot_overwrite_case_or_api_key_file(self) -> None:
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            code = lab.main(
                ["compile", "--case", str(self.case_path), "--output", str(self.case_path)]
            )
        self.assertEqual(code, 2)
        self.assertEqual(json.loads(stderr.getvalue())["error"]["code"], "output_overwrites_input")
        self.assertEqual(json.loads(self.case_path.read_text()), self.case)

        key_file = self.root / "secret.txt"
        key_file.write_text("fixture-key", encoding="utf-8")
        key_file.chmod(0o600)
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            code = lab.main(
                [
                    "run",
                    "--case",
                    str(self.case_path),
                    "--base-url",
                    "http://127.0.0.1:1",
                    "--api-key-file",
                    str(key_file),
                    "--output",
                    str(key_file),
                ]
            )
        self.assertEqual(code, 2)
        self.assertEqual(json.loads(stderr.getvalue())["error"]["code"], "output_overwrites_input")
        self.assertEqual(key_file.read_text(), "fixture-key")

    def test_run_calls_loopback_virtual_provider_without_phone_or_upstream(self) -> None:
        self.case["preset"] = base_preset(
            {
                "identifier": "ejs-run",
                "content": '<% setvar("run", 1) %>RUN <%- "{{char}}" %>',
                "role": "system",
                "type": "custom",
                "injectionPosition": "relative",
                "enabled": True,
                "active": True,
            },
            marker("chatHistory"),
        )
        self.case_path.write_text(json.dumps(self.case), encoding="utf-8")
        config = provider.VirtualProviderConfig(
            capture_dir=self.root / "captures",
            client_key=CLIENT_KEY,
            model="tavo-virtual-test",
            allowed_clients=provider.validate_allowed_clients(["127.0.0.1"]),
        )
        server = provider.VirtualProviderServer(("127.0.0.1", 0), config)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        output = self.root / "run.json"
        old_key = os.environ.get(lab.DEFAULT_KEY_ENV)
        os.environ[lab.DEFAULT_KEY_ENV] = CLIENT_KEY
        try:
            code = lab.main(
                [
                    "run",
                    "--case",
                    str(self.case_path),
                    "--base-url",
                    f"http://127.0.0.1:{server.server_address[1]}",
                    "--output",
                    str(output),
                ]
            )
        finally:
            if old_key is None:
                os.environ.pop(lab.DEFAULT_KEY_ENV, None)
            else:
                os.environ[lab.DEFAULT_KEY_ENV] = old_key
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)
        self.assertEqual(code, 0)
        result = json.loads(output.read_text())
        self.assertEqual(result["mode"], "run")
        self.assertTrue(result["responseText"].startswith("TAVO_VIRTUAL_OK::"))
        capture = json.loads(next((self.root / "captures").glob("*.json")).read_text())
        self.assertEqual(capture["request"]["body"], result["request"])
        self.assertEqual(capture["provider"], "tavo-virtual")
        captured_text = json.dumps(capture["request"]["body"], ensure_ascii=False)
        self.assertIn("RUN Mira", captured_text)
        self.assertNotIn("<%", captured_text)
        self.assertEqual(result["ejs"]["variables"]["final"]["chat"]["run"], 1)

    def test_run_multiturn_calls_provider_sequentially_and_carries_real_reply(self) -> None:
        self.case.pop("userInput")
        self.case["preset"] = base_preset(
            {
                "identifier": "session-counter",
                "content": '<% incvar("sessionTurn") %>SESSION=<%- getvar("sessionTurn") %>',
                "role": "system",
                "type": "custom",
                "injectionPosition": "relative",
                "enabled": True,
                "active": True,
            },
            marker("chatHistory"),
        )
        self.case["turns"] = [
            {"label": "first", "userInput": "first-user-message"},
            {"label": "second", "userInput": "second-user-message"},
        ]
        self.case_path.write_text(json.dumps(self.case), encoding="utf-8")
        config = provider.VirtualProviderConfig(
            capture_dir=self.root / "session-captures",
            client_key=CLIENT_KEY,
            model="tavo-virtual-test",
            allowed_clients=provider.validate_allowed_clients(["127.0.0.1"]),
        )
        server = provider.VirtualProviderServer(("127.0.0.1", 0), config)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        output = self.root / "session-run.json"
        old_key = os.environ.get(lab.DEFAULT_KEY_ENV)
        os.environ[lab.DEFAULT_KEY_ENV] = CLIENT_KEY
        try:
            code = lab.main(
                [
                    "run",
                    "--case",
                    str(self.case_path),
                    "--base-url",
                    f"http://127.0.0.1:{server.server_address[1]}",
                    "--output",
                    str(output),
                ]
            )
        finally:
            if old_key is None:
                os.environ.pop(lab.DEFAULT_KEY_ENV, None)
            else:
                os.environ[lab.DEFAULT_KEY_ENV] = old_key
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)

        self.assertEqual(code, 0)
        result = json.loads(output.read_text())
        self.assertEqual(result["mode"], "run-session")
        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["session"]["completedTurns"], 2)
        self.assertEqual(result["finalEjsVariables"]["chat"]["sessionTurn"], 2)
        first_reply = result["turns"][0]["responseText"]
        second_request = json.dumps(result["turns"][1]["request"], ensure_ascii=False)
        self.assertIn("first-user-message", second_request)
        self.assertIn(first_reply, second_request)
        self.assertIn("second-user-message", second_request)
        self.assertIn("SESSION=2", second_request)
        captures = list((self.root / "session-captures").glob("*.json"))
        self.assertEqual(len(captures), 2)

    def test_run_refuses_unrendered_ejs_before_network(self) -> None:
        self.case["ejs"] = {"mode": "off"}
        self.case["preset"] = base_preset(
            {
                "identifier": "ejs",
                "content": '<%- "valid but disabled" %>',
                "role": "system",
                "type": "custom",
                "injectionPosition": "relative",
                "enabled": True,
                "active": True,
            },
            marker("chatHistory"),
        )
        self.case_path.write_text(json.dumps(self.case), encoding="utf-8")
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            code = lab.main(
                [
                    "run",
                    "--case",
                    str(self.case_path),
                    "--base-url",
                    "http://127.0.0.1:1",
                    "--no-auth",
                ]
            )
        self.assertEqual(code, 2)
        self.assertEqual(json.loads(stderr.getvalue())["error"]["code"], "unrendered_ejs")

    def test_run_requires_explicit_model_and_trust_for_case_base_url(self) -> None:
        old_model = os.environ.pop(lab.DEFAULT_MODEL_ENV, None)
        old_base = os.environ.pop(lab.DEFAULT_BASE_URL_ENV, None)
        no_model = dict(self.case)
        no_model.pop("model")
        self.case_path.write_text(json.dumps(no_model), encoding="utf-8")
        stderr = io.StringIO()
        try:
            with contextlib.redirect_stderr(stderr):
                code = lab.main(
                    ["run", "--case", str(self.case_path), "--base-url", "http://127.0.0.1:1", "--no-auth"]
                )
            self.assertEqual(code, 2)
            self.assertEqual(json.loads(stderr.getvalue())["error"]["code"], "missing_model")

            self.case["model"] = {"id": "x", "baseUrl": "http://127.0.0.1:1"}
            self.case_path.write_text(json.dumps(self.case), encoding="utf-8")
            stderr = io.StringIO()
            with contextlib.redirect_stderr(stderr):
                code = lab.main(["run", "--case", str(self.case_path), "--no-auth"])
            self.assertEqual(code, 2)
            self.assertEqual(json.loads(stderr.getvalue())["error"]["code"], "untrusted_case_base_url")
        finally:
            if old_model is not None:
                os.environ[lab.DEFAULT_MODEL_ENV] = old_model
            if old_base is not None:
                os.environ[lab.DEFAULT_BASE_URL_ENV] = old_base

    def test_environment_api_key_with_control_character_is_rejected_without_echo(self) -> None:
        bad_key = "secret-value\nsecond-line"
        old_key = os.environ.get(lab.DEFAULT_KEY_ENV)
        os.environ[lab.DEFAULT_KEY_ENV] = bad_key
        stderr = io.StringIO()
        try:
            with contextlib.redirect_stderr(stderr):
                code = lab.main(
                    [
                        "run",
                        "--case",
                        str(self.case_path),
                        "--base-url",
                        "http://127.0.0.1:1",
                    ]
                )
        finally:
            if old_key is None:
                os.environ.pop(lab.DEFAULT_KEY_ENV, None)
            else:
                os.environ[lab.DEFAULT_KEY_ENV] = old_key
        self.assertEqual(code, 2)
        error = json.loads(stderr.getvalue())["error"]
        self.assertEqual(error["code"], "invalid_api_key")
        self.assertNotIn(bad_key, error["message"])

    def test_api_key_file_symlink_is_rejected(self) -> None:
        target = self.root / "key.txt"
        target.write_text("fixture-key", encoding="utf-8")
        target.chmod(0o600)
        link = self.root / "key-link.txt"
        link.symlink_to(target)
        with self.assertRaises(lab.LabError) as raised:
            lab.read_secret_file(link)
        self.assertEqual(raised.exception.code, "insecure_key_file")

    def test_redirect_is_not_followed_and_error_echo_redacts_key(self) -> None:
        class RedirectHandler(BaseHTTPRequestHandler):
            def do_POST(self) -> None:  # noqa: N802
                if self.path == "/v1/chat/completions":
                    body = f"Bearer {CLIENT_KEY}".encode()
                    self.send_response(302)
                    self.send_header("Location", "/echo")
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
                else:
                    self.send_response(200)
                    self.end_headers()

            def log_message(self, _format: str, *_args: object) -> None:
                return

        server = ThreadingHTTPServer(("127.0.0.1", 0), RedirectHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with self.assertRaises(lab.LabError) as raised:
                lab.call_model(
                    {"model": "x", "messages": [{"role": "user", "content": "x"}], "stream": False},
                    base_url=f"http://127.0.0.1:{server.server_address[1]}",
                    api_key=CLIENT_KEY,
                    timeout=2,
                    allow_insecure_http=False,
                )
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)
        self.assertEqual(raised.exception.code, "provider_http_error")
        diagnostic_text = json.dumps(lab.error_payload(raised.exception))
        self.assertNotIn(CLIENT_KEY, diagnostic_text)
        self.assertIn("omitted", diagnostic_text)

    def test_provider_response_redacts_sensitive_values_and_keys(self) -> None:
        value = {
            "authorization": "anything",
            CLIENT_KEY: "value",
            "nested": {"message": f"Bearer {CLIENT_KEY}"},
        }
        redacted = lab.redact_provider_value(value, CLIENT_KEY)
        serialized = json.dumps(redacted)
        self.assertNotIn(CLIENT_KEY, serialized)
        self.assertEqual(redacted["authorization"], "<redacted>")


if __name__ == "__main__":
    unittest.main()
