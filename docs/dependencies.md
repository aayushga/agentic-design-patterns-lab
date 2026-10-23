# Dependency policy and platform notes

The lab keeps local-only patterns free of an OpenAI dependency. Each standalone
pattern includes the shared `requirements-test.txt`; optional SDK requirements
include their pattern's requirements so the same security constraints apply even
when installed independently. The root `requirements.txt` installs the full local
lab, including MCP/A2A. `requirements-dev.txt` adds pinned verification tools.

```bash
python -m pip install --upgrade 'pip>=26.2,<27'
python -m pip install --upgrade --only-binary=:all: -r requirements.txt
# Optional model SDK, still no API call during installation:
python -m pip install --upgrade --only-binary=:all: -r patterns/01-prompt-chaining/openai_version/requirements.txt
```

`constraints.txt` sets minimum patched versions and compatible major ranges without
installing otherwise unused packages. It is **not a lockfile**. Actual production
applications should resolve and hash-pin their selected dependencies separately for
each supported Python/platform combination, then audit and rebuild those locks.
OpenAI is limited to the tested 2.x API line; upgrading to 3.x needs an explicit
migration and contract validation. This does not change the selected Astra model.

## Review findings (2026-10-22)

A scan of the existing development environment found advisory records across six
packages, including installer/test tooling. Duplicate advisory aliases were present;
these are not six proven exploits in the application. Reviewed patch floors are:

| Package | Previously installed | Constraint / installer floor |
| --- | --- | --- |
| anyio | 4.13.0 | ≥4.14.2, <5 |
| certifi | 2026.2.25 | ≥2026.10.19 |
| cryptography | 48.0.1 | ≥50.0.2, <51 |
| pytest | 9.0.2 | ≥9.0.3, <10 |
| Pygments | 2.19.2 | ≥2.20.0, <3 |
| pip | 26.0.1 | Upgrade installer to ≥26.2, <27 |

Relevant upstream advisories include [AnyIO TLS hostname handling](https://github.com/agronholm/anyio/security/advisories/GHSA-82r6-8w77-94w6),
[certifi trust-store removal](https://github.com/certifi/python-certifi/security/advisories/GHSA-6q48-6c7w-9gw2),
and [cryptography PKCS#7 decryption](https://github.com/pyca/cryptography/security/advisories/GHSA-g6cj-pr64-35w5).
The full dependency audit checks current public metadata rather than freezing an
allowlist of these advisories. No vulnerability is ignored or marked resolved
merely because a teaching example does not exercise the affected feature.

## Intel macOS limitation

The review ran on an x86_64 macOS Python 3.12 runtime. PyPI publishes cryptography
50.0.2 wheels for Linux, Windows, and macOS ARM, but no compatible Intel macOS
wheel. A binary-only full-lab install on that platform therefore stops instead of
silently accepting the older vulnerable dependency. This applies to protocol SDK
transitive dependencies, not standard-library-only examples.

Use a supported wheel platform (the Linux GitHub Actions jobs validate the complete
resolution), or build the patched cryptography source with its supported Rust/native
toolchain before installing the other requirements. Follow the upstream
[cryptography installation guide](https://cryptography.io/en/latest/installation/).
A source build is a deliberate local setup step; this review does not install a
compiler, change system Python, or weaken the security floor. Existing virtual
environments need rebuilding/upgrading; changing this file does not patch them.

The isolated local compatibility run upgraded the other affected packages and
passed the suite with OpenAI 2.54.0. Its Intel-specific cryptography limitation
remained visible to the scanner. The mandatory Linux dependency-audit job validates
the fully patched resolution and fails on known vulnerabilities or missing audit
metadata. A green scan is a dated observation, not a guarantee against future issues.
