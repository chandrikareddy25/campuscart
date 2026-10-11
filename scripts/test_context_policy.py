import unittest
from context_policy import decide,compare
class ContextPolicyTests(unittest.TestCase):
    def test_valid_checkout_accepts(self):self.assertEqual(decide({'status':'passed'})['action'],'accept')
    def test_wrong_total_rejects(self):self.assertEqual(decide({'status':'failed','kind':'integrity'})['action'],'reject')
    def test_checkout_500_with_ready_dependency_rejects(self):self.assertEqual(decide({'status':'failed','kind':'http','http_status':500,'dependency_ready':True})['action'],'reject')
    def test_dependency_outage_does_not_prove_release_defect(self):self.assertEqual(decide({'status':'failed','kind':'http','http_status':500,'dependency_ready':False})['action'],'retry')
    def test_service_unavailable_retries(self):self.assertEqual(decide({'status':'failed','kind':'http','http_status':503})['action'],'retry')
    def test_known_constraint_defers_without_accepting(self):self.assertEqual(decide({'status':'failed','kind':'business_precondition'})['action'],'defer')
    def test_supported_conflict_defers(self):self.assertEqual(decide({'status':'failed','kind':'http','http_status':409,'constraint_confirmed':True})['action'],'defer')
    def test_unexplained_conflict_rejects(self):self.assertEqual(decide({'status':'failed','kind':'http','http_status':409,'constraint_confirmed':False})['action'],'reject')
    def test_cleanup_failure_prevents_retry(self):self.assertEqual(decide({'status':'failed','kind':'http','http_status':503,'cleanup_failed':True})['action'],'defer')
    def test_baseline_comparison_is_explicit(self):self.assertEqual(compare({'status':'failed','kind':'business_precondition'}),{'health_only':'accept','existing_guard':'reject','contextual_guard':'defer'})
if __name__=='__main__':unittest.main()
