# INSTRUCTION_FACTS — ss007-pep752-implicit-namespaces

Grouped values for the instruction author. Each line is one value, not prose.

## Deliverable shape

CPython standard library feature implementing PEP 752
New package importable as packagenamespaces
Package lives at Lib/packagenamespaces/
packagenamespaces.normalize
packagenamespaces.matching
packagenamespaces.grants
packagenamespaces.uploads
packagenamespaces.metadata
packagenamespaces.policy
packagenamespaces.cli
Entry point: python -m packagenamespaces
the package root re-exports every public symbol
GrantStore, RepositoryIndex and SecurityPolicy import from the package root

## Naming (normalize)

normalize_name
is_valid_namespace
hyphen_depth
runs of - _ . fold to one -
lowercased
Foo.bar_BAZ becomes foo-bar-baz
valid: ASCII letter or digit at both ends
invalid: empty, leading/trailing separators, spaces, punctuation
non-string input: normalize_name raises TypeError, is_valid_namespace is False
names holding newlines, tabs or other control characters are invalid
TypeError
ValueError
hyphen_depth counts hyphens after normalization

## Matching (matching)

namespace_matches
exact match or starts with the namespace followed by a hyphen
foo matches foo-bar, not foobar
both inputs normalized before comparison

## Grants (grants)

Grant
GrantStore
GrantError
InvalidNamespaceError
OverlapError
DepthLimitError
UnknownGrantError
grants_overlap
DEFAULT_DEPTH_LIMIT = 3
GrantStore.reserve
GrantStore.transfer
GrantStore.remove
GrantStore.get
GrantStore.namespaces
GrantStore.matching
GrantStore.parent
GrantStore.children
GrantStore.depth_limit
Grant.name
Grant.owner
get returns None when ungranted
parent returns None without a grant
len of a store counts its active grants
a namespace string is in a store when its normalized form holds a grant
parent returns the granted parent name as a string
children returns the granted child names as a sorted list of strings
reserve stores the normalized name
reserve rejects invalid names with InvalidNamespaceError
reserve rejects empty owners
reserve enforces the hyphen depth limit with DepthLimitError
depth_limit None means unlimited
overlap appends a hyphen to both normalized names
overlap is detected in both directions
a longer namespace under an existing grant overlaps
foo and foobar do not overlap
overlap allowed only for the overlapping grant's own owner
same owner may nest grants
exact duplicate for another owner is rejected
unknown namespace raises UnknownGrantError on transfer and remove
transfer that would overlap another owner's grant raises OverlapError
namespaces returns sorted names
matching returns sorted grants
parent is the granted direct parent or None
children are granted direct children, sorted
a missing middle grant breaks the parent and children links

## Uploads (uploads)

authorize_upload
GrandfatheredRegistry
UploadConflictError
CONFLICT_STATUS = 409
409 Conflict
status_code
UploadConflictError carries project, namespace, owner
UploadConflictError.owner is the uploader that attempted the upload
the conflict reports the owner argument, not the grant holder
authorize_upload returns True when allowed
authorize_upload rejects empty or non-string owners with ValueError
owner validation runs before any grant is consulted
stranger upload under a reserved prefix raises UploadConflictError
owner upload under own grant is allowed
unreserved project upload is allowed
grandfathered project upload by a stranger is allowed
GrandfatheredRegistry.add
GrandfatheredRegistry.discard
GrandfatheredRegistry.covers
GrandfatheredRegistry.projects
len of a registry counts its exempt projects
a project string is in a registry when its normalized form is exempt
UploadConflictError.status_code
UploadConflictError.project
UploadConflictError.namespace
UploadConflictError.owner
True
False
normalization runs before the upload check

## Repository metadata (metadata)

RepositoryIndex
API_VERSION is the string "1.5"
LEGACY_API_VERSION is the string "1.4"
1.5
1.4
NotSupportedError
RepositoryIndex.register_project
RepositoryIndex.project_owner
RepositoryIndex.projects
RepositoryIndex.project_detail
RepositoryIndex.list_namespaces
RepositoryIndex.namespace_detail
RepositoryIndex.simple_html
RepositoryIndex.store
RepositoryIndex.supports_namespaces
RepositoryIndex.grandfathered
RepositoryIndex.api_version
project_owner returns None when unknown
register_project records ownership without authorizing uploads
a stranger-owned project under a reserved prefix still registers
project_detail returns name and namespaces keys
{"name": "<project>", "namespaces": null}
{"name": "<project>", "namespaces": [{"name": "<namespace>", "owned": true}]}
{"name": "<namespace>", "owned": false}
{"name": "<namespace>"}
{"name": "<namespace>", "parent": "<parent>", "children": ["<child>"], "owner": "<owner>"}
"parent": null
{"api_version": "1.5", "namespaces": [{"name": "<namespace>"}]}
{"filename": "<file>", "url": "<url>"}
owned is true when the project owner holds the grant
owned is false for grandfathered projects
matches sorted by name in project_detail
grant removal sets project_detail namespaces to null
/namespaces
/namespace/<namespace>
list_namespaces returns name mappings, sorted
list_namespaces returns a bare sorted list of name mappings
namespace_detail returns name, parent, children, owner
namespace_detail normalizes its input
namespace_detail raises UnknownGrantError when ungranted
parent is null without a grant
children lists direct children only
legacy repositories omit the namespaces key
legacy repositories report version 1.4
legacy list and detail raise NotSupportedError
supporting repositories report version 1.5
simple_html takes project and files with filename and url
simple_html renders a full HTML document with doctype
simple_html title and heading name the project
simple_html renders one anchor per file in order with href and filename
HTML Simple API is unchanged
simple_html output contains no namespace metadata
simple_html escapes special characters

## Installer policy (policy)

SecurityPolicy
SecurityPolicy.allows
SecurityPolicy.evaluate
SecurityPolicy.namespaces
SecurityPolicy.owner
SecurityPolicy takes namespaces and owner
allows takes project and index
evaluate takes requirements and index
evaluate returns normalized-name to boolean mapping
project owner must equal the policy owner
matching policy namespace must hold an active grant for that owner
unknown projects denied
ungranted namespaces denied
grandfathered foreign projects denied
grants are per-repository
a grant on one index confers nothing on another
invalid policy namespaces raise InvalidNamespaceError
empty policy owner raises ValueError

## CLI (cli)

main
main(argv)
main takes argv and returns an exit status
reserve <namespace> --owner <owner>
list
list --json
show <namespace>
show <namespace> --json
remove <namespace>
register <project> --owner <owner>
grandfather <project> --owner <owner>
check-upload <project> --owner <owner>
dump
dump --project <project>
--store
--owner
--json
--project
--help
{"grants": {"<namespace>": "<owner>"}, "projects": {"<project>": "<owner>"}, "grandfathered": ["<project>"]}
the CLI persists exactly the documented store schema
a hand-written documented store loads back
grandfather records the project owner and exempts the project
[{"name": "<namespace>", "owner": "<owner>"}]
list --json prints name and owner entries
bare dump prints the versioned namespace envelope
the versioned api_version envelope belongs to bare dump only
dump entries carry names only, from list_namespaces
dump --project prints one project detail mapping
reserved <namespace> for <owner>
removed <namespace>
registered <project> for <owner>
grandfathered <project>
OK <project>
list prints <namespace> <owner> per line, sorted
show line name: <name>
show line owner: <owner>
show line parent: <parent>
show line children: <children>
name: <name>
owner: <owner>
parent: <parent>
children: <children>
parent: none
children: none
show unknown exits 1
unknown grant
reserve overlap exits 1
overlaps the grant
check-upload allowed exits 0
check-upload denied exits 3 with 409 Conflict
CONFLICT_EXIT = 3
exit status 3
corrupt store exits 1
empty owner exits 1
check-upload with an empty owner exits 1 even for unreserved projects
corrupt store message contains error
empty owner message contains error
non-string owners or entries in a store exit 1

## Shell harness (Tools)

Tools/packagenamespaces/gen_fixtures.sh
Tools/packagenamespaces/verify_offline.sh
gen_fixtures takes an output directory
gen_fixtures writes grants.json
gen_fixtures writes projects.json
gen_fixtures writes grandfathered.json
gen_fixtures writes second-index.json
verify_offline takes a fixture directory
verify_offline exits 0 on success
verify_offline exits nonzero when fixtures are missing
verify_offline exits nonzero when fixtures are damaged
verify_offline validates every fixture shape before checking
a malformed second index fails verification
grants.json holds {"grants": [{"name": "<name>", "owner": "<owner>"}]}
grants.json lists at least two name and owner entries
projects.json holds {"projects": {"<project>": "<owner>"}}
grandfathered.json holds {"grandfathered": ["<project>"]}
second-index.json holds {"grants": [], "projects": {"<project>": "<owner>"}}
verify: all checks passed
no network use in either script

## Docs

Doc/library/packagenamespaces.rst
Doc/library/distribution.rst lists the new page
Doc/whatsnew/3.16.rst
Misc/NEWS.d/next/Library/
NEWS entry mentions packagenamespaces and 752
whatsnew entry mentions packagenamespaces and 752
library page mentions PEP 752
library page names PEP 752 in prose or through the :pep: role
library page documents SecurityPolicy
library page documents RepositoryIndex

## Build integration

Makefile.pre.in LIBSUBDIRS lists packagenamespaces
Python/stdlib_module_names.h lists packagenamespaces
normal make install ships the new package
sys.stdlib_module_names contains packagenamespaces
