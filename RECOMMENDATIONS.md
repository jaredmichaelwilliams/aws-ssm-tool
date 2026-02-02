# AWS SSM Tool - Optimization & Feature Recommendations

This document contains analysis and recommendations for improving the aws-ssm-tool project.

**Last Updated:** After merging master branch

## Table of Contents
- [Summary of Changes from Master](#summary-of-changes-from-master)
- [Optimization Opportunities](#optimization-opportunities)
- [New Feature Recommendations](#new-feature-recommendations)
- [Code Quality Issues](#code-quality-issues)
- [Implementation Priority](#implementation-priority)

---

## Summary of Changes from Master

The following improvements were found after merging master:

### Addressed Issues
| Issue | Status | Notes |
|-------|--------|-------|
| Eager client initialization | **Partially Fixed** | Reduced from 12 clients to 3 (ssm, iam, sts) in `environment.py:111-120` |
| Tree output | **Implemented** | Added `--format tree` option using `rich` library |
| Test coverage | **Improved** | New integration tests in `tests/integration/test.sh` |
| Documentation | **Improved** | New API docs, CLI docs, Docker usage |

### New Features Added
- `stat` command - Shows account/caller context and parameter metadata
- `list-dirs` / `ls-dirs` command - Lists directories only
- `--flat-output` flag - Flattens nested paths in output
- `--dirs-only` flag - Filters to directories
- `--caller-context` flag - Shows caller identity info
- Docker support with multi-arch builds
- `rich` library integration for pretty output

---

## Optimization Opportunities

### 1. Update Outdated Dependencies (Critical)

**Location:** `setup.cfg:44-52`

**Current State:**
```
boto==2.49.0        # Deprecated library (2019)
boto3==1.17.97      # Released June 2021
botocore==1.20.97   # Released June 2021
rich==13.3.4        # Released March 2023
```

**Issues:**
- `boto` (classic) is deprecated and should be removed entirely
- boto3/botocore are ~5 years behind, missing security patches and features
- The `get_boto()` method in `environment.py:96-109` uses legacy boto only for Route53
- `coloredlogs` is listed as dependency but appears unused (replaced by `rich`)

**Recommended Fix:**
```
# Remove boto and coloredlogs entirely
boto3>=1.34.0
botocore>=1.34.0
rich>=13.7.0
```

---

### 2. Fix Hardcoded DEBUG Log Level (High)

**Location:** `src/ssm/util/__init__.py:124-125`

**Current State:**
```python
# FIXME: get this from some kind of global config
logger.setLevel("DEBUG")
```

**Issues:**
- Always outputs debug information regardless of user intent
- No way to control verbosity
- The `--debug` flag exists in CLI but doesn't affect log level

**Recommended Fix:**
```python
import os

def get_logger(name, console=CONSOLE, fake=False):
    # ...
    log_level = os.environ.get('SSM_LOG_LEVEL', 'WARNING')
    logger.setLevel(log_level)
    return logger
```

Also wire up the `--debug` flag in `wrapper.py` to set log level.

---

### 3. Defer Profile Loading at Import Time (Medium)

**Location:** `src/ssm/api/environment.py:171-184`

**Current State:**
```python
# Executed at module import time
Environment.ENV_CONFIGS = collections.OrderedDict()
Environment.ALL_PROFS = session.Session().available_profiles
LOGGER.info(tmp.format(len(Environment.ALL_PROFS)))
for profile_name in Environment.ALL_PROFS:
    Environment.ENV_CONFIGS[profile_name] = dict(...)
LOGGER.info("loading metadata from envs")
for env_name, env_config in Environment.ENV_CONFIGS.copy().items():
    LOGGER.info(f"\t- {env_name}")
    # ...
```

**Issues:**
- Slows down import/startup for every command
- Logs profile loading even for `--help`
- May fail if any profile is misconfigured

**Recommended Fix:**
```python
@classmethod
def _ensure_profiles_loaded(cls):
    if hasattr(cls, '_profiles_loaded'):
        return
    cls.ALL_PROFS = session.Session().available_profiles
    # ... rest of loading logic
    cls._profiles_loaded = True

@classmethod
def from_profile(cls, name):
    cls._ensure_profiles_loaded()
    # ... existing logic
```

---

### 4. SecretManager Created on Every Access (Medium)

**Location:** `src/ssm/api/environment.py:162-168`

**Current State:**
```python
@property
def secrets(self):
    """returns a secrets manager for this session"""
    return SecretManager(env=self)
```

**Issue:** Creates a new SecretManager instance on every access.

**Recommended Fix:**
```python
@functools.cached_property
def secrets(self):
    """returns a secrets manager for this session"""
    return SecretManager(env=self)
```

---

### 5. Inefficient `keys()` Method (Low)

**Location:** `src/ssm/api/manager.py:108-121`

**Current State:**
```python
def keys(self, under=None):
    paginator = self.env.ssm.get_paginator("describe_parameters")
    pager = paginator.paginate(...)
    return self._unpack_pager(pager).keys()
```

**Issue:** `_unpack_pager` expects `Parameters` with `Name` and `Value` keys, but `describe_parameters` returns metadata without values. This may cause KeyError or return unexpected results.

**Recommended Fix:**
```python
def keys(self, under=None):
    paginator = self.env.ssm.get_paginator("describe_parameters")
    pager = paginator.paginate(...)
    out = []
    for page in pager:
        out.extend(p["Name"] for p in page["Parameters"])
    return out
```

---

### 6. Add Retry Configuration (Low)

**Missing:** boto3 retry/backoff configuration for resilience.

**Recommended Addition in `environment.py`:**
```python
from botocore.config import Config

BOTO_CONFIG = Config(
    retries={
        'max_attempts': 3,
        'mode': 'adaptive'
    },
    connect_timeout=5,
    read_timeout=30
)

def init_session(self):
    self.session = boto3.session.Session(...)
    self.ssm = self.session.client("ssm", config=BOTO_CONFIG)
    # ...
```

---

### 7. Remove Unused Dependencies (Low)

**Location:** `setup.cfg:48`

**Current State:**
```
coloredlogs
termcolor
```

**Issue:**
- `coloredlogs` is imported nowhere in the codebase (replaced by `rich.logging.RichHandler`)
- `termcolor` is still used in `util/__init__.py` but `rich` can handle all coloring

**Recommended:** Remove `coloredlogs`, consider removing `termcolor`.

---

## New Feature Recommendations

### 1. Implement `put_many` (Critical - Currently Broken)

**Location:** `src/ssm/api/__init__.py:238-242`

**Current State:**
```python
def put_many(secret_name, input_file=None, **kwargs):
    """put many secrets"""
    raise NotImplementedError()
```

**Recommended Implementation:**
```python
import yaml
import json

def put_many(namespace, input_file=None, format="yaml", **kwargs):
    """Put multiple secrets from a file to a namespace"""
    assert input_file, "input_file is required"

    with open(input_file) as f:
        if format in ["yaml", "yml"]:
            data = yaml.safe_load(f)
        elif format == "json":
            data = json.load(f)
        else:
            raise ValueError(f"Unsupported format: {format}")

    secrets = _get_client(**kwargs)
    results = []
    for key, value in data.items():
        full_path = f"{namespace.rstrip('/')}/{key}"
        secrets[full_path] = str(value)
        results.append(full_path)
        LOGGER.info(f"Created: {full_path}")

    return results
```

---

### 2. Implement `delete_path` (High - Currently Broken)

**Location:** `src/ssm/api/__init__.py:233-235`

**Current State:**
```python
def delete_path(path_prefix, **kwargs):
    raise NotImplementedError()
```

**Recommended Implementation:**
```python
def delete_path(path_prefix, no_backup=False, dry_run=False, **kwargs):
    """Delete all parameters under a path prefix"""
    secrets = _get_client(**kwargs)
    keys = list(secrets.under(path_prefix).keys())

    if dry_run:
        LOGGER.info(f"Would delete {len(keys)} parameters:")
        for k in keys:
            LOGGER.info(f"  - {k}")
        return keys

    results = []
    for key in keys:
        result = delete(key, no_backup=no_backup, **kwargs)
        results.append(result)

    return results
```

---

### 3. Add `copy_many` Command (High)

Bulk copy operation to complement `move_many`:

```python
def copy_many(
    src_name,
    dst_name,
    src_profile: str = "default",
    dst_profile: str = "default",
    **kwargs,
):
    """Copy all parameters from one path to another"""
    dst_name = dst_name.rstrip('/')
    src_man = _get_client(profile=src_profile)
    dst_man = _get_client(profile=dst_profile)

    params = src_man.under(src_name)
    results = []

    for name, value in params.items():
        new_name = f"{dst_name}{name[len(src_name.rstrip('/')):]}"
        dst_man[new_name] = value
        results.append((name, new_name))
        LOGGER.info(f"Copied: {name} -> {new_name}")

    return results
```

**CLI Usage:**
```bash
ssm copy-many /prod/config /staging/config --src-profile prod --dst-profile staging
```

---

### 4. Add `diff` Command (High)

Compare parameters between environments or paths:

```bash
ssm diff /prod/config /staging/config --src-profile prod --dst-profile staging
```

**Output Example:**
```
< /prod/config/api_key: a]k3...   (only in source)
> /staging/config/new_setting: val  (only in destination)
! /prod/config/debug: true vs false  (different values)
= /prod/config/timeout: 30  (identical - 5 parameters)
```

---

### 5. Add `--dry-run` Flag (High)

For destructive operations (`delete`, `delete-path`, `move`, `move-many`):

```bash
ssm delete /prod/secrets --dry-run
ssm move-many /old /new --dry-run
ssm delete-path /test --dry-run
```

---

### 6. Add `search` / `find` Command (High)

Search parameters by name pattern:

```bash
ssm search "database*" --profile prod
ssm find --contains "password" --profile prod
ssm search "/prod/*/api_key" --profile prod
```

**Implementation using fnmatch:**
```python
import fnmatch

def search(pattern, **kwargs):
    """Search parameters by name pattern (supports wildcards)"""
    secrets = _get_client(**kwargs)
    all_keys = secrets.keys()
    return [k for k in all_keys if fnmatch.fnmatch(k, pattern)]
```

---

### 7. Add Parameter History Support (Medium)

AWS SSM supports parameter versioning:

```bash
ssm history /prod/secret --profile prod
ssm read /prod/secret --version 3
ssm rollback /prod/secret --to-version 2
```

**API:**
```python
def history(secret_name, **kwargs):
    """Get version history for a parameter"""
    env = _get_env(**kwargs)
    paginator = env.ssm.get_paginator('get_parameter_history')
    pages = paginator.paginate(Name=secret_name, WithDecryption=True)
    return [p for page in pages for p in page['Parameters']]
```

---

### 8. Add Parameter Type Selection (Medium)

Currently hardcodes `SecureString` in `manager.py:54`:

```python
Type="SecureString",
```

**Recommended:** Add `--type` option:
```bash
ssm update /config/value value --type String
ssm update /config/list "a,b,c" --type StringList
ssm update /prod/secret value --type SecureString  # default
```

---

### 9. Add Tagging Support (Medium)

```bash
ssm update /prod/secret value --tag env=prod --tag team=backend
ssm list --tag env=prod
ssm tag /prod/secret --add team=frontend --remove deprecated
ssm tags /prod/secret  # show tags
```

**Implementation:**
```python
def add_tags(secret_name, tags: dict, **kwargs):
    """Add tags to a parameter"""
    env = _get_env(**kwargs)
    env.ssm.add_tags_to_resource(
        ResourceType='Parameter',
        ResourceId=secret_name,
        Tags=[{'Key': k, 'Value': v} for k, v in tags.items()]
    )
```

---

### 10. Add stdin Support (Medium)

```bash
cat secret.txt | ssm update /prod/secret --stdin
echo "value" | ssm update /prod/secret -
generate-secret | ssm update /prod/api-key --stdin
```

**Implementation in `update`:**
```python
import sys

def update(secret_name, value, file=None, stdin=False, **kwargs):
    if stdin or value == '-':
        value = sys.stdin.read().strip()
    elif file:
        value = open(file).read()
    # ...
```

---

### 11. Add Shell Completion (Medium)

Click has built-in support. Add to README:

```bash
# Bash
eval "$(_SSM_COMPLETE=bash_source ssm)"

# Zsh
eval "$(_SSM_COMPLETE=zsh_source ssm)"

# Fish
_SSM_COMPLETE=fish_source ssm | source
```

Or generate completion scripts:
```bash
_SSM_COMPLETE=bash_source ssm > ~/.ssm-complete.bash
echo "source ~/.ssm-complete.bash" >> ~/.bashrc
```

---

### 12. Add `--quiet` / `-q` Flag (Low)

Suppress non-essential output:

```bash
ssm update /prod/secret value -q  # No output on success
ssm delete /prod/secret -q        # No output on success
```

---

### 13. Add Confirmation for Destructive Operations (Low)

```bash
ssm delete-path /prod
# WARNING: This will delete 47 parameters under /prod
# Type 'yes' to confirm:

ssm delete-path /prod --yes  # Skip confirmation
ssm delete-path /prod --force  # Alias for --yes
```

---

### 14. Wire Up `--debug` Flag (Low)

**Location:** `src/ssm/cli/wrapper.py:21-29`

The `--debug` flag is defined but doesn't actually enable debug logging.

**Fix in `proxy` function:**
```python
def proxy(*args, **kwargs):
    if kwargs.pop('debug', False):
        logging.getLogger().setLevel('DEBUG')
    # ... rest of function
```

---

## Code Quality Issues

### 1. Import Statement in Wrong Location

**Location:** `src/ssm/api/__init__.py:79`

```python
def list_dirs(path_prefix, **kwargs) -> typing.List:
    ...

import typing  # <-- Should be at top of file

def list(path_prefix, dirs_only: bool = False, **kwargs) -> typing.List:
```

**Fix:** Move `import typing` to top of file with other imports.

---

### 2. Missing `__all__` Exports

Most modules lack `__all__` definitions, making the public API unclear.

**Recommended:** Add to each module, e.g., in `api/__init__.py`:
```python
__all__ = [
    'read', 'update', 'delete', 'list', 'list_dirs',
    'copy', 'move', 'copy_many', 'move_many',
    'get_many', 'put_many', 'stat', 'delete_path',
]
```

---

### 3. Type Hints Incomplete

Many functions lack type hints. Consider adding throughout:

```python
def read(secret_name: str, **kwargs) -> str:
    """reads a secret"""

def list(path_prefix: str, dirs_only: bool = False, **kwargs) -> list[str]:
    """Lists parameters with prefixes below the given path."""
```

---

### 4. Unused `cascade` Option

The `cascade` option is defined in `cli/options.py:43-51` and used in `get_many` command, but the API function `get_many` doesn't use a `cascade` parameter:

```python
# In bin/ssm.py:143
cli.options.cascade,  # Passed to command

# In api/__init__.py:107 - no cascade parameter used
def get_many(namespace, flat_output: bool = False, **kwargs):
```

**Fix:** Either implement cascading logic or remove unused option.

---

## Implementation Priority

### Phase 1 - Critical Fixes
1. ✅ Update dependencies (remove boto, update boto3/botocore, remove coloredlogs)
2. ✅ Implement `put_many` (currently broken)
3. ✅ Implement `delete_path` (currently broken)
4. ✅ Fix import statement location in `api/__init__.py`

### Phase 2 - High Priority Features
5. Add `copy_many` command
6. Add `diff` command
7. Add `--dry-run` flag
8. Add `search`/`find` command
9. Fix hardcoded DEBUG log level

### Phase 3 - Performance
10. Defer profile loading to first use
11. Cache SecretManager with `@cached_property`
12. Fix `keys()` method implementation
13. Add boto3 retry configuration
14. Wire up `--debug` flag

### Phase 4 - Enhanced Features
15. Add parameter history support
16. Add parameter type selection
17. Add tagging support
18. Add stdin support

### Phase 5 - Polish
19. Add shell completion docs
20. Add `--quiet` flag
21. Add confirmation for destructive ops
22. Add `__all__` exports
23. Complete type hints
24. Remove unused `cascade` option or implement it

---

## Notes

**Strengths of Current Codebase:**
- Well-structured with clear separation of concerns
- The CLI wrapper pattern (`ApiWrapper`) is elegant and reduces boilerplate
- The dictionary protocol implementation for SecretManager is Pythonic
- Good use of `rich` library for output formatting
- Solid integration test coverage in shell scripts
- Docker support is well implemented

**Testing Improvements Needed:**
- Add unit tests with mocked boto3 clients (using `moto` library)
- Add pytest fixtures for common test scenarios
- Test error handling paths
- Add tests for CLI argument parsing edge cases
