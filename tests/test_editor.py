"""Check project isolation, preserved media, and source-to-edit timing maps."""

import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1] / "skills/video-edit/scripts"
sys.path.insert(0, str(SCRIPTS))

import editor  # noqa: E402 - Import the bundled CLI without installing it globally.
import setup  # noqa: E402 - Test the portable template updater without installing dependencies.


class ProjectTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix="Video Editor Tests ")
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)

    def test_all_resolution_presets_and_orientations(self):
        for quality, dimensions in {
            "HD": (1280, 720),
            "FHD": (1920, 1080),
            "QHD": (2560, 1440),
        }.items():
            for orientation in ("landscape", "portrait"):
                with self.subTest(quality=quality, orientation=orientation):
                    project = editor.init_project(
                        self.root, f"{quality}-{orientation}", orientation, quality
                    )
                    manifest = editor.read(project / "timeline/manifest.json")
                    expected = dimensions if orientation == "landscape" else dimensions[::-1]
                    self.assertEqual((manifest["width"], manifest["height"]), expected)

    def test_existing_project_cannot_be_overwritten(self):
        project = editor.init_project(self.root, "example")
        original = (project / "project.json").read_bytes()
        with self.assertRaises(ValueError):
            editor.init_project(self.root, "example")
        self.assertEqual((project / "project.json").read_bytes(), original)

    def test_ingest_is_idempotent_and_preserves_source(self):
        project = editor.init_project(self.root, "example")
        source = self.root / "original media.png"
        source.write_bytes(b"synthetic test fixture")
        first = editor.ingest(project, source)
        second = editor.ingest(project, source)
        self.assertEqual(first, second)
        self.assertEqual(len(editor.read(project / "project.json")["assets"]), 1)
        self.assertEqual(source.read_bytes(), (project / first["original"]).read_bytes())
        self.assertEqual(source.read_bytes(), (project / "public" / first["src"]).read_bytes())

    def test_output_protection(self):
        output = self.root / "existing.mp4"
        output.write_bytes(b"keep this file")
        with self.assertRaises(ValueError):
            editor.no_overwrite(output)
        self.assertEqual(output.read_bytes(), b"keep this file")

    def test_explicit_root_overrides_other_configuration(self):
        with patch.dict("os.environ", {"AI_EDITOR_ROOT": str(self.root / "environment")}):
            self.assertEqual(
                editor.root_path(self.root / "explicit"), (self.root / "explicit").resolve()
            )

    def test_snapshot_preserves_manifest_and_reason(self):
        project = editor.init_project(self.root, "example")
        before = editor.read(project / "timeline/manifest.json")
        with patch.object(
            sys, "argv", ["editor.py", "snapshot", str(project), "--reason", "Revise opening"]
        ):
            editor.main()
        snapshots = list((project / "timeline/history").glob("*.json"))
        self.assertEqual(len(snapshots), 1)
        data = json.loads(snapshots[0].read_text())
        self.assertEqual(data["manifest"], before)
        self.assertEqual(data["reason"], "Revise opening")


class TimingTests(unittest.TestCase):
    def test_no_silence_keeps_entire_source(self):
        plan = editor.silence_plan({"duration": 10, "silence": []}, 0.15)
        self.assertEqual(
            plan["ranges"], [{"sourceStart": 0, "sourceEnd": 10, "outputStart": 0, "outputEnd": 10}]
        )

    def test_silence_edits_preserve_speech_padding_and_output_continuity(self):
        plan = editor.silence_plan({"duration": 10, "silence": [[2, 4], [7, 9]]}, 0.15)
        self.assertAlmostEqual(plan["duration"], 6.6)
        first, second, third = plan["ranges"]
        self.assertAlmostEqual(first["sourceEnd"], 2.15)
        self.assertAlmostEqual(second["sourceStart"], 3.85)
        self.assertAlmostEqual(third["sourceStart"], 8.85)
        for previous, current in zip(plan["ranges"], plan["ranges"][1:]):
            self.assertAlmostEqual(previous["outputEnd"], current["outputStart"])

    def test_short_pauses_are_retained(self):
        plan = editor.silence_plan({"duration": 3, "silence": [[1, 1.2]]}, 0.15)
        self.assertEqual(plan["duration"], 3)

    def test_srt_timestamps_cross_hour_boundary(self):
        self.assertEqual(editor.timestamp(3661.125), "01:01:01,125")


class TemplateUpdateTests(unittest.TestCase):
    def test_updates_are_explicit_and_preserve_a_backup(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "skill"
            tools = Path(directory) / "tools"
            source.mkdir()
            tools.mkdir()
            (source / "render.mjs").write_text("new renderer")
            (tools / "render.mjs").write_text("custom renderer")
            setup.copy_templates(source, tools)
            self.assertEqual((tools / "render.mjs").read_text(), "custom renderer")
            backup = setup.copy_templates(source, tools, update=True)
            self.assertEqual((tools / "render.mjs").read_text(), "new renderer")
            self.assertEqual((Path(backup) / "render.mjs").read_text(), "custom renderer")
            self.assertIsNone(setup.copy_templates(source, tools, update=True))

    def test_source_checkout_dependencies_are_not_copied_into_runtime(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "skill"
            tools = Path(directory) / "tools"
            (source / "node_modules/example").mkdir(parents=True)
            (source / "node_modules/example/package.json").write_text("{}")
            (source / "motion").mkdir()
            (source / "motion/output.mjs").write_text("new encoder")
            setup.copy_templates(source, tools)
            self.assertTrue((tools / "motion/output.mjs").exists())
            self.assertFalse((tools / "node_modules").exists())


if __name__ == "__main__":
    unittest.main()
