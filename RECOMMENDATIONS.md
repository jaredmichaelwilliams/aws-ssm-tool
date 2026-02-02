# AWS SSM Tool - Optimization & Feature Recommendations

This document contains analysis and recommendations for improving the aws-ssm-tool project.

## Table of Contents
- [Optimization Opportunities](#optimization-opportunities)
- [New Feature Recommendations](#new-feature-recommendations)
- [Implementation Priority](#implementation-priority)

---

## Optimization Opportunities

### 1. Update Outdated Dependencies (Critical)

**Location:** `setup.cfg:44-51`

**Current State:**
```
boto==2.49.0        # Deprecated library
boto3==1.17.97      # Released June 2021
botocore==1.20.97   # Released June 2021
```

**Issues:**
- `boto` (classic) is deprecated and should be removed
- boto3/botocore are ~5 years behind, missing security patches and features
- The `get_boto()` method in `environment.py:82-95` uses legacy boto which is only needed for very old Route53 operations

**Recommended Fix:**
```
# Remove boto entirely
boto3>=1.34.0
botocore>=1.34.0
```

---

### 2. Implement Lazy Client Initialization (High)

**Location:** `src/ssm/api/environment.py:97-117`

**Current State:**
```python
def init_session(self):
    self.s3 = self.session.client("s3")
    self.ec2 = self.session.client("ec2")
    self.emr = self.session.client("emr")
    self.ssm = self.session.client("ssm")
    self.iam = self.session.client("iam")
    self.sts = self.session.client("sts")
    self.cloudwatch = self.session.client("cloudwatch")
    self.route53 = self.session.client("route53")
    self.support = boto3.session.Session(...).client("support")
    self.redshift = self.session.client("redshift")
    self.cloudformation = self.session.client("cloudformation")
```

**Issues:**
- Creates 12 AWS clients on instantiation even though only SSM is used
- Each client creation involves network calls and adds latency
- Wastes memory for unused clients

**Recommended Fix:**
```python
import functools

class Environment:
    @functools.cached_property
    def ssm(self):
        return self.session.client("ssm")

    @functools.cached_property
    def s3(self):
        return self.session.client("s3")

    # ... etc for other clients
```

---

### 3. Enable Memoization for Environment Handles (Medium)

**Location:** `src/ssm/api/__init__.py:18-24`

**Current State:**
```python
# @util.memoized  # <-- Commented out
def _get_handle(env=None, **kwargs):
    env = Environment.from_profile(env) if util.is_string(env) else env
    return env.secrets
```

**Issues:**
- Each API call creates a new Environment instance
- Redundant session creation for repeated operations

**Recommended Fix:**
Implement a proper caching mechanism:
```python
from functools import lru_cache

@lru_cache(maxsize=16)
def _get_handle(env=None):
    env = Environment.from_profile(env) if util.is_string(env) else env
    return env.secrets
```

---

### 4. Fix Hardcoded Debug Log Level (Medium)

**Location:** `src/ssm/util/__init__.py:60`

**Current State:**
```python
# FIXME: get this from some kind of global config
logger.setLevel("DEBUG")
```

**Issues:**
- Always outputs debug information
- No way to control verbosity

**Recommended Fix:**
```python
import os

def get_logger(name):
    log_level = os.environ.get('SSM_LOG_LEVEL', 'WARNING')
    logger.setLevel(log_level)
    return logger
```

---

### 5. Defer Profile Loading (Low)

**Location:** `src/ssm/api/environment.py:170-183`

**Current State:**
```python
# Executed at module import time
Environment.ALL_PROFS = session.Session().available_profiles
for profile_name in Environment.ALL_PROFS:
    Environment.ENV_CONFIGS[profile_name] = dict(...)
```

**Issues:**
- Slows down import/startup
- May fail if any profile is misconfigured
- Loads profiles that may never be used

**Recommended Fix:**
Load profiles lazily on first access.

---

### 6. Optimize `keys()` Method (Low)

**Location:** `src/ssm/api/manager.py:82-95`

**Current State:**
Uses `describe_parameters` with full pagination, then extracts only keys.

**Recommended Fix:**
Use `describe_parameters` more efficiently and only return names.

---

### 7. Add Retry Configuration (Low)

**Missing:** boto3 retry/backoff configuration

**Recommended Addition:**
```python
from botocore.config import Config

config = Config(
    retries={
        'max_attempts': 3,
        'mode': 'adaptive'
    },
    connect_timeout=5,
    read_timeout=30
)
self.ssm = self.session.client("ssm", config=config)
```

---

## New Feature Recommendations

### 1. Implement `put_many` (Critical - Currently Broken)

**Location:** `src/ssm/api/__init__.py:142-144`

**Current State:**
```python
def put_many(secret_name, input_file=None, **kwargs):
    raise NotImplementedError()
```

**Recommended Implementation:**
```python
def put_many(namespace, input_file=None, format="yaml", **kwargs):
    """Put multiple secrets from a file"""
    assert input_file, "input_file is required"

    with open(input_file) as f:
        if format in ["yaml", "yml"]:
            data = yaml.safe_load(f)
        elif format == "json":
            data = json.load(f)
        else:
            raise ValueError(f"Unsupported format: {format}")

    secrets = _get_handle(**kwargs)
    results = []
    for key, value in data.items():
        full_path = f"{namespace}/{key}" if not key.startswith('/') else key
        secrets[full_path] = value
        results.append(full_path)

    return results
```

---

### 2. Add `copy_many` Command (High)

Bulk copy operation to complement `move_many`:
```bash
ssm copy-many /prod/config /staging/config --src-env prod --dest-env staging
```

---

### 3. Add `diff` Command (High)

Compare parameters between environments:
```bash
ssm diff /prod/config /staging/config --src-env prod --dest-env staging
```

**Output:**
```
- /prod/config/api_key: *** (different values)
+ /staging/config/new_setting: (only in staging)
- /prod/config/old_setting: (only in prod)
= /prod/config/shared: (identical)
```

---

### 4. Add `search` Command (High)

Search parameters by name pattern:
```bash
ssm search "database*" --env prod
ssm search --contains "password" --env prod
```

---

### 5. Add `--dry-run` Flag (High)

For destructive operations:
```bash
ssm delete /prod/secrets/* --dry-run
ssm move-many /old /new --dry-run
```

---

### 6. Add Parameter History Support (Medium)

SSM supports versioning:
```bash
ssm history /prod/secret --env prod
ssm read /prod/secret --version 3
ssm rollback /prod/secret --version 2
```

---

### 7. Add Parameter Type Selection (Medium)

Currently hardcodes `SecureString`:
```bash
ssm update /config/value --type String
ssm update /config/list --type StringList "a,b,c"
```

---

### 8. Add Tagging Support (Medium)

```bash
ssm update /prod/secret value --tag env=prod --tag team=backend
ssm list --tag env=prod
ssm tag /prod/secret --add team=frontend
```

---

### 9. Add stdin Support (Medium)

```bash
cat secret.txt | ssm update /prod/secret --stdin
echo "value" | ssm update /prod/secret -
generate-secret | ssm update /prod/api-key --stdin
```

---

### 10. Add Shell Completion (Medium)

Click has built-in support:
```bash
# Bash
eval "$(_SSM_COMPLETE=bash_source ssm)"

# Zsh
eval "$(_SSM_COMPLETE=zsh_source ssm)"

# Fish
_SSM_COMPLETE=fish_source ssm | source
```

---

### 11. Add `export` / `import` Commands (Medium)

Bulk backup and restore:
```bash
ssm export /prod --format yaml > backup.yml
ssm export /prod --format json > backup.json
ssm import backup.yml --env staging --prefix /staging
```

---

### 12. Add `tree` Command (Low)

Hierarchical view:
```bash
$ ssm tree /prod --env prod
/prod
├── database
│   ├── host
│   ├── password
│   └── username
├── api
│   └── key
└── config
    ├── debug
    └── log_level
```

---

### 13. Add `validate` Command (Low)

Validate parameter paths and values:
```bash
ssm validate backup.yml
ssm validate /prod/config --exists --env prod
```

---

### 14. Improve Test Coverage (High)

**Current State:** Tests only verify imports

**Recommended:**
- Add unit tests with mocked boto3 clients
- Add integration tests with localstack
- Test error handling paths
- Test CLI argument parsing

---

## Implementation Priority

### Phase 1 - Critical Fixes
1. Update dependencies (remove boto, update boto3/botocore)
2. Implement `put_many` (currently broken)
3. Fix hardcoded DEBUG log level

### Phase 2 - Performance
4. Implement lazy client initialization
5. Enable environment handle memoization
6. Add retry configuration

### Phase 3 - Core Features
7. Add `copy_many` command
8. Add `diff` command
9. Add `--dry-run` flag
10. Add stdin support

### Phase 4 - Enhanced Features
11. Add `search` command
12. Add parameter history support
13. Add parameter type selection
14. Add tagging support

### Phase 5 - Polish
15. Add shell completion
16. Add `export`/`import` commands
17. Add `tree` command
18. Improve test coverage

---

## Notes

- The codebase is well-structured with clear separation of concerns
- The CLI wrapper pattern is elegant and reduces boilerplate
- The dictionary protocol implementation for SecretManager is Pythonic
- Consider adding type hints throughout for better IDE support and documentation
