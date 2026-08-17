Create a new GitHub release of this Ansible Collection following the steps in order:

- Find out the next tag number to use:

```sh
git tag | sort -V | tail -1
```

- Unless otherwise stated, use the next minor version. For example:

Current: v0.5.3
Next: v0.5.4

- Create a new branch using the format `release/{tag}`
- Update the version on @galaxy.yml to match the git tag version
- Update `version:` in @ci/execution-environment/requirements.yml to the git tag
  itself, including the leading `v` (`galaxy.yml` carries the bare version,
  this file carries the tag). The Execution Environment build fails the tag if
  the two do not agree.
- Commit the changes
- Push the changes
- Create the git tag
- Push the git tag to origin
- Create a PR to merge this branch to `main`
