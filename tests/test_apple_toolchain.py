import importlib.util
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "check_apple_toolchain.py"
SPEC = importlib.util.spec_from_file_location("check_apple_toolchain", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class AppleToolchainTests(unittest.TestCase):
    def test_command_line_tools_only_is_blocked_with_remediation(self):
        report = MODULE.evaluate_toolchain(
            {
                "xcode_select": (0, "/Library/Developer/CommandLineTools"),
                "xcodebuild": (1, "xcode-select: error: tool requires Xcode"),
                "swift": (0, "Apple Swift version 6.4"),
                "sdk_path": (0, "/Library/Developer/CommandLineTools/SDKs/MacOSX.sdk"),
            }
        )

        self.assertEqual(report["status"], "BLOCKED_FULL_XCODE_REQUIRED")
        self.assertFalse(report["ready"])
        self.assertTrue(any("xcode-select --switch" in step for step in report["remediation"]))

    def test_full_xcode_is_ready(self):
        report = MODULE.evaluate_toolchain(
            {
                "xcode_select": (0, "/Applications/Xcode.app/Contents/Developer"),
                "xcodebuild": (0, "Xcode 18.0\nBuild version 20A1"),
                "swift": (0, "Apple Swift version 6.4"),
                "sdk_path": (0, "/Applications/Xcode.app/SDKs/MacOSX.sdk"),
            }
        )

        self.assertEqual(report["status"], "READY")
        self.assertTrue(report["ready"])
        self.assertEqual(report["remediation"], [])


if __name__ == "__main__":
    unittest.main()
