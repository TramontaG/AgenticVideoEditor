"""Verify real A/V cuts, safe failure paths, and reusable edit timing maps."""

import math
from pathlib import Path
import shutil
import struct
import sys
import tempfile
import unittest
import wave
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "skills/video-edit/scripts"))
from editor import probe, read, run  # noqa: E402
from video_processing import frame_aligned_plan, remove_video_silence, video_info  # noqa: E402


class CutPlanTests(unittest.TestCase):
    def test_audio_codec_padding_does_not_add_a_video_frame(self):
        metadata = {
            "streams": [
                {
                    "codec_type": "video",
                    "avg_frame_rate": "0/0",
                    "r_frame_rate": "6/1",
                    "start_time": "0",
                    "tags": {"DURATION": "00:00:01.000000000"},
                }
            ],
            "format": {"duration": "1.008"},
        }
        with patch("video_processing.probe", return_value=metadata):
            _, _, fps, duration = video_info("example.webm")
        self.assertEqual(frame_aligned_plan(duration, [], 0.15, fps)["durationInFrames"], 6)

    def test_edge_silence_is_removed_and_speech_margins_are_retained(self):
        plan = frame_aligned_plan(5, [[0, 0.8], [1.8, 3.2], [4.2, 5]], 0.15, 20)
        self.assertEqual(plan["durationInFrames"], 52)
        self.assertEqual(
            [(r["sourceStartFrame"], r["sourceEndFrame"]) for r in plan["ranges"]],
            [(13, 39), (61, 87)],
        )
        self.assertAlmostEqual(plan["ranges"][0]["outputEnd"], plan["ranges"][1]["outputStart"])

    def test_all_silence_has_no_kept_frames(self):
        self.assertEqual(frame_aligned_plan(5, [[0, 5]], 0.15, 30)["ranges"], [])

    def test_overlapping_intervals_do_not_duplicate_output(self):
        plan = frame_aligned_plan(5, [[1, 3], [2, 4]], 0, 30)
        self.assertEqual(plan["durationInFrames"], 60)


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "FFmpeg is required")
class VideoSilenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="Video silence tests ")
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        audio = self.folder / "voice.wav"
        with wave.open(str(audio), "wb") as stream:
            stream.setnchannels(1)
            stream.setsampwidth(2)
            stream.setframerate(16000)
            samples = []
            for index in range(80000):
                t = index / 16000
                tone = 440 if 0.8 <= t < 1.8 else 880 if 3.2 <= t < 4.2 else 0
                samples.append(
                    struct.pack("<h", int(8000 * math.sin(2 * math.pi * tone * t)) if tone else 0)
                )
            stream.writeframes(b"".join(samples))
        self.source = self.folder / "original.mov"
        run(
            [
                "ffmpeg",
                "-v",
                "error",
                "-n",
                "-f",
                "lavfi",
                "-i",
                "testsrc2=s=160x90:r=20:d=5",
                "-i",
                audio,
                "-c:v",
                "libx264",
                "-pix_fmt",
                "yuv420p",
                "-c:a",
                "pcm_s16le",
                self.source,
            ]
        )

    def test_actual_video_and_audio_are_cut_together(self):
        original = self.source.read_bytes()
        output = self.folder / "edited.mp4"
        result = remove_video_silence(self.source, output)
        self.assertTrue(2.4 <= result["duration"] <= 2.8)
        self.assertEqual(len(result["ranges"]), 2)
        self.assertEqual(self.source.read_bytes(), original)
        self.assertEqual(read(str(output) + ".json")["ranges"], result["ranges"])
        metadata = probe(output)
        video = next(s for s in metadata["streams"] if s["codec_type"] == "video")
        audio = next(s for s in metadata["streams"] if s["codec_type"] == "audio")
        self.assertAlmostEqual(float(video["duration"]), result["duration"], delta=0.06)
        self.assertAlmostEqual(float(audio["duration"]), result["duration"], delta=0.06)
        self.assertFalse(list(self.folder.glob(".silence-*")))
        # Re-detecting the edited audio confirms the long pauses are gone.
        from video_processing import detect_silence

        self.assertEqual(detect_silence(output, min_silence=0.5), [])

    def test_missing_audio_and_existing_outputs_are_rejected(self):
        silent_video = self.folder / "no-audio.mp4"
        run(["ffmpeg", "-v", "error", "-n", "-i", self.source, "-an", "-c:v", "copy", silent_video])
        output = self.folder / "should-not-exist.mp4"
        with self.assertRaisesRegex(ValueError, "no audio"):
            remove_video_silence(silent_video, output)
        self.assertFalse(output.exists())
        output.write_bytes(b"preserve existing output")
        with self.assertRaises(ValueError):
            remove_video_silence(self.source, output)
        self.assertEqual(output.read_bytes(), b"preserve existing output")

    def test_continuous_audio_keeps_full_duration(self):
        continuous = self.folder / "continuous.mov"
        run(
            [
                "ffmpeg",
                "-v",
                "error",
                "-n",
                "-i",
                self.source,
                "-f",
                "lavfi",
                "-i",
                "sine=frequency=440:duration=5",
                "-map",
                "0:v:0",
                "-map",
                "1:a:0",
                "-c:v",
                "copy",
                "-c:a",
                "pcm_s16le",
                continuous,
            ]
        )
        result = remove_video_silence(continuous, self.folder / "continuous-edited.mp4")
        self.assertAlmostEqual(result["duration"], 5, delta=0.05)
        self.assertEqual(len(result["ranges"]), 1)

    def test_entirely_silent_video_does_not_create_empty_export(self):
        silent = self.folder / "silent.mov"
        run(
            [
                "ffmpeg",
                "-v",
                "error",
                "-n",
                "-i",
                self.source,
                "-f",
                "lavfi",
                "-i",
                "anullsrc=r=16000:cl=mono",
                "-map",
                "0:v:0",
                "-map",
                "1:a:0",
                "-t",
                "5",
                "-c:v",
                "copy",
                "-c:a",
                "pcm_s16le",
                silent,
            ]
        )
        output = self.folder / "empty.mp4"
        with self.assertRaisesRegex(ValueError, "No non-silent"):
            remove_video_silence(silent, output)
        self.assertFalse(output.exists())
        self.assertFalse(Path(str(output) + ".json").exists())


if __name__ == "__main__":
    unittest.main()
