import importlib.util
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]


def load_script(name):
    spec=importlib.util.spec_from_file_location(name,ROOT/'.github/scripts'/f'{name}.py')
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


prepare=load_script('prepare_release')
sync=load_script('sync_zenodo_doi')


class ReleaseMetadataTests(unittest.TestCase):
    def test_html_prepare_and_sync_preserve_one_doi_badge(self):
        original=(ROOT/'README.md').read_text()
        pending=prepare.update_badges_for_pending_doi(original)
        self.assertIn('<h1 align="center">ORCA PED Analyzer</h1>',pending)
        self.assertIn('DOI-pending-lightgrey',pending)
        self.assertEqual(pending.count('alt="DOI"'),1)
        self.assertEqual(pending,prepare.update_badges_for_pending_doi(pending))
        published=sync.set_readme_badges(pending,'10.5281/zenodo.123456')
        self.assertEqual(published.count('alt="DOI"'),1)
        self.assertNotIn('DOI-pending-lightgrey',published)
        self.assertIn('https://doi.org/10.5281/zenodo.123456',published)
        self.assertEqual(published,sync.set_readme_badges(published,'10.5281/zenodo.123456'))
        for platform in ('Windows','Linux','macOS'):
            self.assertIn(f'alt="{platform}"',published)

    def test_markdown_header_remains_supported(self):
        pending=prepare.update_badges_for_pending_doi('# ORCA PED Analyzer\n\nText\n')
        self.assertIn(prepare.VERSION_BADGE,pending)
        self.assertIn(prepare.DOI_PENDING_BADGE,pending)
        self.assertEqual(pending,prepare.update_badges_for_pending_doi(pending))
        published=sync.set_readme_badges(pending,'10.5281/zenodo.123456')
        self.assertNotIn('DOI-pending',published)
        self.assertEqual(published.count('[![DOI]'),1)

    def test_html_header_without_doi_gets_one_badge(self):
        text=prepare.HTML_DOI_BADGE_RE.sub('',(ROOT/'README.md').read_text())
        self.assertEqual(prepare.update_badges_for_pending_doi(text).count('alt="DOI"'),1)

    def test_complete_prepare_script_on_repository_metadata(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            for filename in ('.github/scripts/prepare_release.py','orca_ped_analyzer.py',
                             'README.md','docs/ORCA_PED_Analyzer_Manual.md','CITATION.cff'):
                dest=root/filename
                dest.parent.mkdir(parents=True,exist_ok=True)
                shutil.copyfile(ROOT/filename,dest)
            env=dict(os.environ,GITHUB_ACTIONS='false')
            result=subprocess.run([sys.executable,str(root/'.github/scripts/prepare_release.py')],
                                  cwd=root,env=env,text=True,capture_output=True)
            self.assertEqual(result.returncode,0,result.stderr)
            version=result.stdout.strip()
            self.assertRegex(version,r'^\d+\.\d+\.\d+$')
            self.assertEqual(prepare.read_version((root/'orca_ped_analyzer.py').read_text()),version)
            for filename in ('README.md','docs/ORCA_PED_Analyzer_Manual.md','CITATION.cff'):
                self.assertIn(version,(root/filename).read_text())
            self.assertIn('DOI-pending-lightgrey',(root/'README.md').read_text())


if __name__=='__main__':
    unittest.main()
