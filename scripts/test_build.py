"""Offline checks for rebuild decisions and upstream resolution."""
import importlib.util
import gzip
import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('build_inputs', Path(__file__).with_name('build.py'))
build = importlib.util.module_from_spec(spec)
spec.loader.exec_module(build)


class BuildInputsTest(unittest.TestCase):
    def setUp(self):
        build.revision.cache_clear()
        build.pinned_image.cache_clear()
        build.npm_version.cache_clear()
        build.alpine_versions.cache_clear()
        build.nodesource_version.cache_clear()

    def test_annotated_tag_resolves_commit_not_tag_object(self):
        tag, commit = 'a' * 40, 'b' * 40
        result = subprocess.CompletedProcess([], 0, f'{tag}\trefs/tags/v6.5.0.0\n{commit}\trefs/tags/v6.5.0.0^{{}}\n')
        with patch.object(build.subprocess, 'run', return_value=result):
            self.assertEqual(build.revision('repo', 'v6.5.0.0'), commit)

    def test_missing_source_ref_fails(self):
        with patch.object(build.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0, '')):
            with self.assertRaises(ValueError):
                build.revision('repo', 'missing')

    def test_registry_failure_is_not_treated_as_missing_image(self):
        with patch.object(build.subprocess, 'run', return_value=subprocess.CompletedProcess([], 1, '', 'connection timed out')):
            with self.assertRaises(RuntimeError):
                build.image_info('image', missing_ok=True)
        with patch.object(build.subprocess, 'run', return_value=subprocess.CompletedProcess([], 1, '', 'manifest unknown')):
            self.assertIsNone(build.image_info('image', missing_ok=True))

    def test_inspect_multi_platform_labels(self):
        response = {'manifest': {'digest': 'sha256:abc'},
                    'image': {'linux/amd64': {'config': {'Labels': {build.LABEL: 'expected'}}}}}
        with patch.object(build.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0, json.dumps(response))):
            self.assertEqual(build.image_info('image')['labels'][build.LABEL], 'expected')

    def test_skip_only_matching_published_main_image(self):
        published = {'digest': 'sha256:abc', 'labels': {build.LABEL: 'expected'}}
        for ref, expected, exists, decision in [
            ('refs/heads/main', 'expected', published, 'false'),
            ('refs/heads/main', 'changed', published, 'true'),
            ('refs/heads/feature', 'expected', published, 'true'),
            ('refs/heads/main', 'expected', None, 'true'),
        ]:
            with self.subTest(ref=ref, expected=expected, exists=exists):
                outputs = {}
                with patch.dict(os.environ, IMAGE='image', GITHUB_REF=ref, BUILD_INPUTS=json.dumps({'fingerprint': expected})), \
                     patch.object(build, 'image_info', return_value=exists), \
                     patch.object(build, 'output', side_effect=lambda k, v: outputs.update({k: v})), \
                     patch('sys.stdout', new=io.StringIO()):
                    build.check_image()
                self.assertEqual(outputs['build'], decision)
                self.assertEqual(outputs['image'], 'image@sha256:abc' if decision == 'false' else '')

    def test_weekly_and_manual_refresh(self):
        with patch.dict(os.environ, FORCE_REFRESH='false'):
            self.assertRegex(build.refresh_key(), r'^\d{4}-W\d{2}$')
        with patch.dict(os.environ, FORCE_REFRESH='true', GITHUB_RUN_ID='123'):
            self.assertEqual(build.refresh_key(), 'manual-123')

    def test_runtime_shared_across_patch_versions_and_branch(self):
        entry = {'profile': 'shopware-6.5', 'flavour': 'debian', 'shopware-version': 'v6.5.0.0'}
        with patch.dict(os.environ, DOCKER_REPOSITORY='repo'), \
             patch.object(build, 'pinned_image', return_value='base@sha256:abc'), \
             patch.object(build, 'nodesource_version', return_value='18.20.8-1nodesource1'), \
             patch.object(build, 'npm_version', return_value='9.9.4'):
            first = build.runtime_inputs(entry, '2026-W40')
            entry['shopware-version'] = '6.5.x'
            self.assertEqual(first, build.runtime_inputs(entry, '2026-W40'))
            self.assertNotEqual(first['fingerprint'], build.runtime_inputs(entry, '2026-W41')['fingerprint'])
            with patch.object(build, 'pinned_image', return_value='base@sha256:changed'):
                self.assertNotEqual(first['fingerprint'], build.runtime_inputs(entry, '2026-W40')['fingerprint'])
            with patch.object(build, 'nodesource_version', return_value='18.20.9-1nodesource1'):
                self.assertNotEqual(first['fingerprint'], build.runtime_inputs(entry, '2026-W40')['fingerprint'])

    def test_base_matrix_uses_profiles_and_skips_frozen_bases(self):
        matrix = build.base_matrix()["include"]
        self.assertEqual(len(matrix), 2)
        self.assertEqual({(e["flavour"], e["php-version"], e["distribution-version"]) for e in matrix},
                         {("alpine", "8.3", "3.19"), ("debian", "8.3", "bookworm")})

    def test_new_php_and_distribution_need_only_profile_changes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'alpine').mkdir()
            (root / 'alpine/build-profiles.toml').write_text(
                '[profiles.custom]\nphp = "8.4"\ndistribution = "3.23"\n'
                'node = "distribution"\nnpm = "distribution"\nfrozen-base = false\n')
            with patch.dict(os.environ, DOCKER_REPOSITORY='repo'), \
                 patch.object(build, 'ROOT', root), \
                 patch.object(build, 'pinned_image', return_value='base@sha256:abc') as image, \
                 patch.object(build, 'alpine_versions', return_value={'nodejs': '24.0.0-r1', 'npm': '11.0.0-r0'}) as packages:
                resolved = build.runtime_inputs({'flavour': 'alpine', 'profile': 'custom'}, 'refresh')
                bases = build.base_matrix()['include']
            image.assert_called_once_with('repo-base:8.4-alpine')
            packages.assert_called_once_with('3.23')
            self.assertEqual(resolved['distribution'], '3.23')
            self.assertEqual(resolved['node-major'], '24')
            self.assertEqual(resolved['playwright-version'], '')
            self.assertEqual(bases, [{'flavour': 'alpine', 'php-version': '8.4', 'distribution-version': '3.23'}])

    def test_unknown_profile_fails_before_network_resolution(self):
        with self.assertRaisesRegex(ValueError, 'Unknown debian build profile'):
            build.runtime_inputs({'flavour': 'debian', 'profile': 'missing'}, 'refresh')

    def test_local_build_uses_same_resolved_inputs_as_ci(self):
        from argparse import Namespace
        entry = {'flavour': 'debian', 'profile': 'shopware-6.5', 'shopware-version': '6.5.x'}
        with patch.dict(os.environ, DOCKER_REPOSITORY='repo'), \
             patch.object(build, 'pinned_image', return_value='base@sha256:abc'), \
             patch.object(build, 'nodesource_version', return_value='18.20.8-1nodesource1'), \
             patch.object(build, 'npm_version', return_value='9.9.4'), \
             patch.object(build, 'refresh_key', return_value='refresh'), \
             patch.object(build, 'revision', return_value='a' * 40), \
             patch.object(build.subprocess, 'run') as run, \
             patch('sys.stdout', new=io.StringIO()):
            ci = build.runtime_inputs(entry, 'refresh')
            args = Namespace(flavour='debian', profile='shopware-6.5', target='shopware',
                             shopware_version='6.5.x', template='repo', force_refresh=False,
                             dry_run=False, tag='test')
            build.local_build(args)
        command = run.call_args.args[0]
        self.assertEqual(command[command.index('BASE_IMAGE=base@sha256:abc')-1], '--build-arg')
        for argument in build.docker_arguments(ci)[1::2]:
            self.assertIn(argument, command)
        self.assertIn('SHOPWARE_SHA=' + 'a' * 40, command)

    def test_npm_major_selects_highest_stable_version(self):
        data = {'versions': {v: {} for v in ['9.9.3', '9.10.0', '9.11.0-beta.1', '10.0.0']}}
        with patch.object(build, 'download', return_value=json.dumps(data).encode()):
            self.assertEqual(build.npm_version('npm', 9), '9.10.0')

    def test_nodesource_selects_newest_node_and_packaging_revision(self):
        versions = ['22.9.0-1nodesource1', '22.10.0-1nodesource1', '22.10.0-2nodesource1']
        data = '\n\n'.join(f'Package: nodejs\nVersion: {v}' for v in versions)
        with patch.object(build, 'download', return_value=gzip.compress(data.encode())):
            self.assertEqual(build.nodesource_version('22'), versions[-1])

    def test_merge_tracks_source_and_runtime_independently(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'debian').mkdir()
            (root / 'debian/Dockerfile').write_text('recipe')
            runtime = {'runtime-id': 'test', 'fingerprint': 'runtime-inputs', 'runtime-image': 'runtime@sha256:abc', 'refresh': '2026-W40'}
            entry = {'runtime-id': 'test', 'flavour': 'debian', 'template': 'repo', 'shopware-sha': 'a' * 40, 'shopware-version': '6.5.x'}
            (root / 'runtime-test.json').write_text(json.dumps(runtime))
            outputs = {}
            previous = Path.cwd()
            try:
                os.chdir(root)
                def merged():
                    (root / 'build-plan.json').write_text(json.dumps({'entries': [entry]}))
                    with patch.object(build, 'output', side_effect=lambda k, v: outputs.update({k: v})):
                        build.merge()
                    return json.loads(outputs['matrix'])['include'][0]['fingerprint']
                first = merged()
                self.assertEqual(first, merged())
                entry['shopware-sha'] = 'b' * 40
                self.assertNotEqual(first, merged())
                entry['shopware-sha'] = 'a' * 40
                runtime['runtime-image'] = 'runtime@sha256:changed'
                (root / 'runtime-test.json').write_text(json.dumps(runtime))
                self.assertNotEqual(first, merged())
                runtime['runtime-image'] = 'runtime@sha256:abc'
                (root / 'runtime-test.json').write_text(json.dumps(runtime))
                (root / 'debian/Dockerfile').write_text('changed recipe')
                self.assertNotEqual(first, merged())
            finally:
                os.chdir(previous)


if __name__ == '__main__':
    unittest.main()
