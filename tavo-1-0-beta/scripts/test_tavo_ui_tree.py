#!/usr/bin/env python3
from __future__ import annotations

import argparse
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock


SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS))

import tavo_ui_tree as ui  # noqa: E402


def hierarchy(*children: str) -> bytes:
    root = (
        '<node index="0" text="" content-desc="" class="android.widget.FrameLayout" '
        'package="app.bitbear.tav" enabled="true" clickable="false" scrollable="false" '
        'long-clickable="false" bounds="[0,0][1000,2000]">'
    )
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<hierarchy rotation="0">'
        f"{root}{''.join(children)}</node>"
        "</hierarchy>"
    ).encode()


def node(
    text: str,
    *,
    bounds: str = "[100,200][500,600]",
    clickable: bool = False,
    scrollable: bool = False,
    long_clickable: bool = False,
) -> str:
    return (
        f'<node index="0" text="{text}" content-desc="" class="android.widget.Button" '
        'package="app.bitbear.tav" enabled="true" '
        f'clickable="{str(clickable).lower()}" scrollable="{str(scrollable).lower()}" '
        f'long-clickable="{str(long_clickable).lower()}" bounds="{bounds}" />'
    )


def gesture_args(**overrides: object) -> argparse.Namespace:
    values: dict[str, object] = {
        "text": "Target",
        "content_desc": None,
        "hint": None,
        "node_class": None,
        "bounds": None,
        "contains": False,
        "allow_clickable_fallback": False,
        "allow_semantic_fallback": False,
        "device": "offline-device",
        "timeout": 1.0,
        "duration_ms": 700,
        "delta_x": 0,
        "delta_y": -100,
        "postcondition_text": "Done",
        "postcondition_content_desc": None,
        "postcondition_hint": None,
        "postcondition_node_class": None,
        "postcondition_contains": False,
        "postcondition_count": 1,
        "postcondition_timeout": 1.0,
        "postcondition_poll_interval": 0.01,
    }
    values.update(overrides)
    return argparse.Namespace(**values)


class TavoUiTreeTests(unittest.TestCase):
    def test_timeout_classifies_gesture_side_effect_without_name_error(self) -> None:
        timeout = subprocess.TimeoutExpired(["adb"], 1)
        with mock.patch.object(ui.subprocess, "run", side_effect=timeout):
            with self.assertRaises(ui.CliFailure) as gesture_error:
                ui.run_adb_raw(
                    "offline-device",
                    ["shell", "input", "swipe", "1", "2", "1", "2", "700"],
                    1,
                )
            self.assertEqual(gesture_error.exception.code, "adb_timeout")
            self.assertTrue(gesture_error.exception.details["sideEffectMayHaveOccurred"])

            with self.assertRaises(ui.CliFailure) as read_error:
                ui.run_adb_raw("offline-device", ["shell", "getprop"], 1)
            self.assertFalse(read_error.exception.details["sideEffectMayHaveOccurred"])

    def test_long_press_requires_unique_long_clickable_target_and_postcondition(self) -> None:
        before = hierarchy(node("Target", long_clickable=True))
        after = hierarchy(node("Done"))
        completed = subprocess.CompletedProcess([], 0, b"", b"")
        with (
            mock.patch.object(
                ui,
                "capture_xml",
                side_effect=[(before, {"type": "offline"}), (after, {"type": "offline"})],
            ),
            mock.patch.object(ui, "run_adb", return_value=completed) as run_adb,
        ):
            result = ui.command_long_press(gesture_args())

        self.assertTrue(result["ok"])
        self.assertTrue(result["sideEffectMayHaveOccurred"])
        self.assertEqual(result["postcondition"]["matchCount"], 1)
        gesture = run_adb.call_args.args[1]
        self.assertEqual(gesture[:3], ["shell", "input", "swipe"])
        self.assertEqual(gesture[3:7], ["300", "400", "300", "400"])
        self.assertEqual(gesture[-1], "700")

    def test_long_press_refuses_unmarked_or_ambiguous_target_before_gesture(self) -> None:
        unmarked = hierarchy(node("Target", long_clickable=False))
        ambiguous = hierarchy(
            node("Target", long_clickable=True),
            node("Target", bounds="[500,200][900,600]", long_clickable=True),
        )
        for xml, expected_code in (
            (unmarked, "target_not_long_clickable"),
            (ambiguous, "ambiguous_match"),
        ):
            with (
                self.subTest(expected_code=expected_code),
                mock.patch.object(ui, "capture_xml", return_value=(xml, {"type": "offline"})),
                mock.patch.object(ui, "run_adb") as run_adb,
                self.assertRaises(ui.CliFailure) as error,
            ):
                ui.command_long_press(gesture_args())
            self.assertEqual(error.exception.code, expected_code)
            run_adb.assert_not_called()

    def test_long_press_clickable_fallback_requires_exact_bounds_and_clickable_target(self) -> None:
        before = hierarchy(node("Target", clickable=True, bounds="[100,200][500,600]"))
        after = hierarchy(node("Done"))
        completed = subprocess.CompletedProcess([], 0, b"", b"")
        with (
            mock.patch.object(
                ui,
                "capture_xml",
                side_effect=[(before, {"type": "offline"}), (after, {"type": "offline"})],
            ),
            mock.patch.object(ui, "run_adb", return_value=completed),
        ):
            result = ui.command_long_press(
                gesture_args(
                    bounds="[100,200][500,600]",
                    allow_clickable_fallback=True,
                )
            )
        self.assertEqual(result["targetCapability"]["required"], "clickable")
        self.assertTrue(result["targetCapability"]["clickableFallback"])

        for overrides, expected_code in (
            ({"bounds": None}, "long_press_fallback_requires_bounds"),
            ({"bounds": "[100,200][500,600]", "text": "Missing"}, "no_matches"),
        ):
            with (
                self.subTest(expected_code=expected_code),
                mock.patch.object(ui, "capture_xml", return_value=(before, {"type": "offline"})),
                mock.patch.object(ui, "run_adb") as run_adb,
                self.assertRaises(ui.CliFailure) as error,
            ):
                ui.command_long_press(
                    gesture_args(
                        allow_clickable_fallback=True,
                        **overrides,
                    )
                )
            self.assertEqual(error.exception.code, expected_code)
            run_adb.assert_not_called()

    def test_long_press_semantic_fallback_requires_exact_bounds_and_label(self) -> None:
        before = hierarchy(node("Hold to talk", bounds="[100,200][500,600]"))
        after = hierarchy(node("Done"))
        completed = subprocess.CompletedProcess([], 0, b"", b"")
        with (
            mock.patch.object(
                ui,
                "capture_xml",
                side_effect=[(before, {"type": "offline"}), (after, {"type": "offline"})],
            ),
            mock.patch.object(ui, "run_adb", return_value=completed),
        ):
            result = ui.command_long_press(
                gesture_args(
                    text="Hold to talk",
                    bounds="[100,200][500,600]",
                    allow_semantic_fallback=True,
                )
            )
        self.assertEqual(
            result["targetCapability"]["required"],
            "enabled-semantic-label-exact-bounds",
        )
        self.assertTrue(result["targetCapability"]["semanticFallback"])

        with (
            mock.patch.object(ui, "capture_xml", return_value=(before, {"type": "offline"})),
            mock.patch.object(ui, "run_adb") as run_adb,
            self.assertRaises(ui.CliFailure) as error,
        ):
            ui.command_long_press(
                gesture_args(
                    text=None,
                    bounds="[100,200][500,600]",
                    allow_semantic_fallback=True,
                )
            )
        self.assertEqual(error.exception.code, "semantic_fallback_requires_label")
        run_adb.assert_not_called()

    def test_bounds_selector_rejects_non_uiautomator_shape(self) -> None:
        with self.assertRaises(ui.CliFailure) as error:
            ui.selectors_from_args(gesture_args(bounds="1025,2436,1168,2612"))
        self.assertEqual(error.exception.code, "invalid_bounds_selector")

    def test_swipe_stays_inside_unique_scrollable_target(self) -> None:
        before = hierarchy(
            node(
                "Target",
                bounds="[100,200][900,1400]",
                scrollable=True,
            )
        )
        after = hierarchy(node("Done"))
        completed = subprocess.CompletedProcess([], 0, b"", b"")
        with (
            mock.patch.object(
                ui,
                "capture_xml",
                side_effect=[(before, {"type": "offline"}), (after, {"type": "offline"})],
            ),
            mock.patch.object(ui, "run_adb", return_value=completed) as run_adb,
        ):
            result = ui.command_swipe(gesture_args(delta_y=-300, duration_ms=350))

        self.assertEqual(result["gesture"]["start"], {"x": 500, "y": 800})
        self.assertEqual(result["gesture"]["end"], {"x": 500, "y": 500})
        self.assertEqual(run_adb.call_args.args[1][-1], "350")

    def test_swipe_refuses_zero_or_out_of_target_end(self) -> None:
        before = hierarchy(node("Target", scrollable=True))
        for overrides, expected_code in (
            ({"delta_x": 0, "delta_y": 0}, "empty_swipe"),
            ({"delta_x": 1000, "delta_y": 0}, "swipe_end_outside_target"),
        ):
            with (
                self.subTest(expected_code=expected_code),
                mock.patch.object(ui, "capture_xml", return_value=(before, {"type": "offline"})),
                mock.patch.object(ui, "run_adb") as run_adb,
                self.assertRaises(ui.CliFailure) as error,
            ):
                ui.command_swipe(gesture_args(**overrides))
            self.assertEqual(error.exception.code, expected_code)
            run_adb.assert_not_called()

    def test_failed_postcondition_reports_possible_side_effect(self) -> None:
        before = hierarchy(node("Target", long_clickable=True))
        after = hierarchy(node("Different"))
        completed = subprocess.CompletedProcess([], 0, b"", b"")
        with (
            mock.patch.object(
                ui,
                "capture_xml",
                side_effect=[(before, {"type": "offline"}), (after, {"type": "offline"})],
            ),
            mock.patch.object(ui, "run_adb", return_value=completed),
            mock.patch.object(ui.time, "monotonic", side_effect=[0.0, 2.0]),
            mock.patch.object(ui.time, "sleep"),
            self.assertRaises(ui.CliFailure) as error,
        ):
            ui.command_long_press(gesture_args(postcondition_timeout=1.0))

        self.assertEqual(error.exception.code, "postcondition_failed")
        self.assertTrue(error.exception.details["sideEffectMayHaveOccurred"])

    def test_gesture_refuses_missing_postcondition_before_adb(self) -> None:
        before = hierarchy(node("Target", long_clickable=True))
        args = gesture_args(postcondition_text=None)
        with (
            mock.patch.object(ui, "capture_xml", return_value=(before, {"type": "offline"})),
            mock.patch.object(ui, "run_adb") as run_adb,
            self.assertRaises(ui.CliFailure) as error,
        ):
            ui.command_long_press(args)
        self.assertEqual(error.exception.code, "missing_postcondition")
        run_adb.assert_not_called()


if __name__ == "__main__":
    unittest.main()
