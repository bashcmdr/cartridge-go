#!/usr/bin/env python3
"""Owned Go bootstrap/context/API probes; no real Go, downloads or environment writes."""
import datetime
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

REPO=Path(os.environ.get('GO_RUNTIME_TEST_REPO',Path(__file__).resolve().parents[1])).resolve()
BASH=Path(os.environ.get('GO_RUNTIME_TEST_BASH',shutil.which('bash'))).resolve()
EVIDENCE=Path(os.environ['GO_RUNTIME_TEST_EVIDENCE_DIR'] if 'GO_RUNTIME_TEST_EVIDENCE_DIR' in os.environ
              else tempfile.mkdtemp(prefix='bcm-go-runtime-records-')).resolve()
EVIDENCE.mkdir(parents=True,exist_ok=True)


class GoRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='bcm-go-runtime-owned-')
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.home=self.root/'home space';self.home.mkdir()
        self.tools=self.root/'tools';self.tools.mkdir()
        self.go_root=self.root/'bootstrap space'
        self.go=self.fake_go(self.go_root/'bin/go','A')
        self.user_bin=self.home/'default go path/bin';self.user_bin.mkdir(parents=True)
        self.record=EVIDENCE/self._testMethodName;self.record.mkdir(exist_ok=True)
        self.spy=self.record/'go-argv.jsonl';self.spy.write_text('')
        self.cyg_spy=self.record/'cygpath-argv.jsonl';self.cyg_spy.write_text('')
        self.safety=self.record/'blocked-host-go.log';self.safety.write_text('')
        env_shim=self.tools/'env'
        env_shim.write_text('#!'+sys.executable+'\n'+
            'import os,sys\n'
            'if len(sys.argv)<3 or sys.argv[1]!="GOTOOLCHAIN=local":sys.exit(95)\n'
            'target=os.path.realpath(sys.argv[2]);root=os.path.realpath(os.environ["OWNED_ROOT"])\n'
            'if os.path.commonpath([target,root])!=root:\n'
            '  with open(os.environ["GO_SAFETY"],"a") as f:f.write("blocked-env-host-go\\n")\n'
            '  sys.exit(96)\n'
            'environ=dict(os.environ);environ["GOTOOLCHAIN"]="local"\n'
            'os.execve(sys.argv[2],sys.argv[2:],environ)\n')
        env_shim.chmod(0o755)
        self.calls=[];self.addCleanup(self.save)
        self.env={'HOME':str(self.home),'PATH':str(self.tools),'GOROOT':str(self.go_root),
                  'GO_SOURCE':str(REPO/'main.bashcmdr'),'TOOLS':str(self.tools),'GO_BIN':str(self.go.parent),
                  'USER_BIN':str(self.user_bin),'GO_SPY':str(self.spy),'CYG_SPY':str(self.cyg_spy),
                  'GO_SAFETY':str(self.safety),'OWNED_ROOT':str(self.root),
                  'DEFAULT_GOPATH':str(self.user_bin.parent),'BASH_ENV':os.devnull,'ENV':os.devnull,'LC_ALL':'C'}
        self.protected={}
        for name in ['.profile','.bash_profile','.bashrc','go.mod','go.work']:
            path=self.home/name;path.write_text('owned sentinel '+name+'\n');self.protected[name]=path.read_text()

    def save(self):
        (self.record/'calls.json').write_text(json.dumps(self.calls,indent=2)+'\n')
        (self.record/'protected-after.json').write_text(json.dumps({n:(self.home/n).read_text() for n in self.protected},indent=2)+'\n')

    def fake_go(self,path,tag):
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text('#!'+sys.executable+'\n'+
            'import json,os,sys\n'
            'args=sys.argv[1:]\n'
            'with open(os.environ["GO_SPY"],"a") as f:f.write(json.dumps({"exe":sys.argv[0],"argv":args,"GOTOOLCHAIN":os.environ.get("GOTOOLCHAIN"),"GOROOT":os.environ.get("GOROOT"),"GOPATH":os.environ.get("GOPATH"),"GOBIN":os.environ.get("GOBIN")})+"\\n")\n'
            'key=" ".join(args)\n'
            'if os.environ.get("FAIL_QUERY")==key:print("/partial-output");sys.exit(37)\n'
            'if os.environ.get("EMPTY_QUERY")==key:sys.exit(0)\n'
            'if args==["version"]:print('+repr('go version fixture-'+tag)+');sys.exit(0)\n'
            'if len(args)==2 and args[0]=="env":\n'
            '  if args[1]=="GOBIN":print(os.environ.get("FAKE_GOBIN",os.environ.get("GOBIN","")));sys.exit(0)\n'
            '  if args[1]=="GOPATH":print(os.environ.get("FAKE_GOPATH",os.environ.get("GOPATH",os.environ["DEFAULT_GOPATH"])));sys.exit(0)\n'
            '  if args[1]=="GOTOOLCHAIN":print(os.environ.get("GOTOOLCHAIN","auto"));sys.exit(0)\n'
            'if len(args)==3 and args[:2]==["env","-w"]:sys.exit(0)\n'
            'sys.exit(99)\n')
        path.chmod(0o755)
        return path

    def cygpath(self,mapping,mode='ok'):
        path=self.tools/'cygpath'
        path.write_text('#!'+sys.executable+'\n'+
            'import json,os,sys\n'
            'with open(os.environ["CYG_SPY"],"a") as f:f.write(json.dumps(sys.argv[1:])+"\\n")\n'+
            'mapping='+repr({k:str(v) for k,v in mapping.items()})+'\n'+
            'mode='+repr(mode)+'\n'
            'if mode=="failed":print("/partial-conversion");sys.exit(38)\n'
            'if mode=="empty":sys.exit(0)\n'
            'if mode=="relative":print("not-absolute");sys.exit(0)\n'
            'if sys.argv[1:3]!=["-u","--"] or len(sys.argv)!=4:sys.exit(97)\n'
            'if sys.argv[3] not in mapping:sys.exit(98)\n'
            'print(mapping[sys.argv[3]])\n')
        path.chmod(0o755)

    def shell(self,body,*,extra=None,strict=True):
        # The old implementation has an absolute host fallback. Intercept it
        # inside Bash too, so archived regressions never execute a real Go.
        guard='function /usr/local/go/bin/go { printf "blocked-direct-host-go\\n" >> "$GO_SAFETY"; return 99; }\n'
        script=('set -euo pipefail\n' if strict else '')+guard+'source "$GO_SOURCE"\n'+body
        p=subprocess.run([str(BASH),'--noprofile','--norc','-c',script],cwd=self.home,
                         env={**self.env,**(extra or {})},text=True,capture_output=True,timeout=10)
        self.calls.append({'script':script,'extra':extra or {},'exit':p.returncode,'stdout':p.stdout,'stderr':p.stderr})
        for name,data in self.protected.items():self.assertEqual((self.home/name).read_text(),data,name)
        self.assertEqual(self.safety.read_text(),'','Host Go execution was blocked by the owned fixture')
        return p

    def good(self,p):self.assertEqual(p.returncode,0,p.stdout+p.stderr)
    def queries(self):return [json.loads(line) for line in self.spy.read_text().splitlines()]

    def test_exported_marker_child_with_reset_path_revalidates_and_repairs(self):
        self.good(self.shell('go_activate; parent=$PATH; '
            '"$BASH" --noprofile --norc -c \'PATH=$TOOLS; source "$GO_SOURCE"; go_activate; '
            '[[ :$PATH: == *":$GO_BIN:"* && :$PATH: == *":$USER_BIN:"* && $BASHCMDR_GO_LOADED == 1 ]]\'; '
            '[[ $PATH == "$parent" ]]'))

    def test_child_with_inherited_path_does_not_own_parent_insertions(self):
        self.good(self.shell('go_activate; parent=$PATH; '
            '"$BASH" --noprofile --norc -c \'source "$GO_SOURCE"; before=$PATH; go_activate; '
            'go_deactivate; [[ $PATH == "$before" && ! ${BASHCMDR_GO_LOADED+x} ]]\'; [[ $PATH == "$parent" ]]'))

    def test_repeat_source_after_current_shell_path_reset_preserves_single_ownership(self):
        self.good(self.shell('go_activate; PATH=$TOOLS; source "$GO_SOURCE"; go_activate; repaired=$PATH; '
            'go_activate; [[ $PATH == "$repaired" ]]; go_deactivate; [[ $PATH == "$TOOLS" && ! ${BASHCMDR_GO_LOADED+x} ]]'))

    def test_effective_path_executable_wins_over_preferred_root_in_all_callbacks(self):
        other=self.fake_go(self.root/'other/bin/go','B');(self.tools/'go').symlink_to(other)
        p=self.shell('before=$PATH; go_setup; go_diagnose; go_activate; [[ $PATH == "$before:$USER_BIN" ]]')
        self.good(p);self.assertIn('fixture-B',p.stdout);self.assertNotIn('fixture-A',p.stdout)
        self.assertTrue(self.queries());self.assertTrue(all(q['exe']==str(self.tools/'go') for q in self.queries()))

    def test_spaced_bootstrap_and_explicit_gobin_are_quoted_and_added(self):
        custom=self.home/'custom user bin [x]';custom.mkdir()
        self.good(self.shell('export GOBIN="$CUSTOM"; go_activate; '
            '[[ :$PATH: == *":$GO_BIN:"* && :$PATH: == *":$CUSTOM:"* && $GOBIN == "$CUSTOM" ]]',extra={'CUSTOM':str(custom)}))
        self.assertIn(['env','GOBIN'],[q['argv'] for q in self.queries()])

    def test_gopath_list_uses_first_directory_without_overwriting_configuration(self):
        first=self.home/'first path';second=self.home/'second path'
        (first/'bin').mkdir(parents=True);(second/'bin').mkdir(parents=True)
        self.good(self.shell('export GOPATH="$FIRST:$SECOND"; before=$(declare -p GOPATH); go_activate; '
            '[[ :$PATH: == *":$FIRST/bin:"* && :$PATH: != *":$SECOND/bin:"* && $(declare -p GOPATH) == "$before" ]]',
            extra={'FIRST':str(first),'SECOND':str(second)}))

    def test_readonly_caller_go_configuration_is_preserved_and_probes_stay_local(self):
        self.good(self.shell('export GOBIN="$USER_BIN" GOPATH="$DEFAULT_GOPATH" GOTOOLCHAIN=go9.9.9+auto; '
            'readonly GOBIN GOPATH GOROOT GOTOOLCHAIN; before=$(declare -p GOBIN GOPATH GOROOT GOTOOLCHAIN); '
            'go_setup; go_activate; go_diagnose; go_deactivate; '
            '[[ $(declare -p GOBIN GOPATH GOROOT GOTOOLCHAIN) == "$before" ]]'))
        self.assertTrue(self.queries());self.assertTrue(all(q['GOTOOLCHAIN']=='local' for q in self.queries()))
        self.assertFalse(any('-w' in q['argv'] for q in self.queries()))

    def test_synthetic_absent_candidate_is_dormant_and_clears_stale_marker(self):
        self.good(self.shell('_go_cmd() { return 1; }; export BASHCMDR_GO_LOADED=1; before=$PATH; '
            'go_activate; [[ ! ${BASHCMDR_GO_LOADED+x} && $PATH == "$before" ]]; go_setup; go_diagnose'))
        self.assertEqual(self.queries(),[])

    def test_invalid_configured_root_is_failure_without_host_bootstrap_fallback(self):
        p=self.shell('export GOROOT="$HOME/absent-root"; before=$PATH; '
            'if go_activate; then exit 81; fi; [[ $PATH == "$before" && ! ${BASHCMDR_GO_LOADED+x} ]]')
        self.good(p);self.assertIn('Configured GOROOT',p.stderr);self.assertEqual(self.queries(),[])

    def test_failed_or_empty_version_and_missing_env_never_publish_context(self):
        for extra in [{'FAIL_QUERY':'version'},{'EMPTY_QUERY':'version'}]:
            with self.subTest(extra=extra):
                self.good(self.shell('export BASHCMDR_GO_LOADED=1; before=$PATH; if go_activate; then exit 82; fi; '
                    '[[ $PATH == "$before" && ! ${BASHCMDR_GO_LOADED+x} ]]',extra=extra))
        (self.tools/'env').unlink()
        p=self.shell('before=$PATH; if go_activate; then exit 83; fi; [[ $PATH == "$before" ]]')
        self.good(p);self.assertIn('env utility',p.stderr)

    def test_failed_partial_env_and_empty_gopath_never_become_loaded_success(self):
        for extra in [{'FAIL_QUERY':'env GOBIN'},{'FAIL_QUERY':'env GOPATH'},{'EMPTY_QUERY':'env GOPATH'}]:
            with self.subTest(extra=extra):
                self.good(self.shell('before=$PATH; if go_activate; then exit 84; fi; '
                    '[[ $PATH == "$before" && ! ${BASHCMDR_GO_LOADED+x} ]]',extra=extra))

    def test_missing_user_bin_is_not_created_and_no_op_repeats_succeed(self):
        absent=self.home/'not-created/bin'
        self.good(self.shell('go_activate; first=$PATH; go_activate; '
            '[[ $PATH == "$first" && $BASHCMDR_GO_LOADED == 1 && ! -e "$ABSENT" ]]',extra={'FAKE_GOBIN':str(absent),'ABSENT':str(absent)}))
        self.assertFalse(absent.exists())

    def test_deactivation_preserves_preexisting_go_and_user_bin_entries(self):
        self.good(self.shell('PATH="$TOOLS:$GO_BIN:$USER_BIN"; before=$PATH; '
            'go_activate; go_deactivate; [[ $PATH == "$before" ]]'))

    def test_deactivation_preserves_empty_and_glob_like_fields_and_removes_one_insertion(self):
        self.good(self.shell('PATH="$TOOLS::$HOME/[*] foreign::/missing:"; before=$PATH; '
            'go_activate; go_deactivate; [[ $PATH == "$before" ]]; '
            'PATH="$TOOLS:$GO_BIN:$GO_BIN"; BASHCMDR_GO_ADDED_PATHS=$GO_BIN; '
            'go_deactivate; [[ $PATH == "$TOOLS:$GO_BIN" ]]'))

    def test_native_windows_bin_and_gopath_forms_use_checked_conversion_fixtures(self):
        mapped=self.home/'mapped native/bin';mapped.mkdir(parents=True)
        cases=[({'FAKE_GOBIN':'C:\\user bin'},'C:\\user bin'),
               ({'FAKE_GOPATH':'C:\\first;D:\\second'},'C:\\first/bin'),
               ({'FAKE_GOPATH':'C:/first;D:/second'},'C:/first/bin'),
               ({'FAKE_GOPATH':'\\\\server\\share;D:\\second'},'\\\\server\\share/bin')]
        for extra,native in cases:
            with self.subTest(native=native):
                self.cygpath({native:mapped})
                self.good(self.shell('go_activate; [[ :$PATH: == *":$MAPPED:"* ]]',extra={**extra,'MAPPED':str(mapped)}))
        calls=[json.loads(line) for line in self.cyg_spy.read_text().splitlines()]
        self.assertEqual(calls,[['-u','--',native] for _,native in cases])

    def test_missing_failed_empty_or_relative_cygpath_output_does_not_mutate_path(self):
        native='C:\\native-bin'
        for mode in ['missing','failed','empty','relative']:
            with self.subTest(mode=mode):
                if mode!='missing':self.cygpath({},mode)
                self.good(self.shell('before=$PATH; if go_activate; then exit 85; fi; '
                    '[[ $PATH == "$before" && ! ${BASHCMDR_GO_LOADED+x} ]]',extra={'FAKE_GOBIN':native}))

    def test_go_exe_bootstrap_filename_uses_its_directory_not_the_file(self):
        self.go.rename(self.go.with_name('go.exe'))
        self.good(self.shell('go_activate; [[ :$PATH: == *":$GO_BIN:"* && $BASHCMDR_GO_LOADED == 1 ]]'))

    def test_readonly_or_incompatible_reserved_bindings_fail_without_path_changes(self):
        for setup in ['readonly PATH','BASHCMDR_GO_LOADED=1; readonly BASHCMDR_GO_LOADED',
                      'BASHCMDR_GO_ADDED_PATHS=keep; readonly BASHCMDR_GO_ADDED_PATHS',
                      'declare -a BASHCMDR_GO_LOADED=(1)']:
            with self.subTest(setup=setup):
                p=self.shell(setup+'; before=$PATH; if go_activate; then exit 86; fi; [[ $PATH == "$before" ]]')
                self.good(p);self.assertIn('writable scalar',p.stderr)
        self.assertEqual(self.queries(),[])

    def test_setup_diagnose_and_explicit_toolchain_write_have_checked_distinct_effects(self):
        self.good(self.shell('before=$PATH; go_setup; go_diagnose; [[ $PATH == "$before" ]]; '
            'if go_toolchain_use invalid; then exit 87; fi; go_toolchain_use go1.27.9'))
        writes=[q for q in self.queries() if '-w' in q['argv']]
        self.assertEqual([q['argv'] for q in writes],[['env','-w','GOTOOLCHAIN=go1.27.9+auto']])
        self.good(self.shell('_go_cmd() { return 1; }; if go_toolchain_use go1.27.9; then exit 88; fi'))

    def test_source_flags_directory_configuration_and_protected_files_survive_lifecycle(self):
        self.good(self.shell('before_flags=$-; before_ifs=$IFS; before_dir=$PWD; before_root=$(declare -p GOROOT); '
            'source "$GO_SOURCE"; go_setup; go_activate; go_diagnose; go_deactivate; '
            '[[ $- == "$before_flags" && $IFS == "$before_ifs" && $PWD == "$before_dir" '
            '&& $(declare -p GOROOT) == "$before_root" ]]'))
        self.assertTrue(self.queries());self.assertFalse(any('-w' in q['argv'] for q in self.queries()))


if __name__=='__main__':
    (EVIDENCE/'runner.json').write_text(json.dumps({'at':datetime.datetime.now().astimezone().isoformat(),
        'bash':str(BASH),'repo':str(REPO),'scope':'Owned Go/cygpath protocol fixtures, synthetic no-candidate branch, no real Go/install/network/privilege or native alternate-platform certification.'},indent=2)+'\n')
    unittest.main(verbosity=2)
