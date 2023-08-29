# Release Strategy

## Quality gates

| [Risk level] | Edge | Beta | Candidate | Stable |
|--|----|----|-----|-----|
| Meaning | Bleeding edge, new features currently in development | Most new features have been stabilized | Feature-ready, currently in testing | Well-tested, production-ready |
| Branch | main | main | main | main |
| Preconditions (quality gates) | Code review, CI | | Deploy, charm-upgrade | |
| Timing | Every merge to the main branch. | | Charm reaches a state of feature completion with respect to the next planned stable release. | In consultation with product manager and engineering manager when the candidate revision has been well tested and is deemed ready for production. |
| Release process  | Automatic (on merge to main) | Manual | Manual | Manual |

## Publishing

```shell
charmcraft pack
charmcraft upload <charm>.charm
charmcraft release <charm> --channel=edge --revision=<RevNumber>
```

## Testing

WRITE ME

* Define a set of test to be performed as part of the release-process.

## Promoting a charm from edge to beta/candidate/stable

WRITE ME

How it is actually done.

[Risk level]: https://snapcraft.io/docs/channels#heading--risk-levels
