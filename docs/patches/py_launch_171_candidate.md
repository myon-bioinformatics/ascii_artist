# Pending launcher rollout for PR #53

The production vendor lock remains at parent main `6f068b340310fe7e342ea89a53cafacd33ca63cc`.
Parent PR #171 (`834e626906ddce34e97d37f0fec2509719f673cf`) is not merged.
Follow its rollout boundary: accept parent main, propagate through Aoi's merged
source lineage, then regenerate vendor bytes and lock using the accepted source.
Do not update only the checked-in vendor file or merge #53 before that rollout.

`py_launch_171_candidate.patch` reproduces the complete launcher change from that
parent candidate against the current vendored bytes (probe isolation plus repeated
signal forwarding). It is for temporary validation, not a lock update.

Validate a temporary copy without changing the checked-in vendor:

```sh
repo="$PWD"
work=$(mktemp -d)
mkdir -p "$work/vendor"
cp vendor/py_launch.cjs "$work/vendor/py_launch.cjs"
(cd "$work" && git apply "$repo/docs/patches/py_launch_171_candidate.patch")
ASCII_SIGNAL_LAUNCHER="$work/vendor/py_launch.cjs" python -m pytest -q docs/patches/signal_candidate_check.py
```

Alternatively apply the patch in a disposable checkout. The regression uses actual
Node/Python processes and readiness/acknowledgement handshakes, sends SIGINT then
SIGTERM to Node only, checks exit 2 and text/JSON ESIGNAL diagnostics, and kills
the process group in cleanup. POSIX only. After the accepted rollout, move this
regression into tests and use the locked launcher path directly.

Validation on Linux, Node 24.19.0, Python 3.12: current launcher fails both cases
with a bounded timeout; the parent candidate passes both cases.
