#!/usr/bin/env bash
set -euo pipefail
root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
mkdir -p "$tmp/go/bin" "$tmp/gopath/bin" "$tmp/tools"
# Do not let a host Go in /usr/bin change this owned bootstrap fixture.
ln -s "$BASH" "$tmp/tools/bash"
ln -s "$(command -v rm)" "$tmp/tools/rm"
ln -s "$(command -v env)" "$tmp/tools/env"
cat > "$tmp/go/bin/go" <<'EOF'
#!/usr/bin/env bash
case "${1-}" in
version) echo 'go version go1.27.0 linux/arm64' ;;
env) case "${2-}" in GOBIN) echo ;; GOPATH) echo "$TEST_GOPATH" ;; GOTOOLCHAIN) echo auto ;; *) exit 1;; esac ;;
*) exit 1 ;;
esac
EOF
chmod +x "$tmp/go/bin/go"
export GOROOT="$tmp/go" TEST_GOPATH="$tmp/gopath" PATH="$tmp/tools"
source "$root/main.bashcmdr"
go_activate
case ":$PATH:" in *":$tmp/go/bin:"*) ;; *) exit 1;; esac
case ":$PATH:" in *":$tmp/gopath/bin:"*) ;; *) exit 1;; esac
before=$PATH
go_activate
[[ $PATH == "$before" ]]
go_deactivate
case ":$PATH:" in *":$tmp/go/bin:"*|*":$tmp/gopath/bin:"*) exit 1;; esac
echo 'go-loader tests passed'
