"""Fail before deployment if the approved rollback baseline is inconsistent."""
import json
import os
from pathlib import Path
from release_guard import ROOT, MANIFEST, POLICY, schema_hash, images, replace_images

policy=json.loads(POLICY.read_text())
if schema_hash()!=policy['schema_sha256']:
    raise SystemExit('Migration files changed. Review rollback compatibility before release.')
if images(MANIFEST.read_text())!=policy['images']:
    raise SystemExit('Current manifest is not the verified baseline. Finish verification first.')
owner=os.environ['GITHUB_REPOSITORY_OWNER'].lower()
target={s:f'ghcr.io/{owner}/campuscart-{s}:{os.environ["GITHUB_SHA"]}' for s in ('backend','frontend')}
MANIFEST.write_text(replace_images(MANIFEST.read_text(),target))
