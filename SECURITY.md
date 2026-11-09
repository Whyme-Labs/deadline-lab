# Laboratory execution only

This project is not a safety-certified controller, security boundary or production fault injector. It must not control physical machinery. Its tests only operate self-launched fixtures and synthetic state.

Scenario files cannot select external PIDs or run shell commands. Fault budgets, counts and durations are bounded. Local processes are reaped, and output directories cannot silently overwrite existing runs. Resume validates completed run artifacts before using them. Hashes detect accidental corruption, not a malicious actor that can rewrite artifacts.

The QNX canary requires a configured lab target. It does not change target permissions, install a driver, request hardware access or redistribute licensed software. Missing prerequisites produce NOT_RUN or a setup error.

Do not upload private SDK files, target images, credentials, confidential project data or proprietary recordings in a public submission.
