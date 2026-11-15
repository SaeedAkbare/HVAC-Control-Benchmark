# Repository transfer notes

The repository is ready for a later owner transfer; no destination is assumed and no transfer is performed by this cleanup.

Internal documentation and image links are relative. Package metadata has no account-specific repository URL. CI uses no repository secrets, has read-only contents permission and runs on `main`. Tests, package checks and both smoke entry points run on normal source changes; the 34-run corrected study and 84-run matrix are explicit manual choices.

After transfer:

1. Confirm Actions is enabled and review workflow permissions, artifact retention and any required status checks. If the default branch is renamed, update the `main` push filter in [CI](../.github/workflows/ci.yml).
2. Run the workflow with `study: tests` to verify the new repository context.
3. Update the repository URL in any external CV or profile. Replace `MAIN_REPOSITORY_URL` in the [LinkedIn draft](linkedin-draft.md) before posting; obtain a new public image link from its relative image reference.
4. Check the historical commit, run and artifact links in the result archives. They deliberately identify the original evidence; do not mechanically substitute an unknown owner. Artifact downloads expire, while the checked-in data and selected figures remain available.
5. Review Git author name/email metadata and the account's email-privacy settings. Ownership transfer does not rewrite existing commit authors.

The existing [MIT license](../LICENSE) credits the project contributors, so it does not require guessing a legal name or changing the copyright holder on transfer. Keep third-party notices in [ACKNOWLEDGMENTS.md](../ACKNOWLEDGMENTS.md). No badge or package repository URL currently needs an owner substitution.
