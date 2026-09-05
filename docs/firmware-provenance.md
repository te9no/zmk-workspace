# Firmware build provenance

Local `just.sh build` and the reusable firmware workflow now export a JSON
sidecar next to each UF2/BIN. It records source and dependency commits, dirty
input fingerprints, the target, and SHA-256 hashes of the binary, generated
`.config`, and generated `zephyr.dts`.

Inputs are sampled before and after building. A changed input aborts export.
The pre-build record is outside the target build tree: local builds use
`<build-root>/.provenance/<artifact>.json`, and CI uses the job's `RUNNER_TEMP`.
This keeps `west build -p always` from deleting the record before verification.
Dirty builds are identified, not presented as reproducible clean commits.
Metadata contains no diff contents or absolute source paths. It is provenance,
not a cryptographic attestation or hardware-test result.

CI publication rejects intervening source changes on the target branch.
Generated firmware/keymap/badge commits may advance the branch. A normal
non-force push still protects against a concurrent update after that check.
Incoming CI binaries require matching provenance sidecars; legacy installed
binaries without sidecars remain supported. Sidecars and binaries are installed
together using the existing rollback-safe directory replacement.

Validation: `python3 -m unittest discover -s tests -q` and
`./just --unstable --fmt --check`. Hardware validation remains separate.

## Current audit checkout

Cornix's active verification source is `work/cornix-madula-studio-keys`, branch
`feature/madula-right-encoder-scroll`; the `madula-lpps-validation` build profile
was used. Older canonical/work checkouts must not be assumed current based on
their directory names. Use explicit `ZMK_CONFIG_ROOT` and inspect `git status`
before building. Historical dirty checkouts and build caches were not deleted
as part of this audit.
