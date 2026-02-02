<table width=100%>
  <tr>
    <td colspan=2><strong>
    aws-ssm-tool
      </strong>&nbsp;&nbsp;&nbsp;&nbsp;
    </td>
  </tr>
  <tr>
    <td width=15%><img src=https://raw.githubusercontent.com/Robot-Wranglers/aws-ssm-tool/master/img/icon.png style="width:150px"></td>
    <td>
    SSM tool is a small helper for interacting with Amazon Simple Systems Manager, focusing on secrets storage/retrieval.
    </td>
  </tr>
</table>
<a href=https://pypi.python.org/pypi/aws-ssm-tool/><img src="https://img.shields.io/pypi/l/aws-ssm-tool.svg"></a>
<a href=https://pypi.python.org/pypi/aws-ssm-tool/><img src="https://badge.fury.io/py/aws-ssm-tool.svg"></a>
<a href="https://github.com/Robot-Wranglers/aws-ssm-tool/actions/workflows/python-test.yml"><img src="https://github.com/Robot-Wranglers/aws-ssm-tool/actions/workflows/python-test.yml/badge.svg"></a>
<a href="https://hub.docker.com/r/robotwranglers/aws-ssm-tool/tags"><img src="https://img.shields.io/badge/dockerhub--blue.svg?logo=Docker"></a>

---------------------------------------------------------------------------------

<div class="toc">
<ul>
<li><a href="#overview">Overview</a></li>
<li><a href="#installation">Installation</a></li>
<li><a href="#usage">Usage</a></li>
<li><a href="#shell-completion">Shell Completion</a></li>
<li><a href="#environment-variables">Environment Variables</a></li>
<li><a href="#usage-from-docker">Usage from Docker</a></li>
</ul>
</div>


---------------------------------------------------------------------------------

## Overview

The [AWS SSM Parameter-Store](https://docs.aws.amazon.com/systems-manager/latest/userguide/systems-manager-parameter-store.html) is great, but can be awkward to work with via the `awscli` tool.  This project provides the `ssm` tool as an alternative interface with simple CRUD.  It also supports moving or copying trees of multiple parameters, and performing those operations across multiple AWS profiles.

See [setup.cfg](setup.cfg) to find the latest info about required versions of boto.  There are other dependencies, including the popular [click](https://click.palletsprojects.com/) library for CLI support and [rich](https://rich.readthedocs.io/) for pretty output.

See the [Usage section](#usage) for more details.

---------------------------------------------------------------------------------

## Installation

See [pypi](https://pypi.org/project/aws-ssm-tool) for available releases.

```
pip install aws-ssm-tool
```

---------------------------------------------------------------------------------

## Usage

After installation, you can invoke this tool as either `ssm` or `python -m ssm`.

### Available Commands

| Command | Aliases | Description |
|---------|---------|-------------|
| `list` | `ls` | List parameters below a path |
| `list-dirs` | `ls-dirs` | List directories (non-leaf paths) only |
| `read` | `get` | Read a single parameter value |
| `update` | `put`, `set` | Create or update a parameter |
| `delete` | `rm` | Delete a single parameter |
| `delete-path` | `rm-path` | Delete all parameters under a path |
| `copy` | `cp` | Copy a parameter to a new location |
| `copy-many` | `cp-many`, `cp-path` | Copy all parameters under a path |
| `move` | `mv` | Move a parameter to a new location |
| `move-many` | `mv-many`, `mv-path` | Move all parameters under a path |
| `get-many` | `get-path` | Get all parameters under a path |
| `put-many` | `put-path` | Create multiple parameters from a file |
| `search` | `find` | Search parameters by name pattern |
| `diff` | `compare` | Compare parameters between paths/profiles |
| `history` | `hist` | View parameter version history |
| `stat` | `st` | Show account info and parameter stats |
| `tags` | `show-tags` | Show tags for a parameter |
| `add-tags` | - | Add tags to a parameter |
| `remove-tags` | - | Remove tags from a parameter |

### Common Options

All commands support these options:

- `--profile`: AWS profile to use (default: `default`, or `AWS_PROFILE` env var)
- `--debug`: Enable verbose debug output
- `--quiet` / `-q`: Suppress non-essential output
- `--format`: Output format (`json`, `yaml`, `stdout`, `tree`, `env`)

### Examples

```bash
# List all parameters
ssm ls /

# Read a specific parameter
ssm get /prod/database/password

# Read a specific version
ssm get /prod/database/password --version 3

# Create/update a parameter
ssm put /dev/api/key "my-secret-value"

# Create with specific type (String, SecureString, StringList)
ssm put /config/setting "value" --type String

# Read value from file
ssm put /prod/cert --file ./certificate.pem

# Read value from stdin
echo "secret" | ssm put /prod/secret --stdin

# Copy a parameter
ssm cp /prod/config/key /staging/config/key

# Copy between AWS profiles
ssm cp /prod/secret /staging/secret --src-profile prod --dst-profile staging

# Copy an entire path hierarchy
ssm cp-many /prod/config /staging/config

# Search for parameters
ssm search "/prod/*/password"
ssm search "*database*"

# Compare two paths
ssm diff /prod/config /staging/config

# View parameter history
ssm history /prod/secret

# Delete with preview (dry-run)
ssm rm /test/secret --dry-run

# Delete an entire path (with confirmation)
ssm rm-path /test/old-config

# Bulk create from YAML file
ssm put-many /prod/config --file secrets.yaml

# View and manage tags
ssm tags /prod/secret
ssm add-tags /prod/secret --tag env=prod --tag team=backend
ssm remove-tags /prod/secret --key deprecated
```

See [the integration tests](https://github.com/Robot-Wranglers/aws-ssm-tool/tree/master/tests/integration/test.sh) for more examples.

---------------------------------------------------------------------------------

## Shell Completion

Enable tab completion for your shell:

### Bash

```bash
# Add to ~/.bashrc
eval "$(_SSM_COMPLETE=bash_source ssm)"

# Or generate a completion script
_SSM_COMPLETE=bash_source ssm > ~/.ssm-complete.bash
echo "source ~/.ssm-complete.bash" >> ~/.bashrc
```

### Zsh

```bash
# Add to ~/.zshrc
eval "$(_SSM_COMPLETE=zsh_source ssm)"
```

### Fish

```bash
# Add to ~/.config/fish/completions/ssm.fish
_SSM_COMPLETE=fish_source ssm > ~/.config/fish/completions/ssm.fish
```

---------------------------------------------------------------------------------

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `AWS_PROFILE` | AWS profile to use | `default` |
| `SSM_LOG_LEVEL` | Log verbosity (DEBUG, INFO, WARNING, ERROR) | `WARNING` |

---------------------------------------------------------------------------------

## Usage from Docker

If you want to build locally, see the [Dockerfile in this repo](Dockerfile) and use the [Makefile](Makefile):

```bash
$ make docker-build docker-test
```

If you don't want to build the container yourself, you can pull it like this:

```bash
$ docker pull robotwranglers/aws-ssm-tool
Using default tag: latest
latest: Pulling from robotwranglers/aws-ssm-tool
docker.io/robotwranglers/aws-ssm-tool:latest
```

See a typical invocation below.  The 1st volume is for authenticating with SSM.  The 2nd volume shares the working directory with the container so commands using files (like `ssm put --file ./path/to/file /path/to/key`) can still work.

```bash
$ docker run \
  -v ~/.aws:/root/.aws \
  -v `pwd`:/workspace \
  -w /workspace \
  docker.io/robotwranglers/aws-ssm-tool:latest \
    ssm ls /
```
