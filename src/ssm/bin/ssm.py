""" ssm.bin.ssm

  Command-line entry-points.
  (This file makes parts of `ssm.api` available via click)
"""

import functools

import click

from ssm import api, cli, util
from ssm.cli.wrapper import ApiWrapper

LOGGER = util.get_logger(__name__)


@click.command(cls=cli.Group)
def entry(*args, **kargs):  # noqa
    """
    SSM tool, a small helper for interacting with Amazon Simple Systems Manager
    for secrets storage/retrieval.

    Environment Variables:
        SSM_LOG_LEVEL: Set log verbosity (DEBUG, INFO, WARNING, ERROR)
        AWS_PROFILE: Default AWS profile to use
    """


ApiWrapper = functools.partial(
    ApiWrapper,
    entry=entry,
)

# Common options
dry_run_option = click.option(
    "--dry-run",
    is_flag=True,
    default=False,
    help="Preview changes without executing them.",
)

force_option = click.option(
    "--force",
    "-f",
    is_flag=True,
    default=False,
    help="Skip confirmation prompts.",
)

param_type_option = click.option(
    "--type",
    "param_type",
    type=click.Choice(["SecureString", "String", "StringList"]),
    default="SecureString",
    show_default=True,
    help="Parameter type.",
)

stdin_option = click.option(
    "--stdin",
    is_flag=True,
    default=False,
    help="Read value from stdin.",
)

version_option = click.option(
    "--version",
    type=int,
    default=None,
    help="Parameter version number.",
)

# === LIST COMMANDS ===

list = ApiWrapper(
    fxn=api.list,
    aliases=["ls"],
    extra_options=[
        cli.options.profile,
        cli.options.output_format_tree_default,
        cli.options.dirs_only,
        click.argument("path_prefix", nargs=1, default="/"),
    ],
)

list_dirs = ApiWrapper(
    fxn=api.list_dirs,
    aliases=["ls-dirs"],
    extra_options=[
        cli.options.profile,
        cli.options.output_format_stdout_default,
        click.argument("path_prefix", nargs=1, default="/"),
    ],
)

# === READ COMMANDS ===

stat = ApiWrapper(
    fxn=api.stat,
    aliases=["st"],
    extra_options=[
        cli.options.profile,
        cli.options.output_format_stdout_default,
        cli.options.caller_context,
        click.argument("path_prefix", nargs=1, default="/"),
    ],
)

read = ApiWrapper(
    fxn=api.read,
    aliases=["get"],
    extra_options=[
        cli.options.profile,
        version_option,
        cli.args.secret_name,
    ],
)

get_many = ApiWrapper(
    fxn=api.get_many,
    aliases=["get-path"],
    extra_options=[
        cli.options.profile,
        cli.options.flat_output,
        cli.options.output_format_yaml_default,
        cli.args.namespace,
    ],
)

# === WRITE COMMANDS ===

update = ApiWrapper(
    fxn=api.update,
    aliases=["put", "set"],
    extra_options=[
        cli.options.profile,
        cli.options.existing_file,
        stdin_option,
        param_type_option,
        click.argument("value", default="", nargs=1),
        cli.args.secret_name,
    ],
)

put_many = ApiWrapper(
    fxn=api.put_many,
    aliases=["put-path"],
    extra_options=[
        cli.options.profile,
        cli.options.existing_file,
        cli.options.output_format_yaml_default,
        dry_run_option,
        param_type_option,
        cli.args.namespace,
    ],
)

# === DELETE COMMANDS ===

delete = ApiWrapper(
    fxn=api.delete,
    aliases=["rm"],
    extra_options=[
        cli.options.profile,
        cli.args.secret_name,
        dry_run_option,
        click.option(
            "--no-backup",
            is_flag=True,
            default=False,
            help="Do not create backup file.",
        ),
    ],
)

delete_path = ApiWrapper(
    fxn=api.delete_path,
    aliases=["rm-path"],
    extra_options=[
        cli.options.profile,
        dry_run_option,
        force_option,
        click.option(
            "--no-backup",
            is_flag=True,
            default=False,
            help="Do not create backup files.",
        ),
        click.argument("path_prefix", nargs=1),
    ],
)

# === COPY/MOVE COMMANDS ===

copy = ApiWrapper(
    fxn=api.copy,
    aliases=["cp"],
    extra_options=[
        cli.options.src_profile_default,
        cli.options.dst_profile_default,
        dry_run_option,
        click.argument("dst_name", nargs=1),
        click.argument("src_name", nargs=1),
    ],
)

copy_many = ApiWrapper(
    fxn=api.copy_many,
    aliases=["cp-many", "cp-path", "copy-path"],
    extra_options=[
        cli.options.src_profile_default,
        cli.options.dst_profile_default,
        dry_run_option,
        click.argument("dst_name", nargs=1),
        click.argument("src_name", nargs=1),
    ],
)

move = ApiWrapper(
    fxn=api.move,
    aliases=["mv"],
    extra_options=[
        cli.options.src_profile_default,
        cli.options.dst_profile_default,
        dry_run_option,
        click.argument("dst_name", nargs=1),
        click.argument("src_name", nargs=1),
    ],
)

move_many = ApiWrapper(
    fxn=api.move_many,
    aliases=["mv-many", "move-path", "mv-path"],
    extra_options=[
        cli.options.src_profile_default,
        cli.options.dst_profile_default,
        dry_run_option,
        click.argument("dst_name", nargs=1),
        click.argument("src_name", nargs=1),
    ],
)

# === SEARCH/DIFF COMMANDS ===

search = ApiWrapper(
    fxn=api.search,
    aliases=["find"],
    extra_options=[
        cli.options.profile,
        cli.options.output_format_stdout_default,
        click.option(
            "--contains",
            default=None,
            help="Also match parameters containing this string.",
        ),
        click.argument("pattern", nargs=1),
    ],
)

diff = ApiWrapper(
    fxn=api.diff,
    aliases=["compare"],
    extra_options=[
        cli.options.src_profile_default,
        cli.options.dst_profile_default,
        cli.options.output_format_yaml_default,
        click.option(
            "--show-values",
            is_flag=True,
            default=False,
            help="Show actual values in diff output.",
        ),
        click.argument("dst_path", nargs=1),
        click.argument("src_path", nargs=1),
    ],
)

# === HISTORY COMMANDS ===

history = ApiWrapper(
    fxn=api.history,
    aliases=["hist"],
    extra_options=[
        cli.options.profile,
        cli.options.output_format_yaml_default,
        click.option(
            "--max-results",
            type=int,
            default=10,
            help="Maximum number of versions to return.",
        ),
        cli.args.secret_name,
    ],
)

# === TAG COMMANDS ===

tags = ApiWrapper(
    fxn=api.tags,
    aliases=["show-tags"],
    extra_options=[
        cli.options.profile,
        cli.options.output_format_yaml_default,
        cli.args.secret_name,
    ],
)


# Tag management requires special handling - use click directly
@entry.command(name="add-tags")
@cli.options.profile
@click.option("--tag", "-t", multiple=True, help="Tag in key=value format.")
@click.argument("secret_name", nargs=1)
def add_tags_cmd(profile, tag, secret_name):
    """Add tags to a parameter. Use --tag key=value (can be repeated)."""
    tag_list = []
    for t in tag:
        if "=" not in t:
            raise click.BadParameter(f"Tag must be in key=value format: {t}")
        k, v = t.split("=", 1)
        tag_list.append((k, v))

    if not tag_list:
        raise click.UsageError("At least one --tag is required")

    api.add_tags(secret_name, tag_list, profile=profile)
    click.echo(f"Added {len(tag_list)} tags to {secret_name}")


@entry.command(name="remove-tags")
@cli.options.profile
@click.option("--key", "-k", multiple=True, help="Tag key to remove.")
@click.argument("secret_name", nargs=1)
def remove_tags_cmd(profile, key, secret_name):
    """Remove tags from a parameter by key names."""
    if not key:
        raise click.UsageError("At least one --key is required")

    api.remove_tags(secret_name, list(key), profile=profile)
    click.echo(f"Removed {len(key)} tags from {secret_name}")
