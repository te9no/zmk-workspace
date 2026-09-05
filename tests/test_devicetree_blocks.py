from pathlib import Path
import sys
import unittest


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

from devicetree_blocks import find_labeled_block, find_named_block, iter_blocks  # noqa: E402
import re  # noqa: E402


class DevicetreeBlocksTest(unittest.TestCase):
    SAMPLE = r'''
// ignored_label: fake_node { }
layout_test: zmk,physical-layout {
    compatible = "zmk,physical-layout";
    description = "braces inside a string: { not structure }";
    // unmatched comment brace }
    /* another unmatched comment { */
    child { value = <1>; };
    keys = <&key_physical_attrs 100 100 0 0 0 0 0>;
};
after_node { value = <2>; };
'''

    def test_labeled_block_ignores_comment_and_string_braces(self):
        block = find_labeled_block(self.SAMPLE, "layout_test")
        self.assertIn("key_physical_attrs", block)
        self.assertNotIn("after_node", block)

    def test_named_block_ignores_comment_and_string_braces(self):
        block = find_named_block(self.SAMPLE, "after_node")
        self.assertIn("value = <2>", block)

    def test_iteration_skips_commented_fake_nodes(self):
        pattern = re.compile(r"\b([A-Za-z0-9_]+)\s*:\s*[A-Za-z0-9_,@-]+\s*\{")
        labels = [label for label, _ in iter_blocks(self.SAMPLE, pattern)]
        self.assertEqual(labels, ["layout_test"])

    def test_unclosed_real_block_is_rejected(self):
        with self.assertRaisesRegex(SystemExit, "Unclosed"):
            find_labeled_block("layout_bad: node { value = <1>;", "layout_bad")


if __name__ == "__main__":
    unittest.main()
