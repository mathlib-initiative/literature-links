# The `$id` namespace

The schema's `$id` is
`https://w3id.org/formal-companion/annotations/v<major>.<minor>/schema.json`.
It is an identifier: no checker fetches it. It is a w3id.org permanent
identifier so that it does not depend on where the repository is hosted or
what it is called.

The namespace is registered with [w3id.org](https://w3id.org/) by
[perma-id/w3id.org#6782](https://github.com/perma-id/w3id.org/pull/6782),
which adds `ids/formal-companion/` to that repository. `.htaccess` here is a
copy of the redirect rules it adds:

| identifier | redirects to (302) |
|---|---|
| `https://w3id.org/formal-companion/annotations/v<major>.<minor>/schema.json` | `schema/annotations-v<major>.<minor>.schema.json` on this repository's `main` branch |
| `https://w3id.org/formal-companion/annotations` | this repository |
| `https://w3id.org/formal-companion` | this repository |

Until that pull request is merged the identifier does not resolve, which
changes nothing for validation. To change a redirect, change `.htaccess`
here, then open a pull request that makes the same change to
`ids/formal-companion/` there.

Each format minor gets its own `$id` and its own schema file in `schema/`;
released schema files never change, so the redirect can point at the `main`
branch.
