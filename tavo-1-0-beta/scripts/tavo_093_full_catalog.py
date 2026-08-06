#!/usr/bin/env python3
"""Fine-grained A-J catalog for the Tavo 0.93 zero-real-model epoch.

The versioned plugin/non-plugin runners retain coarse orchestration cases.  The
master runner additionally loads this catalog so every numbered requirement in
the approved plan, including the retained 34-case prompt-edge and 35-case
cross-feature matrices, receives an independent terminal result.
"""

from __future__ import annotations

from typing import Iterable

import tavo_093_runner_core as core


PROMPT_EDGE_CASES = (
    "worldbook precedence baseline",
    "worldbook precedence with reversed order",
    "worldbook precedence keyword control",
    "secondary none hit",
    "secondary none miss",
    "secondary AND-any hit",
    "secondary AND-any miss",
    "secondary AND-all hit",
    "secondary AND-all miss",
    "secondary NOT-any hit",
    "secondary NOT-any miss",
    "secondary NOT-all hit",
    "secondary NOT-all miss",
    "case-sensitive ASCII keyword hit",
    "case-sensitive ASCII keyword miss",
    "whole-word ASCII keyword hit",
    "whole-word ASCII keyword miss",
    "whole-word Chinese keyword hit",
    "whole-word Chinese keyword miss",
    "multiple main keywords hit",
    "multiple main keywords miss",
    "relative preset forward order",
    "relative preset reverse order",
    "absolute preset system depth",
    "absolute preset user depth",
    "absolute preset assistant depth",
    "regex capture in code fence hit",
    "regex capture in code fence miss",
    "regex Markdown display hit",
    "regex Markdown display miss",
    "regex raw substitution hit",
    "regex raw substitution miss",
    "regex placement depth hit",
    "regex placement depth miss",
)


CROSS_FEATURE_CASES = (
    "regex-to-worldbook enabled path",
    "regex-to-worldbook control",
    "worldbook constant activation",
    "worldbook keyword hit",
    "worldbook keyword miss",
    "worldbook secondary-any hit",
    "worldbook secondary-any miss",
    "worldbook probability 100",
    "worldbook probability 0",
    "worldbook scan-depth in window",
    "worldbook scan-depth outside window",
    "worldbook sticky trigger",
    "worldbook sticky carry",
    "worldbook sticky unactivated control",
    "worldbook cooldown trigger",
    "worldbook cooldown blocked",
    "worldbook cooldown expired",
    "worldbook delay before threshold",
    "worldbook delay after threshold",
    "worldbook position before",
    "worldbook position after",
    "worldbook position top of examples",
    "worldbook position bottom of examples",
    "worldbook depth system role",
    "worldbook depth assistant role",
    "character first message",
    "character alternate greeting A",
    "character alternate greeting B",
    "character example messages",
    "preset absolute depth zero",
    "preset absolute depth three",
    "input clear/set/append/get/send",
    "message append/update/delete",
    "plugin TavoJS lorebook CRUD",
    "chat switch and TavoJS readback",
)


SECTION_ROWS: dict[str, tuple[str, ...]] = {
    "A": (
        "v1 omitted/explicit specVersion compatibility and no i18n namespace",
        "v2 minimal install readback entry execution and retained disable",
        "SemVer stable prerelease and build-metadata acceptance",
        "SemVer invalid prefix short form leading zero and prerelease rejection",
        "minAppVersion lower equal higher prerelease and build comparison",
        "specVersion 3 and missing required v2 field rejection",
        "localization defaultLocale optional resources zh-CN and zh_CN rejection",
        "catalog missing unsafe symlink UTF-8 JSON object flat-key/value validation",
        "$t legal positions across identity actions settings select and defaults",
        "$t empty key extra fields and unsupported-position rejection",
        "locale exact compatible English defaultLocale and key fallback chain",
        "localized structured select stable value and changing label",
        "text/textarea defaults language switch override retention and reset",
        "tavo.plugin.i18n getters supportedLocales copy t interpolation and missing key",
        "i18n onChange unsubscribe getter ordering no entry rerun and manual rerender",
        "i18n entry input sidebar chat-fragment and message-fragment hosts",
        "ordinary message TavoJS cannot access plugin i18n namespace",
        "same-id v1-to-v2 update preserves config enabled and runtime contribution",
        "root wrapper zip and unsafe/ambiguous/missing/symlink package canaries",
        "plugin reload error display disable and restart behavior",
        "right-sidebar plugin action position label click and handler readback",
        "plugin HTML fragment button separated from ordinary AR bubble button",
        "chat:changed alias delivery for chat:updated",
        "othersContinuation groupReply and auxiliary exclusion matrix",
        "input attachment preservation across cancellation",
        "tavo.input.send concurrent busy result",
        "persona TTS binding and queue-stop request scheduling",
    ),
    "B": (
        "custom provider models probe save reopen and inactive retention",
        "Chat Completions Responses and legacy Completions JSON/SSE paths",
        "global versus API parameter precedence",
        "adjacent-role merge and system/user converter final role order",
        "Fable 5 controls persistence and local wire fields",
        "Mythos 5 controls persistence and local wire fields",
        "normal delayed cancel abrupt EOF and no-DONE JSON/SSE",
        "HTTP 400 401 429 500 invalid JSON wrong Content-Type oversized and unreachable",
        "fault state preserves input message count retry count recovery and redaction",
        "reply regeneration continuation and othersContinuation request association",
        "reasoning display versus persistent-content boundary",
        "reroll A/B/C session retention and restart clearing",
        "translation API language/content request and display placement",
        "group natural all specified contextual mention request and speaker matrix",
        "contextual-speaker API group injection and quick-avatar entry state",
    ),
    "C": (
        "OpenRouter appears in ASR provider selector",
        "OpenRouter and Custom OpenAI ASR save reopen restart inactive retention",
        "all ASR parameters persist sentinel values",
        "OpenAI multipart model language prompt format temperature and WAV metadata",
        "OpenRouter audio-chat path audio structure and parameter forwarding",
        "automated long-press down hold release sends",
        "long-press cancel submits no request or message",
        "Fill input does not send and supports edit/clear",
        "short press too-short slide-cancel and repeated long-press",
        "microphone deny temporary grant re-deny and Bluetooth permission recovery",
        "ASR delay empty transcript HTTP errors malformed type and disconnect",
        "ASR fault preserves message/input and next request recovers",
        "ASR evidence stores audio metadata/hash only",
        "human speech recognition accuracy explicitly not tested",
    ),
    "D": (
        "TTS provider form test-key redaction save and reopen",
        "voice-binding selector character/persona choose cancel and reopen",
        "character target and persona target requests",
        "missing target and dual-target rejection",
        "TTS model voice input speed format wire fields",
        "fixed empty damaged delayed and HTTP-error WAV handling",
        "two-item queue then stop scheduling and disconnect",
        "role user narration quote code tag and regex playback-rule request counts",
        "background playback and rule persistence",
        "real voice naturalness speaker audibility and audible stop not evaluated",
    ),
    "E": (
        "image provider save reopen and request fields",
        "image b64_json and local URL fixed PNG responses",
        "damaged empty wrong-type and HTTP-error image handling",
        "image imagine input-plus and TavoJS entry paths",
        "image preview prompt edit regeneration and download",
        "image insertion message type and UI",
        "send local small image into chat",
        "image-description request result and main-chat injection",
        "multimodal final payload text/image order hash and message association",
        "reference-image count and first-image behavior as protocol observation",
        "real image quality and provider compatibility not evaluated",
    ),
    "F": (
        "right-sidebar labels order grouping and legacy-entry reachability",
        "chat rename pin clone and statistics",
        "chat restart/delete on sacrificial chat only",
        "JSONL import TXT/JSON export reimport and field diff",
        "greeting selector alternate greetings and backtracking",
        "context logs correspond to worldbook regex preset and captured request",
        "input clear set append get send and concurrent busy",
        "message append insert update delete and actual not-found",
        "italic Markdown following-space persistence UI reopen and restart",
        "copied theme non-default font save reopen restart and original restore",
        "keyboard shortcut and quick-group-chat persistence",
        "storage categories read-only and runner-owned cache cleanup gate",
    ),
    "G": (
        "native character maximum-field create read update export import",
        "CCv2 import and readback",
        "CCv3 import and readback",
        "PNG embed extract import and readback",
        "persona create update active export import and binding",
        "local-file and local-HTTP import without third-party fetch",
        "first message alternate greetings and example messages UI",
        "sacrificial character persona lorebook regex preset and plugin actual delete",
    ),
    "I": (
        "HTML sanitizer script iframe style event dangerous URL data and local URL",
        "CSS absolute fixed sticky z-index overflow across scroll keyboard and redraw",
        "message floating button viewport overlay and native chrome boundary",
        "JavaScript load rerender update chat-switch restart and listener lifecycle",
        "Android WebView fetch receiver and Illegal invocation regression",
        "AR button plugin fragment native input and native sidebar action evidence",
        "tavo.character.current/get in plugin and message-panel hosts",
        "chat global and message variable scope persistence",
        "message TavoJS CRUD and current-message boundary",
        "file save load URL exists delete on runner-owned file",
        "toast preview select export app.version and local-only openUrl",
        "render/plugin state across rerender chat switch restart and export/import",
        "three same-PID rounds FDSize thread crash ANR and HyperSentinel evidence",
    ),
    "J": (
        "stabilize all retained fixtures before Backup B",
        "create private Backup B alias size and SHA-256 only",
        "mutate or remove one sacrificial duplicate from every data family",
        "restore Backup B with legal restart and PID change",
        "compare stable IDs field hashes enabled state runtime and UI",
        "on mismatch stop recovery-required and roll back with Backup A",
    ),
}


H_SUPPORT_ROWS = (
    "worldbook complete activation lifecycle position role and binding axes",
    "preset relative absolute role depth order enabled and binding axes",
    "regex send display persistent scope substitution and safety axes",
    "EJS/macro variables control flow order escaping errors and leak prevention",
    "long-memory local summarizer generation injection isolation reset and decoy",
    "character persona greeting example message input and plugin request influence",
    "virtual responses never count as model understanding or instruction following",
)


def _rows(
    matrix_item: str,
    titles: Iterable[str],
    *,
    key_prefix: str,
    stage: str,
    risk: str,
    proof_axes: tuple[str, ...],
    manual_numbers: frozenset[int] = frozenset(),
    real_model_numbers: frozenset[int] = frozenset(),
    destructive_numbers: frozenset[int] = frozenset(),
) -> list[core.CaseSpec]:
    result: list[core.CaseSpec] = []
    for number, title in enumerate(titles, start=1):
        result.append(
            core.CaseSpec(
                key=f"D93-{key_prefix}{number:02d}",
                title=title,
                stage=stage,
                risk=risk,
                proof_axes=proof_axes,
                requires_real_model=number in real_model_numbers,
                manual=number in manual_numbers,
                destructive=number in destructive_numbers,
                notes=(
                    "Zero-real-model epoch: a deterministic fixture may prove request/UI "
                    "integration, never model semantics."
                ),
                matrix_items=(matrix_item,),
            )
        )
    return result


def build_cases() -> list[core.CaseSpec]:
    cases: list[core.CaseSpec] = []
    cases.extend(
        _rows(
            "A",
            SECTION_ROWS["A"],
            key_prefix="A",
            stage="plugin-runtime",
            risk="medium",
            proof_axes=("schema", "ui", "persistence", "roundtrip"),
        )
    )
    cases.extend(
        _rows(
            "B",
            SECTION_ROWS["B"],
            key_prefix="B",
            stage="deterministic-request",
            risk="medium",
            proof_axes=("ui", "persistence", "request"),
        )
    )
    cases.extend(
        _rows(
            "C",
            SECTION_ROWS["C"],
            key_prefix="C",
            stage="deterministic-request",
            risk="medium",
            proof_axes=("ui", "persistence", "request"),
            manual_numbers=frozenset({14}),
            real_model_numbers=frozenset({14}),
        )
    )
    cases.extend(
        _rows(
            "D",
            SECTION_ROWS["D"],
            key_prefix="D",
            stage="deterministic-request",
            risk="medium",
            proof_axes=("ui", "persistence", "request"),
            manual_numbers=frozenset({10}),
            real_model_numbers=frozenset({10}),
        )
    )
    cases.extend(
        _rows(
            "E",
            SECTION_ROWS["E"],
            key_prefix="E",
            stage="deterministic-request",
            risk="medium",
            proof_axes=("ui", "persistence", "request"),
            manual_numbers=frozenset({11}),
            real_model_numbers=frozenset({11}),
        )
    )
    cases.extend(
        _rows(
            "F",
            SECTION_ROWS["F"],
            key_prefix="F",
            stage="ui-persistence",
            risk="medium",
            proof_axes=("ui", "persistence", "roundtrip"),
        )
    )
    cases.extend(
        _rows(
            "G",
            SECTION_ROWS["G"],
            key_prefix="G",
            stage="plugin-runtime",
            risk="medium",
            proof_axes=("ui", "persistence", "roundtrip"),
        )
    )
    cases.extend(
        _rows(
            "H",
            PROMPT_EDGE_CASES,
            key_prefix="HPE",
            stage="deterministic-request",
            risk="medium",
            proof_axes=("request", "persistence"),
        )
    )
    cases.extend(
        _rows(
            "H",
            CROSS_FEATURE_CASES,
            key_prefix="HCF",
            stage="deterministic-request",
            risk="medium",
            proof_axes=("request", "persistence", "roundtrip"),
        )
    )
    cases.extend(
        _rows(
            "H",
            H_SUPPORT_ROWS,
            key_prefix="HX",
            stage="deterministic-request",
            risk="medium",
            proof_axes=("request", "persistence", "roundtrip"),
        )
    )
    cases.extend(
        _rows(
            "I",
            SECTION_ROWS["I"],
            key_prefix="I",
            stage="plugin-runtime",
            risk="medium",
            proof_axes=("ui", "persistence", "roundtrip"),
        )
    )
    cases.extend(
        _rows(
            "J",
            SECTION_ROWS["J"],
            key_prefix="J",
            stage="backup-restore",
            risk="high",
            proof_axes=("roundtrip", "restoration"),
            destructive_numbers=frozenset(range(1, len(SECTION_ROWS["J"]) + 1)),
        )
    )
    return cases


def catalog_summary() -> dict[str, object]:
    cases = build_cases()
    return {
        "caseCount": len(cases),
        "matrixCounts": {
            item: sum(item in case.matrix_items for case in cases)
            for item in core.MATRIX_ITEMS
        },
        "caseKeys": [case.key for case in cases],
        "catalogErrors": core.validate_catalog(cases),
    }


if __name__ == "__main__":
    import json

    print(json.dumps(catalog_summary(), ensure_ascii=False, indent=2))
