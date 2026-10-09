import unittest

class PipelineFailureTest(unittest.TestCase):
    def test_pipeline_blocks_failure(self):
        self.fail("Intentional failure to verify the CI gate")
