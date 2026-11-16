# Go Loader Cartridge

Use an existing Go bootstrap from Bash Commander and manage its current-shell PATH entries. Ordinary setup, activation and diagnosis do not install Go, write shell profiles or change a project's Go files. An explicit optional toolchain-selection action writes Go's own saved setting, as described below.

**Prerelease policy:** Bash Commander is an official OAS FOSS project
preparing its first public prerelease. Support will cover only exact configurations
and flows that pass final release acceptance. The current native baseline is Linux
Mint 22.3/x86_64/Bash 5.2.21, with a private historical Bash 4.3 compatibility
case; other platforms remain unverified portability targets. This is a Bash-centric
core without a global Linux or `sudo` requirement. A language-feature threshold
does not certify a platform or every upstream runtime version. Final release
acceptance and public availability are still pending.

The examples require matching Console/cartridge revisions made available for
review or publication; a default-branch checkout may not contain these changes.
See the matching Console's [prerelease support policy](https://github.com/bashcmdr/console/blob/main/docs/SUPPORT.md)
for the exact evidence boundaries, working flows and unavailable features.


## Requirements

- The selected [Bash Commander console](https://github.com/bashcmdr/console) and Bash 4.3+. Git and `jq` are needed for the console installation flow; runtime probes use ordinary tools including `env`, `dirname`, `cat`, `readlink`, `mkdir`, `ln` and `rm`.
- An existing external Go executable for active integration. Install Go separately using its upstream instructions; this cartridge is not an installer and needs no other cartridge or sudo.
- Existing writable user-bin directories when they are to be added to PATH. The cartridge does not create a missing user-bin directory or build/install a sample program.

Upstream Go/runtime support is separate from Bash Commander portability. Native drive/UNC paths need `cygpath` only when conversion to Bash paths is required; ordinary POSIX paths do not need it. Linux host Bash and a private Bash4.3 build do not certify Git Bash, OpenWrt, Termux or other native platforms.

## Install and enable

Use canonical `bashcmdr`; `bcm` is an optional shortcut when it resolves to that installation. Clone into a new destination; use an existing console's selected root instead of overwriting it. An explicit Git source needs no registry index.

```bash
git clone https://github.com/bashcmdr/console.git "$HOME/.local/bin/bashcmdr"
export BASHCMDR_ROOT_DIR="$HOME/.local/bin/bashcmdr"
export PATH="$BASHCMDR_ROOT_DIR/bin:$PATH"
bashcmdr version
bashcmdr cartridge install go-loader --from https://github.com/bashcmdr/cartridge-go.git
bashcmdr cartridge plug go-loader
bashcmdr cartridge list active
```

External `plug` records persistent activation and runs in that command's process; it cannot export PATH changes into its parent shell. To initialize the marked-active cartridge in your current shell, start a fresh Bash process and initialize that console there:

```bash
export BASHCMDR_ROOT_DIR="$HOME/.local/bin/bashcmdr"
export PATH="$BASHCMDR_ROOT_DIR/bin:$PATH"
source "$BASHCMDR_ROOT_DIR/boot/shell-init.bashcmdr"
printf 'Bash Commander boot status: %s\n' "$BASHCMDR_BOOT_EXIT_CODE"
command -v go
go version
```

Boot status must be `0` before continuing. Sourcing the initializer is nonfatal, so its return status alone does not establish successful boot. Missing Go may leave activation dormant even after successful boot; `BASHCMDR_GO_LOADED=1` indicates successful cartridge activation. An executable `go` already on PATH does not prove that the current shell was initialized. Initialization runs once per shell; use a fresh shell after correcting startup or changing installations. Make persistent profile changes yourself after checking this flow.

Sourcing `main.bashcmdr`, even with an action argument, defines functions without dispatching. To invoke a defined helper directly, call it explicitly; direct helper calls do not change the console's persistent activation state. Executing the script runs an action in a child process and cannot change the parent shell's PATH.

## Inspect the installed bootstrap

```bash
go version
go env GOBIN GOPATH
command -v go
```

These user-invoked Go commands follow Go's normal toolchain/configuration rules. The cartridge's own ordinary probes instead force process-local `GOTOOLCHAIN=local`; that prevents those probes from asking Go to download an automatic toolchain. It does not turn arbitrary later Go commands into offline operations or validate every upstream setting.

## Configured root

If no external Go is on PATH, an existing configured bootstrap can be selected before fresh initialization. Use your actual absolute Bash path instead of the example:

```bash
export GOROOT="$HOME/custom go bootstrap"
```

An external Go already on PATH takes precedence. Nonempty caller GOROOT/GOPATH/GOBIN values are retained; the runtime discovery/ownership rules below explain fallback and native-path conversion.

## Diagnose and get help

```bash
bashcmdr help cartridge
go_help
bashcmdr cartridge diagnose go-loader
go_diagnose
bashcmdr console log --lines 50
```

Diagnostics identify the bootstrap and the shell's GOTOOLCHAIN value. They do not enumerate every persisted upstream setting; absent Go is reported as dormant success, while invalid configuration or failed required queries fail. Use the selected console log command and review logs before sharing them.

In a bare cartridge checkout:

```bash
bash main.bashcmdr help
bash main.bashcmdr setup
bash main.bashcmdr diagnose
```

The available actions are `setup`, `activate`, `deactivate`, `diagnose`, `help` and `toolchain-use`. Bare inspection needs no console libraries; sourcing with an action still does not dispatch it.

## Optional persistent toolchain selection

This is an explicit change to Go's saved configuration. Choose `GO_TOOLCHAIN_TO_USE` yourself as an exact numeric `goMAJOR.MINOR.PATCH` selector before running it; the helper rejects missing patch numbers, release-candidate syntax and arbitrary strings. The variable is only for this example, not a cartridge setting.

```bash
go_toolchain_use "${GO_TOOLCHAIN_TO_USE:?Set GO_TOOLCHAIN_TO_USE to an exact numeric Go selector}"
```

The helper requests `go env -w GOTOOLCHAIN=<selector>+auto` through the existing bootstrap rather than implementing an installer. That Go process and later Go commands follow [Go's toolchain rules](https://go.dev/doc/toolchain#go-toolchain-selection) and may select or download toolchains. A GOTOOLCHAIN environment value can override the saved default. Cartridge deactivation does not undo this setting.

To remove the saved setting:

```bash
go env -u GOTOOLCHAIN
```

Removal does not restore an earlier custom value. Record that value beforehand and restore it through Go's own interface if needed. The installed bootstrap must support the requested Go setting; failures propagate. See [Go environment settings](https://pkg.go.dev/cmd/go#hdr-Print_Go_environment_information) for persistence and precedence.

## Deactivate

```bash
bashcmdr cartridge unplug go-loader
go_deactivate
```

The external command changes persistent activation for future startup; the helper removes owned PATH insertions from the initialized current shell. Preexisting/unrelated PATH fields and caller root/workspace settings remain. Defined helpers and the Go installation remain; this cleanup does not reset saved Go configuration or reverse arbitrary caller edits.

## Runtime discovery and ownership

`go-loader` configures an existing external Go bootstrap in the current Bash
shell. The external `go` already found on PATH has precedence. If there is none,
the cartridge tries the configured `GOROOT/bin/go` or `go.exe`, then the optional
legacy `/usr/local/go/bin/go` location when no GOROOT was configured. An invalid
configured root fails visibly. No Linux installation directory or sudo is
required.

Activation rechecks the bootstrap and effective user-bin configuration on every
call. An inherited exported `BASHCMDR_GO_LOADED=1` does not bypass repair after a
child resets PATH. Existing directories are added only when absent; a missing
user-bin directory is not created. Re-sourcing/repeating activation preserves
the current shell's ownership tracking. Deactivation removes one occurrence
for each owned insertion and retains preexisting/unrelated PATH fields. This
is not a full rollback of arbitrary later caller edits.

The user-bin path comes from `go env GOBIN`, or the first `go env GOPATH` element
plus `/bin` when GOBIN is empty. Caller GOROOT/GOPATH/GOBIN settings are retained.
Go's Unix colon-separated and native Windows semicolon-separated GOPATH forms
are handled. Native Windows drive/UNC paths require an available `cygpath -u`
conversion to Bash paths; that utility is not required for ordinary POSIX paths.
An unavailable or failed required conversion returns failure before PATH is
changed. These data-format controls do not certify native Windows execution.

Ordinary setup/activation/diagnostic probes use the portable `env` utility with
process-local `GOTOOLCHAIN=local`, so they inspect the bundled bootstrap without
requesting automatic toolchain downloads or changing even readonly caller
configuration. Failed, empty required or partial failed probe output cannot
publish loaded success. PATH and ownership/marker bindings must be writable
scalar variables. Diagnostics identify the selected bootstrap and the shell's
GOTOOLCHAIN value; they do not claim to read every persisted Go setting.

The cartridge never modifies `.profile`, `.bash_profile`, `.bashrc`, other startup files, `/usr/local/go`, `go.mod`, or `go.work`.

`go_toolchain_use go1.N.P` is the explicit operation that writes Go's native
`GOTOOLCHAIN=go1.N.P+auto` default; use `go env -u GOTOOLCHAIN` to undo it.
An existing GOTOOLCHAIN environment value can take precedence over Go's saved
default. Normal activation does not invoke `go env -w`. Go itself retains
responsibility for its own caches, configuration and explicit toolchain actions.

## Development checks

```bash
bash tests/main.bash
python3 tests/test_runtime_context.py
python3 tests/test_docs.py --console-root /absolute/path/to/bashcmdr-console
bash -n main.bashcmdr
```

The regression suites use owned temporary homes, inert Go/cygpath interfaces and constrained local Git. The optional saved-setting example writes only the fake Go configuration in these fixtures; no real Go, toolchain download, installer, privileged/service operation or live installation change runs. These controls are separate from hosted CI and native-platform/support acceptance.

The shared development payload runs those checks and records tool identities,
individual exit statuses, full stdout/stderr and owned runtime/guide records:

```bash
bash --noprofile --norc tests/ci.bash /absolute/path/to/bashcmdr-console
```

The workflow proposal uses Ubuntu24.04 and the Python3.14 series as a development
baseline, with exact action commit references and a fixed Console compatibility
input. It checks for Bash4.3+, Git and jq instead of installing distro packages
or assuming sudo. Diagnostic artifacts are retained even after a failed check.
The action implementations use Node24 and require a compatible Actions runner
(at least2.327.1); the hosted Ubuntu runner is proposed here, not a self-hosted
runner requirement for using this cartridge. See the official
[checkout](https://github.com/actions/checkout),
[setup-python](https://github.com/actions/setup-python) and
[artifact](https://github.com/actions/upload-artifact) documentation.

This private proposal has not run on GitHub. Its pinned Console commit must be
available to the workflow before hosted execution can succeed. The separately
selected release platform matrix, actual hosted results and release acceptance
remain pending. An Ubuntu development runner does not limit the Bash-centric
runtime contract or certify Windows, Termux, OpenWrt or other native systems.

## Project links and licensing

- [Bash Commander console](https://github.com/bashcmdr/console)
- [This cartridge](https://github.com/bashcmdr/cartridge-go)
- [Go command environment documentation](https://pkg.go.dev/cmd/go#hdr-GOPATH_environment_variable)
- [cygpath conversion interface](https://www.cygwin.com/cygwin-ug-net/cygpath.html)

Copyright 2026 Eric Milgram. Original project code is licensed under [Apache-2.0](LICENSE); see [NOTICE](NOTICE). Bash Commander is an official OAS FOSS project.

Upstream Go licensing is separate. Local tests do not establish production readiness or a release promise.

## Manifest metadata

The `lifecycle` entries name Bash functions defined by sourcing `main.bashcmdr`;
use them in the shell context described above. They are not executable file paths
or commands evaluated by the Console from this metadata. `testing.test_script`
names the development entrypoint `tests/ci.bash`, which takes the compatible
Console checkout argument shown above. Tests are not run automatically when this
cartridge is sourced or activated. External dependency entries are discovery
hints; the runtime selection rules above determine the tools actually used.
Console dependency and loaded-state checks are separate from these descriptive
lifecycle/testing entries.
