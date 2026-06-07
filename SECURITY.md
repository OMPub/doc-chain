# Security Policy

Security feedback is welcome. Doc Chain is intended to be reusable public
infrastructure, and careful review of its contract, reference tooling, and
protocol documentation helps make every project built on it safer.

This policy describes responsible disclosure for Doc Chain. It is not currently
a formal bug bounty, and the project does not promise rewards or fixed response
times.

## Supported Targets

Security reports are most useful when they affect:

- the current `main` branch
- `contracts/src/DocChain.sol`
- the EIP-712 signing and submission flow
- the ABI, event model, and reusable reference tooling
- deployment metadata and release procedures
- protocol or security documentation whose ambiguity could cause an unsafe
  implementation

Please identify the exact commit, network, and contract address involved in a
deployment report. Historical commits and unlisted deployments are reviewed on
a best-effort basis.

Profile-specific behavior usually belongs to the project defining that profile.
For example, canonicalization, source validation, attester eligibility, and
branch scoring for the RSO Archive should normally be reported to the RSO
Archive project. Report it here when the issue is in Doc Chain's reusable code
or protocol boundary.

## Reporting A Vulnerability

Do not open a public issue containing vulnerability details, exploit code,
private keys, credentials, or sensitive data.

Use GitHub's private vulnerability reporting from the repository's Security tab
when it is available. If it is unavailable, open a minimal
[GitHub issue](https://github.com/OMPub/doc-chain/issues/new) asking the
maintainers to contact you privately. Include only enough information to
identify the affected component and the best way to reach you.

Once a private channel is established, please include:

- the affected component, commit, deployment, or contract address
- the security impact and who could be affected
- clear reproduction steps or a minimal proof of concept
- any preconditions required for exploitation
- suggested mitigations, if known
- your preferred disclosure timeline and attribution

The maintainers will acknowledge reports, investigate them in good faith, and
coordinate a reasonable disclosure timeline with the reporter. Timing depends
on severity, complexity, and whether deployed contracts or downstream projects
are affected.

## Research Guidelines

Please:

- use local environments, forks, or testnets whenever possible
- stop after establishing the minimum evidence needed to demonstrate impact
- avoid accessing, changing, or retaining data that is not yours
- avoid disrupting users, deployments, or third-party services
- give maintainers a reasonable opportunity to investigate and mitigate an
  issue before public disclosure

Do not use social engineering, phishing, credential theft, privacy violations,
denial of service, destructive testing, or attacks against third-party
infrastructure.

## Intended Behavior And Scope Boundaries

The following are important design boundaries, but are not vulnerabilities by
themselves:

- attestations are permissionless, and the contract does not reserve
  `docChainId` values
- the contract does not fetch or validate the bytes referenced by a URI
- the contract does not choose a canonical branch, define eligible attesters,
  or sponsor gas
- profile-specific validation and consensus happen outside the contract
- EIP-1271 authorization is evaluated when an attestation is submitted
- distinct signed claims may coexist, including competing or conflicting claims

Reports showing a concrete security impact across one of these boundaries are
still welcome. Generic best-practice suggestions, third-party service outages,
and testnet-only activity without a plausible impact may be closed as
informational.

See [docs/threat-model.md](docs/threat-model.md) for the full contract boundary
and known non-goals.

## Good-Faith Research

The project will not initiate legal action against researchers for good-faith
security research that follows this policy. This statement applies only to
systems controlled by the Doc Chain project; it cannot authorize testing of
third-party systems or override applicable law.

There is no formal reward program at this time. With the reporter's permission,
the project may publicly credit useful disclosures after remediation.
