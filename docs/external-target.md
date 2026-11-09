# Independent HTTP/file target

## What is independent

The test uses the already installed nginx executable, with its original code unchanged. The executed environment reported nginx 1.26.3. A generated private configuration enables DAV PUT for two disposable files and a random health token. Executable hashes, version/configuration output, server configuration and process exit status accompany each run.

The gateway, fault hooks, scenario generator, requirements and checker are Deadline Lab code. No upstream nginx bug is alleged. The experiment demonstrates the workbench against independently authored request processing and externally observed state, not an independently discovered QNX application defect.

The nginx executable is not copied into the deliverable. A fresh environment needs its own installation with `--with-http_dav_module`.

## Reproduced failures

The expiry case holds an old request, lets its client reach a real socket timeout, performs a newer request, then releases the old one. The timeout-only gateway forwards the old request anyway. nginx writes its value to the file. The checker rejects an observed effect dispatched after its authorisation expiry.

The ordering case releases an older request while its authorisation is still valid, after a newer request has already changed the file. An expiry check alone admits it. The added sequence fence rejects that stale request at the one serial gateway.

A third control completes a write but suppresses its acknowledgement. The client times out even though the file changed. This is an unknown outcome until observation, not evidence of rollback. The reference gateway does not claim to undo the completed write.

## Observation assumptions

The runner reads bytes from the target directory before and after each controlled operation. nginx creates the effects, not the checker. The required snapshots include a byte hash, decoded value and local monotonic observation timestamp. Request provenance is checked against the scenario; release observations must retain the exact identity of the original held request.

Values in a scenario are deliberately distinct, making each file transition observable. This adapter cannot count invisible repeated writes of identical values and does not claim at-most-once physical actuation. It has a single writer and serial admission. There is no cross-host clock or consensus claim.

The deadline property concerns the instant a gateway dispatches a request. Backend completion can occur later. A physical deadline would need a boundary with a different observation and control contract.

## Repeatability and reduction

The campaign uses two authored scenario families with seeded parameter variations. It is not coverage-guided fuzzing. Different seeds do not make them independent applications. Explicit release hooks control the major interleaving, while operating-system timing still varies.

The reducer is shared with the C-fixture and native-source adapters. It rejects grammatically invalid candidates and never treats INCONCLUSIVE as a reproduced failure. Accepted reductions require two successful reproductions. The final witnesses are replayed five times per compared policy and audited for one-action deletion minimality. No global shortest-sequence guarantee is made. Final evidence bundles are retained; intermediate reduction runs use temporary directories.

## Isolation

Only IPv4 loopback is used. All listening ports are ephemeral. The runner verifies a random startup token before mutation, handles port-startup failures as errors, and owns the single foreground nginx process. It never uses `nginx -s`, edits `/etc/nginx`, signals an unrelated PID, accepts a scenario-specified executable or targets an external host.

An explicit `--nginx` argument is a trusted operator-provided local executable path, not data controlled by a scenario. Do not point this laboratory at production services or expose its hook endpoint publicly.

A clean target exit, a complete observation history and all required files are prerequisites for a conclusive result. Checksums detect accidental changes; an attacker who can rewrite the full bundle can rewrite its hashes too.

## Primary references

- nginx DAV module, documented PUT/file operations: https://nginx.org/en/docs/http/ngx_http_dav_module.html
- nginx command-line configuration and prefix isolation: https://nginx.org/en/docs/switches.html
- nginx developer-mode process configuration: https://nginx.org/en/docs/ngx_core_module.html

These sources describe software interfaces. The results themselves come from this package's recorded local executions.
