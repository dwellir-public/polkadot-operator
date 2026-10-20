# Development, testing, deployment, and releases

Run the commands below from the repository root. Development requires Python
and `uv`; building requires Charmcraft. Deployment and integration testing also
require Juju and access to a suitable controller. The integration workflow uses
LXD.

## Development

Create feature or fix branches from `main` and open pull requests targeting
`main`.

Run the local checks before requesting review:

```bash
make charm-venv
make charm-test
```

`make charm-test` applies formatting fixes, then runs lint and unit tests.
Review any formatting changes before committing.

The Charm Tests workflow runs formatting, lint, and unit tests for pull requests
and pushes to `main`. It also packs the charm for both supported platforms and
runs Actionlint against the GitHub workflows. Dependabot checks action versions
weekly and groups updates into reviewable pull requests.

## Integration testing

Run the Charm Integration Tests workflow manually in GitHub Actions, or use a
temporary model on an existing controller:

```bash
make integration-test-clean CONTROLLER=<controller>
```

This target creates a model, runs the integration tests, and destroys the model
and its storage on exit. It defaults to building for Ubuntu 24.04 amd64; override
`INTEGRATION_PLATFORM` to select another supported platform.

The current integration test checks that the charm builds. Validate deployment,
configuration, actions, and relations separately when those behaviors change.

## Build

Build for the platform used by the target machines:

```bash
make build-charm CHARMCRAFT_ARGS='--platform ubuntu@24.04:amd64'
```

The resulting artifact is `polkadot_ubuntu@24.04-amd64.charm`. Ubuntu 22.04 amd64
is also supported; substitute `22.04` in the platform and artifact name.

## Deploy or refresh

Replace the placeholders with the target model, application name, client binary
URL, and service arguments for the intended chain and node role.

Deploy a new application using the built artifact:

```bash
juju deploy ./polkadot_ubuntu@24.04-amd64.charm <application> \
  --model <model> --base ubuntu@24.04 \
  --config binary-url=<binary-url> --config service-args='<service-args>'
```

To update an existing application with the built artifact:

```bash
juju refresh <application> --model <model> \
  --path ./polkadot_ubuntu@24.04-amd64.charm
```

Wait for hooks to complete, then inspect the application and its units:

```bash
juju status --model <model> --relations
juju show-unit --model <model> <application>/0
juju debug-log --model <model> --include <application>/0 --replay
```

Confirm that the workload is running with the intended configuration and that
its RPC and metrics endpoints respond as expected. For changes to relations,
check the published relation data and verify that related applications remain
healthy. For observability changes, also confirm that the monitoring consumer
receives metrics and logs with the expected topology labels.

## Manual release

Merging into `main` does not publish a charm or create a GitHub release.
Release jobs only run from `main` in this repository. A concurrency group allows
one release run at a time without cancelling an active release. Avoid queuing
multiple releases: GitHub may replace an older pending run with a newer one.

1. Merge the changes to release into `main` and confirm that Charm Tests passes.
2. Complete integration verification for the intended changes.
3. In GitHub Actions, select **Release Charm to Charmhub and GitHub**.
4. Select **Run workflow**, choose `main`, and start the workflow.
5. Confirm that both Charmhub uploads and the GitHub release succeed.

The release workflow runs formatting, lint, and unit tests, then builds separate
amd64 charms on Ubuntu 22.04 and 24.04. It generates SHA256 checksums alongside
the artifacts and verifies both before uploading either to Charmhub. The upload
job uses the `edge` GitHub environment and publishes to the channel defined by
`RELEASE_CHANNEL` in the workflow (currently `latest/edge`).

The workflow then verifies the artifacts again and creates a GitHub release
tagged `latest-edge-r<rev22>-r<rev24>`, attaching both charm files and their
checksums and recording their Charmhub revisions and source commit.

### Release environment setup

Configure the `edge` environment in the repository's GitHub settings. Store
`CHARMHUB_TOKEN` as an environment secret, restrict deployment branches to
`main`, and configure required reviewers if release approval is needed.

If the token is currently a repository secret, an administrator must supply its
value again as the environment secret before removing the repository secret.
GitHub does not allow reading back existing secret values. A repository secret
with the same name remains available as a fallback until it is removed; adding
an environment to the workflow alone does not change the secret's scope.

Publishing to other Charmhub channels is outside this workflow. Avoid starting
overlapping release runs. If a run fails after an upload, inspect the completed
steps and Charmhub revisions before retrying: an upload may already have
published a revision even when the overall workflow fails.
