""" ssm.api

  See the docs here:
    https://github.com/Robot-Wranglers/aws-ssm-tool
"""

import collections
import fnmatch
import json
import sys
import typing

import botocore
import yaml

from ssm import util
from ssm.api.environment import Environment

LOGGER = util.get_logger(__name__)

__all__ = [
    "read",
    "update",
    "delete",
    "delete_path",
    "list",
    "list_dirs",
    "copy",
    "move",
    "copy_many",
    "move_many",
    "get_many",
    "put_many",
    "stat",
    "search",
    "history",
    "tags",
    "add_tags",
    "remove_tags",
    "diff",
]


def _get_env(
    profile: typing.Optional[str] = None, env=None, **kwargs
) -> Environment:
    """gets environment from environment or named profile"""
    assert profile or env, str(kwargs)
    env = Environment.from_profile(profile) if profile else env
    assert env
    return env


def _get_client(profile: typing.Optional[str] = None, **kwargs):
    """gets handle for the secrets-manager"""
    env = _get_env(profile=profile, **kwargs)
    env.logger.info("getting client")
    sman = env.secrets
    return sman


def read(
    secret_name: str, version: typing.Optional[int] = None, **kwargs
) -> str:
    """
    reads a secret, optionally at a specific version
    """
    assert secret_name, f"cannot read secret_name `{secret_name}`"
    env = _get_env(**kwargs)
    try:
        if version:
            params = dict(Name=f"{secret_name}:{version}", WithDecryption=True)
            return env.ssm.get_parameter(**params)["Parameter"]["Value"]
        return env.secrets[secret_name]
    except (KeyError,) as exc:
        LOGGER.error(f"KeyError: {exc}")
        raise SystemExit(1)
    except botocore.exceptions.ClientError as exc:
        LOGGER.error(f"ClientError: {exc}")
        raise SystemExit(1)


def stat(
    path_prefix: str = "/", caller_context: bool = True, **kwargs
) -> typing.OrderedDict:
    """
    reports status, including account details and metadata summary for SSM parameters.
    """
    env = _get_env(**kwargs)
    caller_id = env.caller_id
    result = collections.OrderedDict()
    if caller_context:
        LOGGER.info("lookup caller-context")
        result.update(
            context=dict(
                user=dict(
                    id=caller_id.get("UserId"),
                    arn=caller_id.get("Arn"),
                ),
                account=dict(
                    profile_name=env.profile_name,
                    id=env.account_id,
                    alias=env.account_alias,
                    region_name=env.region_name,
                ),
            )
        )
    result.update(
        parameters=dict(
            root=path_prefix,
            key_count=len(env.secrets.under(path_prefix)),
            children=env.secrets.children(path_prefix),
        ),
    )
    return result


def list_dirs(path_prefix: str, **kwargs) -> typing.List[str]:
    """
    lists subpaths (i.e. directories) under the given path.
    no leaf nodes are returned
    """
    kwargs.update(dirs_only=True)
    return list(path_prefix, **kwargs)


def list(
    path_prefix: str, dirs_only: bool = False, **kwargs
) -> typing.List[str]:
    """
    Lists parameters with prefixes below the given path.

    This is recursive by default and only returns leafs:
    use `list-dirs` or pass `--dirs` to get directories only.
    """
    # WARNING: do not use `list()` builtin here..
    secrets = _get_client(**kwargs)
    if dirs_only:
        return secrets.children(path_prefix)
    result = secrets.under(path_prefix).keys()
    result = [x for x in result]
    return result


def get_many(
    namespace: str, flat_output: bool = False, **kwargs
) -> typing.Dict[str, str]:
    """
    gets many secrets from specified hierarchy/namespace
    """
    secrets = _get_client(**kwargs)
    result = secrets.under(namespace)
    if flat_output:
        result = util.flatten_output(result)
    return result


def delete(
    secret_name: str,
    no_backup: bool = False,
    dry_run: bool = False,
    **kwargs,
) -> typing.Union[str, bool]:
    """deletes secret (keeping a local-backup is default). Use --dry-run to preview."""

    def get_backup_file(prefix):
        return ".tmp.{}".format(prefix.replace("/", "_"))

    if dry_run:
        LOGGER.info(f"[DRY-RUN] Would delete: {secret_name}")
        return secret_name

    secrets = _get_client(**kwargs)
    try:
        parameter = read(secret_name=secret_name, **kwargs)
    except (botocore.exceptions.ClientError, SystemExit):
        LOGGER.warning(f"error reading secret @ `{secret_name}` (is this a path?)")
        parameter = None
    if parameter is not None:
        if not no_backup:
            backup = get_backup_file(secret_name)
            LOGGER.debug(f"backup to: {backup}")
            with open(backup, "w") as fhandle:
                fhandle.write(parameter)
        del secrets[secret_name]
        return parameter
    else:
        return False


def delete_path(
    path_prefix: str,
    no_backup: bool = False,
    dry_run: bool = False,
    force: bool = False,
    **kwargs,
) -> typing.List[str]:
    """
    Delete all parameters under a path prefix.
    Use --dry-run to preview, --force to skip confirmation.
    """
    secrets = _get_client(**kwargs)
    keys = [k for k in secrets.under(path_prefix).keys()]

    if not keys:
        LOGGER.warning(f"No parameters found under {path_prefix}")
        return []

    if dry_run:
        LOGGER.info(
            f"[DRY-RUN] Would delete {len(keys)} parameters under {path_prefix}:"
        )
        for k in keys:
            LOGGER.info(f"  - {k}")
        return keys

    if not force:
        LOGGER.warning(
            f"About to delete {len(keys)} parameters under {path_prefix}"
        )
        confirm = input("Type 'yes' to confirm: ")
        if confirm.lower() != "yes":
            LOGGER.info("Aborted.")
            return []

    results = []
    for key in keys:
        result = delete(key, no_backup=no_backup, **kwargs)
        if result:
            results.append(key)
            LOGGER.info(f"Deleted: {key}")

    return results


def move(
    src_name: str,
    dst_name: str,
    src_profile: str = "default",
    dst_profile: str = "default",
    dry_run: bool = False,
    **kwargs,
) -> bool:
    """
    moves a secret from src to dest. Use --dry-run to preview.
    """
    if dry_run:
        LOGGER.info(f"[DRY-RUN] Would move: {src_name} -> {dst_name}")
        return True

    result = copy(
        src_name,
        dst_name,
        src_profile=src_profile,
        dst_profile=dst_profile,
        **kwargs,
    )
    if result:
        src_env = Environment.from_profile(src_profile)
        del src_env.secrets[src_name]
    return result


def move_many(
    src_name: str,
    dst_name: str,
    src_profile: str = "default",
    dst_profile: str = "default",
    dry_run: bool = False,
    **kwargs,
) -> typing.List[bool]:
    """
    moves a whole path of secrets to a new location. Use --dry-run to preview.
    """
    dst_name = dst_name[:-1] if dst_name.endswith("/") else dst_name
    src_man = _get_client(profile=src_profile)
    names = [n for n in src_man.under(src_name).keys()]

    if dry_run:
        LOGGER.info(
            f"[DRY-RUN] Would move {len(names)} parameters under `{src_name}`:"
        )
        for name in names:
            new_name = "/".join([dst_name, name[len(src_name) :]])
            LOGGER.info(f"  {name} -> {new_name}")
        return [True] * len(names)

    LOGGER.debug(f"moving {len(names)} parameters under `{src_name}`")
    results = []
    for name in names:
        new_name = "/".join([dst_name, name[len(src_name) :]])
        LOGGER.debug(f"  {name} -> {new_name}")
        results.append(
            move(
                name,
                new_name,
                src_profile=src_profile,
                dst_profile=dst_profile,
                **kwargs,
            )
        )
    return results


def copy(
    src_name: str,
    dst_name: str,
    src_profile: str = "default",
    dst_profile: str = "default",
    dry_run: bool = False,
    **kwargs,
) -> bool:
    """
    copies a secret from given source to destination. Use --dry-run to preview.
    """
    if dry_run:
        LOGGER.info(f"[DRY-RUN] Would copy: {src_name} -> {dst_name}")
        return True

    # NB: mind the signature, this code is reused by `move`
    src_man = _get_client(profile=src_profile)
    dst_man = _get_client(profile=dst_profile)
    dst_name = dst_name or src_name
    try:
        value = src_man[src_name]
    except (botocore.exceptions.ClientError, KeyError):
        LOGGER.error(
            f"Cant retrieve `{src_name}` using profile `{src_man.env.name}`!"
        )
        LOGGER.warning(
            f"Hint: Use `ssm copy-many ...` if `{src_name}` is a hierarchy"
        )
        return False
    else:
        dst_man[dst_name] = value
        return True


def copy_many(
    src_name: str,
    dst_name: str,
    src_profile: str = "default",
    dst_profile: str = "default",
    dry_run: bool = False,
    **kwargs,
) -> typing.List[typing.Tuple[str, str]]:
    """
    Copy all parameters from one path to another.
    Supports cross-profile copying. Use --dry-run to preview.
    """
    dst_name = dst_name.rstrip("/")
    src_name_stripped = src_name.rstrip("/")
    src_man = _get_client(profile=src_profile)
    dst_man = _get_client(profile=dst_profile)

    params = src_man.under(src_name)

    if not params:
        LOGGER.warning(f"No parameters found under {src_name}")
        return []

    if dry_run:
        LOGGER.info(f"[DRY-RUN] Would copy {len(params)} parameters:")
        for name in params.keys():
            new_name = f"{dst_name}{name[len(src_name_stripped):]}"
            LOGGER.info(f"  {name} -> {new_name}")
        return [
            (k, f"{dst_name}{k[len(src_name_stripped):]}") for k in params.keys()
        ]

    results = []
    for name, value in params.items():
        new_name = f"{dst_name}{name[len(src_name_stripped):]}"
        dst_man[new_name] = value
        results.append((name, new_name))
        LOGGER.info(f"Copied: {name} -> {new_name}")

    return results


def update(
    secret_name: str,
    value: str = "",
    file: typing.Optional[str] = None,
    stdin: bool = False,
    param_type: str = "SecureString",
    **kwargs,
) -> bool:
    """
    updates secret in given location with new value.
    Supports reading from file (--file), stdin (--stdin or value of '-'),
    and parameter type selection (--type).
    """
    # Handle stdin input
    if stdin or value == "-":
        value = sys.stdin.read().strip()
    elif file:
        with open(file) as f:
            value = f.read()

    if not value:
        err = (
            "when `value` is not given as second arg, "
            "then `--file` or `--stdin` must be provided"
        )
        LOGGER.critical(err)
        raise RuntimeError(err)

    secrets = _get_client(**kwargs)
    secrets.set_secret(name=secret_name, value=value, param_type=param_type)
    return True


def put_many(
    namespace: str,
    input_file: typing.Optional[str] = None,
    format: str = "yaml",
    dry_run: bool = False,
    param_type: str = "SecureString",
    **kwargs,
) -> typing.List[str]:
    """
    Put multiple secrets from a file to a namespace.
    Expects a flat key-value structure in the input file.
    Use --dry-run to preview.
    """
    if not input_file:
        err = "input_file is required for put_many (use --file)"
        LOGGER.critical(err)
        raise RuntimeError(err)

    with open(input_file) as f:
        if format in ["yaml", "yml"]:
            data = yaml.safe_load(f)
        elif format == "json":
            data = json.load(f)
        else:
            raise ValueError(f"Unsupported format: {format}")

    if not isinstance(data, dict):
        raise ValueError(f"Expected dict in file, got {type(data)}")

    namespace = namespace.rstrip("/")

    if dry_run:
        LOGGER.info(
            f"[DRY-RUN] Would create {len(data)} parameters under {namespace}:"
        )
        for key in data.keys():
            LOGGER.info(f"  - {namespace}/{key}")
        return [f"{namespace}/{k}" for k in data.keys()]

    secrets = _get_client(**kwargs)
    results = []
    for key, value in data.items():
        full_path = f"{namespace}/{key}"
        secrets.set_secret(name=full_path, value=str(value), param_type=param_type)
        results.append(full_path)
        LOGGER.info(f"Created: {full_path}")

    return results


def search(
    pattern: str,
    contains: typing.Optional[str] = None,
    **kwargs,
) -> typing.List[str]:
    """
    Search parameters by name pattern (supports wildcards).
    Use fnmatch patterns like '/prod/*/api_key' or '*database*'.
    """
    secrets = _get_client(**kwargs)
    all_keys = secrets.keys()

    results = []
    for key in all_keys:
        # Match by pattern
        if fnmatch.fnmatch(key, pattern):
            results.append(key)
        # Also check contains if specified
        elif contains and contains in key:
            results.append(key)

    return sorted(set(results))


def diff(
    src_path: str,
    dst_path: str,
    src_profile: str = "default",
    dst_profile: str = "default",
    show_values: bool = False,
    **kwargs,
) -> typing.Dict[str, typing.Any]:
    """
    Compare parameters between two paths/environments.
    Returns dict with 'only_in_src', 'only_in_dst', 'different', 'identical_count'.
    """
    src_man = _get_client(profile=src_profile)
    dst_man = _get_client(profile=dst_profile)

    src_path = src_path.rstrip("/")
    dst_path = dst_path.rstrip("/")

    src_params = src_man.under(src_path)
    dst_params = dst_man.under(dst_path)

    # Normalize keys by removing the path prefix
    def normalize_key(key, prefix):
        return key[len(prefix) :] if key.startswith(prefix) else key

    src_normalized = {normalize_key(k, src_path): v for k, v in src_params.items()}
    dst_normalized = {normalize_key(k, dst_path): v for k, v in dst_params.items()}

    src_keys = set(src_normalized.keys())
    dst_keys = set(dst_normalized.keys())

    only_in_src = sorted(src_keys - dst_keys)
    only_in_dst = sorted(dst_keys - src_keys)
    common_keys = src_keys & dst_keys

    different = []
    identical = []

    for key in sorted(common_keys):
        src_val = src_normalized[key]
        dst_val = dst_normalized[key]
        if src_val != dst_val:
            if show_values:
                different.append({"key": key, "src": src_val, "dst": dst_val})
            else:
                different.append(key)
        else:
            identical.append(key)

    result = {
        "only_in_src": [f"{src_path}{k}" for k in only_in_src],
        "only_in_dst": [f"{dst_path}{k}" for k in only_in_dst],
        "different": different,
        "identical_count": len(identical),
    }

    return result


def history(
    secret_name: str,
    max_results: int = 10,
    **kwargs,
) -> typing.List[typing.Dict]:
    """
    Get version history for a parameter.
    Returns list of version info dicts.
    """
    env = _get_env(**kwargs)
    paginator = env.ssm.get_paginator("get_parameter_history")
    pages = paginator.paginate(
        Name=secret_name,
        WithDecryption=True,
        PaginationConfig={"MaxItems": max_results},
    )

    results = []
    for page in pages:
        for param in page["Parameters"]:
            results.append(
                {
                    "version": param.get("Version"),
                    "value": param.get("Value"),
                    "type": param.get("Type"),
                    "last_modified": str(param.get("LastModifiedDate", "")),
                    "last_modified_user": param.get("LastModifiedUser", ""),
                }
            )

    return results


def tags(secret_name: str, **kwargs) -> typing.List[typing.Dict[str, str]]:
    """
    Get tags for a parameter.
    """
    env = _get_env(**kwargs)
    response = env.ssm.list_tags_for_resource(
        ResourceType="Parameter",
        ResourceId=secret_name,
    )
    return response.get("TagList", [])


def add_tags(
    secret_name: str,
    tag_list: typing.List[typing.Tuple[str, str]],
    **kwargs,
) -> bool:
    """
    Add tags to a parameter.
    tag_list is a list of (key, value) tuples.
    """
    env = _get_env(**kwargs)
    env.ssm.add_tags_to_resource(
        ResourceType="Parameter",
        ResourceId=secret_name,
        Tags=[{"Key": k, "Value": v} for k, v in tag_list],
    )
    LOGGER.info(f"Added {len(tag_list)} tags to {secret_name}")
    return True


def remove_tags(
    secret_name: str,
    tag_keys: typing.List[str],
    **kwargs,
) -> bool:
    """
    Remove tags from a parameter by key names.
    """
    env = _get_env(**kwargs)
    env.ssm.remove_tags_from_resource(
        ResourceType="Parameter",
        ResourceId=secret_name,
        TagKeys=tag_keys,
    )
    LOGGER.info(f"Removed {len(tag_keys)} tags from {secret_name}")
    return True
