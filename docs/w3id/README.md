# The `$id` namespace

The schema's `$id` is
`https://w3id.org/formal-companion/annotations/v<major>.<minor>/schema.json`.
It is an identifier: no checker fetches it. It is a w3id.org permanent
identifier so that it does not depend on where the repository is hosted or
what it is called.

This directory holds the files that register the namespace with
[w3id.org](https://w3id.org/): copy `.htaccess` and this `README.md` into a
`formal-companion/` directory of a fork of
[perma-id/w3id.org](https://github.com/perma-id/w3id.org) and open a pull
request there. Until that pull request is merged the identifier does not
resolve, which changes nothing for validation.

Each format minor gets its own `$id` and its own schema file in `schema/`;
released schema files never change, so the redirect can point at the `main`
branch.
