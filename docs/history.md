# History

*Informative.* This page records where the code came from. Nothing here is a
rule of the format.

## Origin

The format was written in September 2026 inside another repository of the
same organisation, as the interchange format between that repository's
tools. On 2026-09-28 it was extracted into this repository with
`git filter-repo`, keeping every commit, author and date that touched the
format's files (the schema, the specification, the examples, the checker,
the id rules and their tests). The commits before `576553d` in this
repository's history are those commits, with their original messages; the
paths they mention are the paths they had before the extraction.

## The withdrawn 1.0.0

The extraction was tagged `v1.0.0` on 2026-09-28. An adversarial review the
next day found that the format had no reader other than its checker, that
its vocabulary had already fallen behind its one producer, that its id rules
could not be reimplemented from the text, and a set of checker defects. The
tag is withdrawn: do not use it. It is deleted from the repository and its
remote when the release candidate is published. The format was reworked as
the `1.0.0rc1` release candidate; `CHANGELOG.md` lists every change. The old
identifier,
`lean-companion/annotations`, is not accepted by any release from the
candidate on.

## Design rules that survived

Five rules from the first design still hold:

1. everything that varies is an abstraction: a location is a W3C Web
   Annotation target with a selector, whatever the medium;
2. an unnumbered passage is a first-class item, and any number of items may
   share a page;
3. the document is highly structured: every root key is a fixed header or an
   array of records with string ids, every array is sorted, every object is
   closed;
4. sources are pinned: a location is only meaningful against one edition;
5. plain JSON on disk, JSON-LD on export.

The rework added a sixth: the core stays small, and everything a reader can
live without is a profile it may ignore.
