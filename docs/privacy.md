# Privacy status

Current-file cleanup was prepared on 16 November 2026. **Git history has not been anonymized.** This repository must not be described as free of personal data.

## Current files

The review covered all 50 files at the tested cleanup revision `aa92ace73802355ddc85d2a4b1e0c03f00cfb33e`: 47 text files and three unchanged, previously inspected PNG figures. Direct personal repository identifiers were found in documentation links and three provenance records. Those links have been removed; the provenance records use the project name and null hosting URLs, with an explicit redaction record.

The resulting text files were checked for the known account name, author/committer names and email addresses, personal paths and credential patterns. No such direct identifiers remain in the reviewed current-file content. This check does not establish anonymity or cover unknown identifiers.

Metrics, solve records, protocols, frozen settings, manifests and figure contents are unchanged. Scientific source-revision hashes, numeric run/job/artifact identifiers, dates and artifact digests remain for traceability. These indirect references can still lead to the original hosting metadata. The MIT license and third-party attribution are unchanged.

## Remaining exposure

Existing commits retain personal author/committer metadata, including a non-private email address. Earlier file versions retain the original repository URLs. Normal commits made through the available connector also use the connected account's identity.

The repository owner, GitHub activity and Actions actor/log metadata remain identifiable. Hosted artifacts, caches, forks, deleted or otherwise unreviewed refs and unreachable objects have not been removed or certified clean. The review of historical file content covered 12 reachable main-line commits through the archive revision; it was not a review of every possible GitHub object.

## Required follow-up

The available connector can create commits and update refs with an expected-head check, but its commit-writing tools expose no author or committer fields. Its general fetch tool is read-only. No history rewrite was attempted with those limitations.

Completing this request requires an authorized GitHub client that can explicitly set both commit identities and perform guarded ref updates. It must inspect the relevant refs, reconstruct their commits with sanitized historical files and identities while preserving the intended scientific record, and update refs only if their expected heads still match. Preserve applicable branch protections and concurrent changes; do not publish a backup ref that keeps the personal history reachable.

Any revised provenance needs a truthful mapping to the sanitized evidence. A ref rewrite alone does not remove Actions records, artifacts, cached commit pages, forks or unreachable objects. Those need a separate hosting review and supported cleanup; cached objects may require GitHub Support.

Changing future email-privacy settings or transferring repository ownership does not remove existing commit metadata. See the [transfer checklist](transfer.md) and [validation record](validation.md).
