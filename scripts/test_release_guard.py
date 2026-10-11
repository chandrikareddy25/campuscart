import contextlib
import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import release_guard as guard

class ReleaseGuardTests(unittest.TestCase):
    def scenario(self, mode='transactional', result='passed', newer=False, schema_ok=True, data_changed=False):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);(root/'release').mkdir();(root/'k8s').mkdir()
            previous={s:f'ghcr.io/test/campuscart-{s}:previous' for s in ('backend','frontend')}
            candidate={s:f'ghcr.io/test/campuscart-{s}:candidate' for s in ('backend','frontend')}
            policy=root/'release/known-good.json';manifest=root/'k8s/application.yaml'
            policy.write_text(json.dumps({'schema_sha256':'approved','images':previous}))
            manifest.write_text('\n'.join('image: '+v for v in candidate.values()))
            calls=[]
            def fake_git(*args):return 'newer' if newer else 'deployment'
            def commit(message,files):calls.append(message);return 'restored'
            snapshots=[{'orders':'changed'},{'orders':'changed'}] if data_changed else [{'orders':'original'}]*2
            with patch.multiple(guard,ROOT=root,POLICY=policy,MANIFEST=manifest),patch.object(guard,'schema_hash',return_value='approved' if schema_ok else 'different'),patch.object(guard,'kube',return_value=type('R',(),{'returncode':0})()),patch.object(guard,'wait_release',return_value=True),patch.object(guard,'probe',side_effect=[{'status':result},{'status':'passed'}]),patch.object(guard,'remote_snapshot',side_effect=snapshots),patch.object(guard,'git',side_effect=fake_git),patch.object(guard,'commit_files',side_effect=commit),patch.dict(os.environ,{'RELEASE_TEST_PASSWORD':'not-a-real-secret','RELEASE_BASELINE':json.dumps({'orders':'original'})}),patch('sys.argv',['guard','--revision','deployment','--mode',mode]),contextlib.redirect_stdout(io.StringIO()):
                code=guard.main()
            report=json.loads((root/'release-results/report.json').read_text())
            return code,report,calls,json.loads(policy.read_text()),manifest.read_text()
    def test_verified_release_promotes_baseline(self):
        code,r,c,p,_=self.scenario();self.assertEqual(code,0);self.assertEqual(r['status'],'passed');self.assertEqual(len(c),1);self.assertTrue(p['images']['backend'].endswith(':candidate'))
    def test_health_only_never_promotes_unverified_baseline(self):
        code,r,c,p,_=self.scenario(mode='health');self.assertEqual(code,0);self.assertEqual(c,[]);self.assertTrue(p['images']['backend'].endswith(':previous'))
    def test_confirmed_failure_restores_both_images_and_checks_recovery(self):
        code,r,c,p,text=self.scenario(result='failed');self.assertEqual(code,1);self.assertEqual(r['status'],'rolled_back');self.assertTrue(r['data_integrity_preserved']);self.assertNotIn(':candidate',text)
    def test_inconclusive_probe_does_not_roll_back(self):
        _,r,c,_,_=self.scenario(result='inconclusive');self.assertEqual(c,[]);self.assertEqual(r['status'],'inconclusive')
    def test_newer_commit_is_never_overwritten(self):
        _,r,c,_,_=self.scenario(result='failed',newer=True);self.assertEqual(c,[]);self.assertIn('Main changed',r['reason'])
    def test_schema_change_blocks_automatic_restoration(self):
        _,r,c,_,_=self.scenario(schema_ok=False);self.assertEqual(c,[]);self.assertIn('Schema changed',r['reason'])
    def test_changed_business_data_rejects_release(self):
        _,r,c,_,_=self.scenario(data_changed=True);self.assertEqual(r['status'],'recovery_failed');self.assertFalse(r['data_integrity_preserved']);self.assertEqual(len(c),1)
    def test_image_replacement_preserves_database_image(self):
        text='image: postgres:17\nimage: ghcr.io/a/campuscart-backend:one\nimage: ghcr.io/a/campuscart-frontend:one\n'
        out=guard.replace_images(text,{'backend':'ghcr.io/a/campuscart-backend:two','frontend':'ghcr.io/a/campuscart-frontend:two'})
        self.assertIn('postgres:17',out);self.assertEqual(out.count(':two'),2)

if __name__=='__main__':unittest.main()
