#!/usr/bin/env python3
"""Execute README examples against a required console in owned local fixtures."""
import argparse
import hashlib
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

REPO = pathlib.Path(os.environ.get('GO_DOCS_TEST_REPO', pathlib.Path(__file__).resolve().parent.parent))
CONSOLE = None
BASH = os.environ.get('GO_DOCS_TEST_BASH') or shutil.which('bash')
URLS = {'console': 'https://github.com/bashcmdr/console.git',
        'go': 'https://github.com/bashcmdr/cartridge-go.git'}


class ReadmeExamples(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='bcm-go-readme-owned-')
        self.addCleanup(self.temp.cleanup)
        self.root = pathlib.Path(self.temp.name)
        self.home = self.root / 'home space'
        self.tools = self.root / 'tools'
        self.home.mkdir(); self.tools.mkdir()
        self.calls = []
        self.gitlog = self.root / 'git-calls.jsonl'; self.gitlog.write_text('')
        self.trace = self.root / 'forbidden.log'; self.trace.write_text('')
        self.gotrace = self.root / 'go-calls.jsonl'; self.gotrace.write_text('')
        self.env = {'HOME': str(self.home), 'PATH': str(self.tools) + os.pathsep + os.defpath,
                    'TMPDIR': str(self.root), 'LC_ALL': 'C', 'TERM': 'dumb',
                    'BASH_ENV': os.devnull, 'ENV': os.devnull, 'BASHCMDR_QUIET_BOOT': '1',
                    'BASHCMDR_VERBOSITY': '1', 'FORBIDDEN': str(self.trace), 'GO_CALLS': str(self.gotrace), 'GO_TOOLCHAIN_TO_USE': 'go1.22.0',
                    'GIT_CONFIG_NOSYSTEM': '1', 'GIT_CONFIG_GLOBAL': os.devnull,
                    'GIT_ALLOW_PROTOCOL': 'file', 'GIT_TERMINAL_PROMPT': '0'}
        (self.tools / 'bash').symlink_to(BASH)
        for name in ['curl', 'wget', 'sudo', 'service', 'systemctl']:
            path = self.tools / name
            path.write_text('#!' + BASH + '\nprintf "%s\\n" ' + name + ' >> "$FORBIDDEN"\nexit 99\n')
            path.chmod(0o755)
        self.project = self.root / 'project space'; self.project.mkdir()
        self.bootstrap = self.home / 'go bootstrap'
        self.userbin = self.home / 'go workspace/bin'
        (self.bootstrap / 'bin').mkdir(parents=True); self.userbin.mkdir(parents=True)
        self.saved_setting = self.home / '.config/go/env'
        go = self.bootstrap / 'bin/go'
        go.write_text('#!' + sys.executable + '\n' + r'''
import json,os,pathlib,sys
args=sys.argv[1:];home=pathlib.Path(os.environ['HOME']);setting=home/'.config/go/env'
with open(os.environ['GO_CALLS'],'a') as f:f.write(json.dumps({'args':args,'GOTOOLCHAIN':os.environ.get('GOTOOLCHAIN')})+'\n')
def reject():
    with open(os.environ['FORBIDDEN'],'a') as f:f.write('unexpected-go:'+repr(args)+'\n')
    sys.exit(99)
if args==['version']:print('go version fixture')
elif args[:1]==['env']:
    if args[1:2]==['-w']:
        if len(args)!=3 or not args[2].startswith('GOTOOLCHAIN='):reject()
        setting.parent.mkdir(parents=True,exist_ok=True);setting.write_text(args[2]+'\n')
    elif args[1:]==['-u','GOTOOLCHAIN']:setting.unlink(missing_ok=True)
    else:
        values={'GOROOT':os.environ.get('GOROOT',str(home/'go bootstrap')),'GOPATH':os.environ.get('GOPATH',str(home/'go workspace')),'GOBIN':os.environ.get('GOBIN','')}
        if not args[1:] or any(x not in values for x in args[1:]):reject()
        for name in args[1:]:print(values[name])
else:reject()
''')
        go.chmod(0o755)
        (self.tools / 'go').symlink_to(go)
        configured = self.home / 'custom go bootstrap/bin/go'
        configured.parent.mkdir(parents=True); shutil.copyfile(go, configured); configured.chmod(0o755)
        self.protected = [self.home / x for x in ['.bashrc', '.bash_profile', '.profile']] + [self.project / 'go.mod', self.project / 'go.work']
        for path in self.protected: path.write_text('owned profile sentinel\n')
        self.before = self.snapshot()
        self.sources = {name: self.root / 'sources' / ('source ' + name) for name in URLS}
        for path in self.sources.values(): path.mkdir(parents=True)
        for name in ['bin', 'lib', 'boot']: shutil.copytree(CONSOLE / name, self.sources['console'] / name)
        shutil.copyfile(CONSOLE / 'VERSION', self.sources['console'] / 'VERSION')
        for name in ['main.bashcmdr', 'manifest.json', 'README.md']: shutil.copyfile(REPO / name, self.sources['go'] / name)
        templates = self.root / 'empty templates'; templates.mkdir()
        self.env['GIT_TEMPLATE_DIR'] = str(templates)
        real_git = shutil.which('git')
        self.revisions = {}
        for name, path in self.sources.items():
            for args in [('init', '--quiet', str(path)), ('-C', str(path), 'add', '--all'),
                         ('-C', str(path), '-c', 'user.name=fixture', '-c', 'user.email=fixture@example.invalid',
                          'commit', '--quiet', '-m', 'Owned exact source subset')]:
                subprocess.run([real_git, *args], env=self.env, check=True, capture_output=True, timeout=10)
            self.revisions[name] = subprocess.check_output([real_git, '-C', str(path), 'rev-parse', 'HEAD'], env=self.env, text=True).strip()
        wrapper = self.tools / 'git'
        wrapper.write_text('#!' + sys.executable + '\n' +
            'REAL=' + repr(real_git) + '\nROOT=' + repr(str(self.root)) + '\nLOG=' + repr(str(self.gitlog)) +
            '\nSOURCES=' + repr({URLS[n]: str(p) for n, p in self.sources.items()}) + '\n' + r'''
import json, pathlib, subprocess, sys
args = sys.argv[1:]
with open(LOG, 'a') as stream: stream.write(json.dumps(args) + '\n')
if args[:1] == ['clone']:
    assert args[-2] in SOURCES and pathlib.Path(args[-1]).resolve().is_relative_to(ROOT)
    assert args[:-2] in [['clone'], ['clone', '--quiet', '--']]
    args[-2] = SOURCES[args[-2]]
elif len(args) == 5 and args[0] == '-C' and args[2:] == ['rev-parse', '--verify', 'HEAD^{commit}']:
    assert pathlib.Path(args[1]).resolve().is_relative_to(ROOT)
else:
    sys.exit(96)
sys.exit(subprocess.run([REAL, *args]).returncode)
''')
        wrapper.chmod(0o755)

    def snapshot(self):
        return {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in self.protected}

    def blocks(self, title):
        text = (REPO / 'README.md').read_text()
        match = re.search(r'^## ' + re.escape(title) + r'\n(.*?)(?=^## |\Z)', text, re.M | re.S)
        self.assertIsNotNone(match, 'README section missing: ' + title)
        return re.findall(r'^```bash\n(.*?)^```', match.group(1), re.M | re.S)

    def run_example(self, text, cwd=None):
        p = subprocess.run([BASH, '--noprofile', '--norc', '-e', '-o', 'pipefail', '-c', text],
                           cwd=cwd or self.project, env=self.env, text=True, capture_output=True, timeout=15)
        self.calls.append({'script': text, 'cwd': str(cwd or self.project), 'exit': p.returncode,
                           'stdout': p.stdout, 'stderr': p.stderr})
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertEqual(self.trace.read_text(), '')
        self.assertEqual(self.snapshot(), self.before)
        return p

    def install_and_boot(self):
        blocks = self.blocks('Install and enable')
        self.assertEqual(len(blocks), 2)
        return '\n'.join(blocks)

    def go_calls(self):
        return [json.loads(line) for line in self.gotrace.read_text().splitlines()]

    def test_fresh_install_and_current_shell_initialization(self):
        install, boot = self.blocks('Install and enable')
        self.run_example(install + '\n[[ -z ${BASHCMDR_GO_LOADED-} && :$PATH: != *":$HOME/go workspace/bin:"* ]]\n')
        p = self.run_example(boot + '\n[[ $BASHCMDR_GO_LOADED == 1 && :$PATH: == *":$HOME/go workspace/bin:"* ]]\n')
        self.assertIn('Bash Commander boot status: 0', p.stdout)
        metadata = json.loads((self.home / '.bashcmdr/registry/installed/go-loader.json').read_text())
        self.assertEqual(metadata['source']['commit'], self.revisions['go'])
        self.assertFalse(self.saved_setting.exists())

    def test_discovery_and_current_shell_path_cleanup(self):
        text = self.install_and_boot() + '\n' + self.blocks('Inspect the installed bootstrap')[0]
        text += '\n' + self.blocks('Deactivate')[0]
        text += '\n[[ -z ${BASHCMDR_GO_LOADED-} && :$PATH: != *":$HOME/go workspace/bin:"* ]]\ncommand -v go\n'
        p = self.run_example(text)
        self.assertIn('go version fixture', p.stdout)
        self.assertFalse(self.saved_setting.exists())
        self.assertFalse(any(x['args'][1:2] == ['-w'] for x in self.go_calls()))

    def test_help_diagnostics_and_selected_console_log(self):
        text = self.install_and_boot() + '\n' + self.blocks('Diagnose and get help')[0]
        p = self.run_example(text)
        self.assertIn('Actions:', p.stdout)
        self.assertIn('toolchain-use', p.stdout)
        self.assertIn('Bootstrap executable:', p.stdout)
        self.assertIn('Shell GOTOOLCHAIN:', p.stdout)
        self.assertIn('Console Log', p.stdout)
        self.assertFalse(self.saved_setting.exists())

    def test_optional_saved_toolchain_setting_and_undo(self):
        blocks = self.blocks('Optional persistent toolchain selection')
        self.assertEqual(len(blocks), 2)
        self.run_example(self.install_and_boot() + '\n' + blocks[0] + '\ngo_deactivate\n')
        self.assertEqual(self.saved_setting.read_text(), 'GOTOOLCHAIN=go1.22.0+auto\n')
        self.run_example(blocks[1])
        self.assertFalse(self.saved_setting.exists())
        writes = [x['args'] for x in self.go_calls() if x['args'][1:2] in [['-w'], ['-u']]]
        self.assertEqual(writes, [['env','-w','GOTOOLCHAIN=go1.22.0+auto'], ['env','-u','GOTOOLCHAIN']])

    def system_path_without_go(self):
        # The example needs "no Go on PATH". Some hosts ship one in a default PATH
        # directory (GitHub's ubuntu-24.04 image has /usr/bin/go), so mirror those
        # directories without go/gofmt instead of trusting the host.
        mirror = self.root / 'system path without go'; mirror.mkdir()
        for directory in os.defpath.split(os.pathsep):
            if not directory or not os.path.isdir(directory):
                continue
            for entry in os.scandir(directory):
                if entry.name in ('go', 'gofmt') or os.path.lexists(mirror / entry.name):
                    continue
                (mirror / entry.name).symlink_to(entry.path)
        return str(mirror)

    def test_configured_root_fallback_without_path_go(self):
        (self.tools / 'go').unlink()
        self.env['PATH'] = str(self.tools) + os.pathsep + self.system_path_without_go()
        text =self.blocks('Configured root')[0] + '\n' + self.install_and_boot()
        text += r'''
[[ $GOROOT == "$HOME/custom go bootstrap" && $(type -P go) == "$GOROOT/bin/go" && $BASHCMDR_GO_LOADED == 1 ]] || exit 91
go_deactivate || exit $?
[[ $GOROOT == "$HOME/custom go bootstrap" && -z ${BASHCMDR_GO_LOADED-} && :$PATH: != *":$GOROOT/bin:"* ]] || exit 92
'''
        self.run_example(text)
        self.assertFalse(self.saved_setting.exists())

    def test_bare_help_lists_actions_and_source_limits(self):
        blocks = self.blocks('Diagnose and get help')
        p = self.run_example(blocks[1], cwd=self.sources['go'])
        self.assertIn('Actions:', p.stdout)
        for action in ['setup', 'activate', 'deactivate', 'diagnose', 'help', 'toolchain-use']:
            self.assertIn(action, p.stdout)
        self.assertIn('saved', p.stdout)
        self.assertIn('go env -u GOTOOLCHAIN', p.stdout)
        before = self.gotrace.read_text()
        self.run_example('source main.bashcmdr activate\n[[ -z ${BASHCMDR_GO_LOADED-} ]]\ndeclare -F go_activate >/dev/null\n', cwd=self.sources['go'])
        self.assertEqual(self.gotrace.read_text(), before)
        self.assertFalse(self.saved_setting.exists())

    def test_missing_console_input_is_error(self):
        p = subprocess.run([sys.executable, str(pathlib.Path(__file__).resolve())],
                           env={'PATH': os.defpath}, text=True, capture_output=True, timeout=10)
        self.assertNotEqual(p.returncode, 0)
        self.assertIn('--console-root', p.stderr)
        self.assertNotIn('skipped=', p.stderr)

    def tearDown(self):
        directory = os.environ.get('GO_DOCS_TEST_EVIDENCE_DIR')
        if directory:
            target = pathlib.Path(directory) / self.id().split('.')[-1]
            target.mkdir(parents=True, exist_ok=True)
            data = {'calls': self.calls, 'source_files': {'README.md': hashlib.sha256((REPO / 'README.md').read_bytes()).hexdigest(),
                    'main.bashcmdr': hashlib.sha256((REPO / 'main.bashcmdr').read_bytes()).hexdigest(),
                    'manifest.json': hashlib.sha256((REPO / 'manifest.json').read_bytes()).hexdigest()},
                    'owned_fixture_commits': self.revisions, 'intercepted_git': self.gitlog.read_text(),
                    'forbidden': self.trace.read_text(), 'go_calls': self.gotrace.read_text(), 'saved_setting_exists': self.saved_setting.exists(),
                    'protected_before': self.before, 'protected_after': self.snapshot(), 'bash': BASH}
            (target / 'records.json').write_text(json.dumps(data, indent=2) + '\n')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__, add_help=False)
    parser.add_argument('--console-root')
    options, remaining = parser.parse_known_args()
    if not options.console_root: parser.error('--console-root is required; missing console inputs must not become a skipped pass')
    CONSOLE = pathlib.Path(options.console_root).resolve()
    if not all((CONSOLE / p).is_file() for p in ['VERSION', 'bin/bashcmdr', 'boot/shell-init.bashcmdr', 'lib/core.bashcmdr']):
        parser.error('--console-root must name a complete selected console source')
    unittest.main(argv=[sys.argv[0], *remaining], verbosity=2)
