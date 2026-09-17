"""Cheap arithmetic and recorded static-probe checks; no model or dataset load."""
import unittest
from analyze import SCRATCH, read, adapter


class AnalysisTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.result = read(SCRATCH/'analysis.json')

    def test_counts_match_independent_peft_meta_instantiation(self):
        expected = {'all_linear_r8': 16515072, 'qv_r8': 2949120, 'qkvo_r8': 5898240, 'qv_r4': 1474560}
        for name, count in expected.items():
            result = self.result['candidates'][name]
            self.assertEqual(result['trainable_parameters'], count)
            self.assertEqual(result['PEFT_meta_instantiation_verified_parameters'], count)

    def test_grouped_query_dimensions_are_not_assumed_square(self):
        dims = self.result['module_dimensions']
        self.assertEqual((dims['q_proj']['in'], dims['q_proj']['out']), (2560, 4096))
        self.assertEqual((dims['v_proj']['in'], dims['v_proj']['out']), (2560, 1024))
        self.assertEqual((dims['down_proj']['in'], dims['down_proj']['out']), (9728, 2560))
        self.assertTrue(all(d['count'] == 36 for d in dims.values()))

    def test_rank_four_state_boundary_and_no_paged_buffers(self):
        state = self.result['candidates']['qv_r4']['optimizer_formula']
        self.assertEqual(state['min_tensor_elements'], 4096)
        for candidate in self.result['candidates'].values():
            self.assertEqual(candidate['optimizer_formula']['tensors_meeting_paged_buffer_threshold_100000'], 0)

    def test_fp32_parameter_bytes_are_not_total_vram_prediction(self):
        qv = self.result['candidates']['qv_r8']
        self.assertEqual(qv['EXACT_raw_parameter_bytes']['FP32'], 11796480)
        self.assertGreater(qv['ESTIMATED_FP32_weight_gradient_optimizer_payload_bytes'], 2*11796480)
        self.assertNotIn('predicted_peak_vram', qv)

    def test_FA_probe_did_not_execute_training_or_cuda(self):
        runtime = self.result['runtime']; probe = runtime['tiny_nontraining_FA_probe']
        self.assertFalse(runtime['cuda_initialized'])
        self.assertTrue(probe['A_frozen'] and probe['B_trainable'])
        self.assertEqual(probe['trainable_before'], 192)
        self.assertEqual(probe['trainable_after'], 64)
        self.assertEqual((probe['forward_calls'], probe['backward_calls'], probe['optimizer_steps']), (0, 0, 0))

    def test_no_corpus_or_evaluation_records_in_analysis(self):
        audit = self.result['audit']
        self.assertEqual(audit['corpus_records_opened'], 0)
        self.assertEqual(audit['evaluation_records_opened'], 0)
        self.assertFalse(any(p.endswith('.jsonl') or p.startswith('evals/') for p in audit['opened_repository_paths']))


if __name__ == '__main__':
    unittest.main(verbosity=2)
