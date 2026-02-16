# Known Issues

**Last Updated**: 2026-02-13

## Active Issues

| ID | Issue | Impact | Workaround | Blocked By |
|----|-------|--------|------------|------------|
| 1 | No auth on `/update_server_config` | Config can be changed by any network client | Restrict by network ACL until auth added | Security decision |
| 2 | Source lists can grow unbounded | Long-running server may accumulate inactive sources | Restart service periodically | Add TTL cleanup |

## Resolved Issues

| ID | Issue | Resolution | Date |
|----|-------|------------|------|
| 1 | Most sport parsers were stubs | Implemented full parsers from legacy app | 2026-02-13 |

## Notes

- Sport codes `sft` and `bsb` are 3 characters but parser checks `data[0]` (single char) - may need fix
