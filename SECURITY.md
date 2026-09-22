# Security policy

## Scope

This policy covers the Shepherd repository, including:

- `install.sh` and the Python installer;
- the project helpers in `scripts/`;
- workflow instructions and starter files shipped in this repository.

Herdr, terminal multiplexers, agent harnesses, and model providers are separate
systems. Report Shepherd-specific handling or integration problems here; report
vulnerabilities in those systems to their respective maintainers.

## Reporting a vulnerability

Please use GitHub's **private vulnerability reporting** feature for this
repository. Do not open a public issue or pull request with an unpatched
vulnerability or working exploit.

Include, where possible:

- the affected commit, release, or installed pack version;
- the affected file and command or installation path;
- clear reproduction steps and expected versus actual behavior;
- the security impact and any practical mitigation;
- logs or proof of concept reduced to the minimum needed to demonstrate the issue.

Remove credentials, personal data, and unrelated project content before sending
logs. If private vulnerability reporting is unavailable, open a brief public
issue asking for a private contact method without including vulnerability details.

We will acknowledge a report when we can, investigate it, and coordinate a fix
or mitigation with the reporter. Please allow time for a fix before public
disclosure.

## Supported versions

The `main` branch is the actively maintained version. Security fixes may also be
backported to a tagged release when the issue affects that release and the fix is
low risk to backport.

## Installation safety

Review the target project and the installation plan before using `--accept` or
`--force`. Shepherd does not download agent harnesses, sign in, or launch agents
during installation. Keep local credentials and environment files outside the
pack source tree and never commit them.
