# Repository transfer notes

Use this checklist when moving the repository to the intended account. The destination has not been selected.

Internal documentation and image links are relative. Package metadata has no account-specific repository URL. CI uses no repository secrets, has read-only contents permission and runs on `main`. Tests, package checks and both smoke entry points run on normal source changes; the 34-run corrected study and 84-run matrix are explicit manual choices.

1. Complete the pending [history and hosting privacy work](privacy.md) before claiming the repository is anonymized. Ownership transfer does not rewrite commit authors or remove earlier file versions.
2. Confirm Actions is enabled in the destination and review workflow permissions, artifact retention and required status checks. If the default branch is renamed, update the `main` push filter in [CI](../.github/workflows/ci.yml).
3. Run the workflow with `study: tests` to verify the new repository context.
4. Update external CV/profile links. Replace `MAIN_REPOSITORY_URL` in the [LinkedIn draft](linkedin-draft.md) before posting and obtain a public image link from its relative image reference.
5. Review the source revisions and run/artifact identifiers retained in the archives. Do not invent replacement identifiers or mechanically substitute an unknown owner. Record any later evidence migration or history mapping accurately. Artifact downloads expire; checked-in data and selected figures remain available.
6. Check repository visibility, the About description and topics in GitHub settings. The connector used for this cleanup does not expose those edits.

Suggested About description: “Synthetic single-zone HVAC benchmark comparing thermostat, day-ahead scheduling and MPC with hard comfort constraints, audited simulation results and reproducible tests.”

The [MIT license](../LICENSE) credits the project contributors. Keep third-party notices in [ACKNOWLEDGMENTS.md](../ACKNOWLEDGMENTS.md). No badge or package repository URL currently needs an owner substitution. No transfer, destination repository creation or deletion has been performed.
