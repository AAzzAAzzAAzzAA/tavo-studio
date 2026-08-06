#!/usr/bin/env python3
"""Assert Tavo virtual-provider captures without treating them as model proof.

Expectation matching is correlation-first: every expectation must identify a
fixture nonce or an exact request ID. The resulting report always states that
the run is virtual, sent zero real-model requests, and must not count toward a
model KPI.
"""

from __future__ import annotations

import argparse
import json
import os
import stat
import sys
import uuid
from pathlib import Path
from typing import Any


SELECTOR_KEYS = (
    "requestId",
    "nonce",
    "intent",
    "path",
    "method",
    "protocol",
    "scenario",
)


class AssertionSpecError(ValueError):
    """The expectation document is malformed or unsafe to evaluate."""


def secure_output_directory(path: Path) -> None:
    if path.is_symlink():
        raise AssertionSpecError(f"Output directory cannot be a symlink: {path}")
    if path.exists() and not path.is_dir():
        raise AssertionSpecError(f"Output directory path is not a directory: {path}")
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    path.chmod(0o700)


def atomic_json(path: Path, value: Any) -> None:
    secure_output_directory(path.parent)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.{uuid.uuid4().hex}.tmp")
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
        os.replace(temporary, path)
        path.chmod(0o600)
    finally:
        if temporary.exists():
            temporary.unlink()


def read_json_file(path: Path, *, label: str) -> Any:
    if path.is_symlink():
        raise AssertionSpecError(f"{label} cannot be a symlink: {path}")
    metadata = path.stat()
    if not stat.S_ISREG(metadata.st_mode):
        raise AssertionSpecError(f"{label} must be a regular file: {path}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise AssertionSpecError(f"{label} is not valid UTF-8 JSON: {path}") from error


def load_captures(capture_dir: Path) -> list[dict[str, Any]]:
    if capture_dir.is_symlink():
        raise AssertionSpecError(f"Capture directory cannot be a symlink: {capture_dir}")
    if not capture_dir.is_dir():
        raise AssertionSpecError(f"Capture directory does not exist: {capture_dir}")
    captures: list[dict[str, Any]] = []
    for path in sorted(capture_dir.glob("*.json")):
        value = read_json_file(path, label="Capture file")
        if not isinstance(value, dict):
            raise AssertionSpecError(f"Capture file must contain an object: {path}")
        value = dict(value)
        value["_captureFile"] = path.name
        captures.append(value)
    return captures


def json_pointer(value: Any, pointer: str) -> Any:
    if pointer == "":
        return value
    if not isinstance(pointer, str) or not pointer.startswith("/"):
        raise AssertionSpecError(f"JSON pointer must be empty or start with '/': {pointer!r}")
    current = value
    for raw_token in pointer[1:].split("/"):
        token = raw_token.replace("~1", "/").replace("~0", "~")
        if isinstance(current, dict):
            if token not in current:
                raise KeyError(pointer)
            current = current[token]
        elif isinstance(current, list):
            if not token.isdigit():
                raise KeyError(pointer)
            index = int(token)
            if index >= len(current):
                raise KeyError(pointer)
            current = current[index]
        else:
            raise KeyError(pointer)
    return current


def is_subset(actual: Any, expected: Any) -> bool:
    if isinstance(expected, dict):
        return isinstance(actual, dict) and all(
            key in actual and is_subset(actual[key], item)
            for key, item in expected.items()
        )
    if isinstance(expected, list):
        return isinstance(actual, list) and len(actual) == len(expected) and all(
            is_subset(actual_item, expected_item)
            for actual_item, expected_item in zip(actual, expected)
        )
    return actual == expected


def validate_expectation(expectation: Any, index: int) -> dict[str, Any]:
    if not isinstance(expectation, dict):
        raise AssertionSpecError(f"expectations[{index}] must be an object")
    identifier = expectation.get("id")
    if not isinstance(identifier, str) or not identifier:
        raise AssertionSpecError(f"expectations[{index}].id must be a non-empty string")
    if not expectation.get("nonce") and not expectation.get("requestId"):
        raise AssertionSpecError(
            f"expectation {identifier!r} must select an exact nonce or requestId"
        )
    if "count" in expectation and "expectedRequestCount" in expectation:
        raise AssertionSpecError(
            f"expectation {identifier!r} cannot set both count and expectedRequestCount"
        )
    count = expectation.get("expectedRequestCount", expectation.get("count", 1))
    if not isinstance(count, int) or isinstance(count, bool) or count < 0:
        raise AssertionSpecError(
            f"expectation {identifier!r} request count must be a non-negative integer"
        )
    for key in SELECTOR_KEYS:
        if key in expectation and not isinstance(expectation[key], str):
            raise AssertionSpecError(f"expectation {identifier!r}.{key} must be a string")
    for key in ("requestPointers", "responsePointers", "capturePointers"):
        mapping = expectation.get(key, {})
        if not isinstance(mapping, dict) or not all(isinstance(item, str) for item in mapping):
            raise AssertionSpecError(f"expectation {identifier!r}.{key} must be an object")
    for key in ("bodyContains", "bodyNotContains", "orderedBodyText"):
        values = expectation.get(key, [])
        if not isinstance(values, list) or not all(isinstance(item, str) for item in values):
            raise AssertionSpecError(
                f"expectation {identifier!r}.{key} must be a list of strings"
            )
    for key in (
        "responseStatus",
        "retryCount",
        "clientDisconnectCount",
        "completedCount",
    ):
        if key in expectation and (
            not isinstance(expectation[key], int) or isinstance(expectation[key], bool)
            or expectation[key] < 0
        ):
            raise AssertionSpecError(
                f"expectation {identifier!r}.{key} must be a non-negative integer"
            )
    aggregation_keys = {
        "retryCount",
        "clientDisconnectCount",
        "completedCount",
        "expectedRequestCount",
    }
    if aggregation_keys.intersection(expectation) and "intent" not in expectation:
        raise AssertionSpecError(
            f"expectation {identifier!r} must select intent for request/retry lifecycle counts"
        )
    if "responseCompleted" in expectation and not isinstance(
        expectation["responseCompleted"], bool
    ):
        raise AssertionSpecError(
            f"expectation {identifier!r}.responseCompleted must be a boolean"
        )
    return expectation


def validate_spec(spec: Any) -> list[dict[str, Any]]:
    if not isinstance(spec, dict):
        raise AssertionSpecError("Expectation document must be an object")
    if spec.get("schemaVersion", 1) != 1:
        raise AssertionSpecError("Only expectation schemaVersion 1 is supported")
    if spec.get("providerMode", "virtual") != "virtual":
        raise AssertionSpecError("providerMode must be 'virtual'")
    if spec.get("countsTowardKpi", False) is not False:
        raise AssertionSpecError("Virtual captures cannot count toward a model KPI")
    if spec.get("realModelRequestsSent", 0) != 0:
        raise AssertionSpecError("Virtual capture specs must state zero real-model requests")
    raw_expectations = spec.get("expectations")
    if not isinstance(raw_expectations, list):
        raise AssertionSpecError("expectations must be a list")
    expectations = [
        validate_expectation(expectation, index)
        for index, expectation in enumerate(raw_expectations)
    ]
    identifiers = [item["id"] for item in expectations]
    if len(identifiers) != len(set(identifiers)):
        raise AssertionSpecError("Expectation IDs must be unique")
    if "rejectUnexpected" in spec and not isinstance(spec["rejectUnexpected"], bool):
        raise AssertionSpecError("rejectUnexpected must be a boolean")
    return expectations


def record_matches(record: dict[str, Any], expectation: dict[str, Any]) -> bool:
    return all(
        key not in expectation or record.get(key) == expectation[key]
        for key in SELECTOR_KEYS
    )


def pointer_failures(
    *,
    identifier: str,
    request_id: str,
    label: str,
    value: Any,
    pointers: dict[str, Any],
) -> list[str]:
    failures: list[str] = []
    for pointer, expected in pointers.items():
        try:
            actual = json_pointer(value, pointer)
        except KeyError:
            failures.append(
                f"{identifier}: {request_id} missing {label} pointer {pointer!r}"
            )
            continue
        if actual != expected:
            failures.append(
                f"{identifier}: {request_id} {label} pointer {pointer!r} "
                f"expected {expected!r}, got {actual!r}"
            )
    return failures


def assert_record(
    record: dict[str, Any],
    expectation: dict[str, Any],
) -> list[str]:
    identifier = expectation["id"]
    request_id = str(record.get("requestId", "<missing-request-id>"))
    failures: list[str] = []
    request = record.get("request")
    response = record.get("response")
    if not isinstance(request, dict):
        return [f"{identifier}: {request_id} has no request object"]
    if not isinstance(response, dict):
        return [f"{identifier}: {request_id} has no response object"]
    failures.extend(
        pointer_failures(
            identifier=identifier,
            request_id=request_id,
            label="request",
            value=request,
            pointers=expectation.get("requestPointers", {}),
        )
    )
    failures.extend(
        pointer_failures(
            identifier=identifier,
            request_id=request_id,
            label="response",
            value=response,
            pointers=expectation.get("responsePointers", {}),
        )
    )
    failures.extend(
        pointer_failures(
            identifier=identifier,
            request_id=request_id,
            label="capture",
            value=record,
            pointers=expectation.get("capturePointers", {}),
        )
    )
    if "requestBodySubset" in expectation:
        if not is_subset(request.get("body"), expectation["requestBodySubset"]):
            failures.append(
                f"{identifier}: {request_id} request body does not contain the expected subset"
            )
    body_text = json.dumps(
        request.get("body"),
        ensure_ascii=False,
        separators=(",", ":"),
    )
    for marker in expectation.get("bodyContains", []):
        if marker not in body_text:
            failures.append(
                f"{identifier}: {request_id} request body is missing marker {marker!r}"
            )
    for marker in expectation.get("bodyNotContains", []):
        if marker in body_text:
            failures.append(
                f"{identifier}: {request_id} request body contains forbidden marker {marker!r}"
            )
    position = 0
    for marker in expectation.get("orderedBodyText", []):
        found = body_text.find(marker, position)
        if found < 0:
            failures.append(
                f"{identifier}: {request_id} request body does not contain "
                f"{marker!r} in the required order"
            )
            break
        position = found + len(marker)
    if "responseStatus" in expectation and response.get("status") != expectation["responseStatus"]:
        failures.append(
            f"{identifier}: {request_id} response status expected "
            f"{expectation['responseStatus']}, got {response.get('status')!r}"
        )
    if (
        "responseCompleted" in expectation
        and response.get("completed") is not expectation["responseCompleted"]
    ):
        failures.append(
            f"{identifier}: {request_id} response completed expected "
            f"{expectation['responseCompleted']!r}, got {response.get('completed')!r}"
        )
    return failures


def evaluate_expectations(
    captures: list[dict[str, Any]],
    spec: dict[str, Any],
) -> dict[str, Any]:
    expectations = validate_spec(spec)
    failures: list[str] = []
    results: list[dict[str, Any]] = []
    matched_indexes: set[int] = set()
    for index, record in enumerate(captures):
        if record.get("provider") != "tavo-virtual":
            failures.append(
                f"capture {record.get('requestId', index)!r} is not from tavo-virtual"
            )
    for expectation in expectations:
        matched = [
            (index, record)
            for index, record in enumerate(captures)
            if record.get("provider") == "tavo-virtual"
            and record_matches(record, expectation)
        ]
        expected_count = expectation.get(
            "expectedRequestCount",
            expectation.get("count", 1),
        )
        expectation_failures: list[str] = []
        if len(matched) != expected_count:
            expectation_failures.append(
                f"{expectation['id']}: expected {expected_count} matching capture(s), "
                f"found {len(matched)}"
            )
        for index, record in matched:
            matched_indexes.add(index)
            expectation_failures.extend(assert_record(record, expectation))
        retry_count = max(0, len(matched) - 1)
        disconnected_count = sum(
            1
            for _index, record in matched
            if isinstance(record.get("response"), dict)
            and record["response"].get("clientDisconnected") is True
        )
        completed_count = sum(
            1
            for _index, record in matched
            if isinstance(record.get("response"), dict)
            and record["response"].get("completed") is True
        )
        lifecycle_counts = {
            "retryCount": retry_count,
            "clientDisconnectCount": disconnected_count,
            "completedCount": completed_count,
        }
        for key, actual in lifecycle_counts.items():
            if key in expectation and expectation[key] != actual:
                expectation_failures.append(
                    f"{expectation['id']}: expected {key}={expectation[key]}, got {actual}"
                )
        failures.extend(expectation_failures)
        results.append(
            {
                "id": expectation["id"],
                "ok": not expectation_failures,
                "expectedCount": expected_count,
                "actualCount": len(matched),
                "retryCount": retry_count,
                "clientDisconnectCount": disconnected_count,
                "completedCount": completed_count,
                "requestIds": [record.get("requestId") for _index, record in matched],
                "failures": expectation_failures,
            }
        )
    if spec.get("rejectUnexpected", False):
        unexpected = [
            record
            for index, record in enumerate(captures)
            if index not in matched_indexes
        ]
        if unexpected:
            failures.append(
                "unexpected captures: "
                + ", ".join(
                    f"{item.get('requestId', '<missing>')}:{item.get('path', '<missing>')}"
                    for item in unexpected
                )
            )
    return {
        "schemaVersion": 1,
        "ok": not failures,
        "providerMode": "virtual",
        "realModelRequestsSent": 0,
        "countsTowardKpi": False,
        "captureCount": len(captures),
        "expectationCount": len(expectations),
        "results": results,
        "failures": failures,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--capture-dir", type=Path, required=True)
    parser.add_argument("--expectations", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        captures = load_captures(args.capture_dir.expanduser().resolve())
        spec = read_json_file(
            args.expectations.expanduser().resolve(),
            label="Expectation file",
        )
        report = evaluate_expectations(captures, spec)
        if args.output:
            atomic_json(args.output.expanduser().resolve(), report)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0 if report["ok"] else 1
    except (OSError, AssertionSpecError) as error:
        print(
            json.dumps(
                {
                    "ok": False,
                    "providerMode": "virtual",
                    "realModelRequestsSent": 0,
                    "countsTowardKpi": False,
                    "error": str(error),
                },
                ensure_ascii=False,
            ),
            file=sys.stderr,
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
