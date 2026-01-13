---
name: click-cli
description: Work with Click CLI framework for Python. Use when the user needs to add commands, options, or modify CLI behavior.
allowed-tools: Read, Write, Edit, Grep
---

# Click CLI Development Skill

This skill helps develop CLI commands using the Click framework.

## Click Basics

### Command Structure
```python
import click

@click.group()
def main():
    """Omelet CLI - Upload images from Markdown."""
    pass

@main.command()
@click.argument("file", type=click.Path(exists=True))
@click.option("--folder", "-f", default=None, help="Folder name")
def buildmarkdown(file: str, folder: str) -> None:
    """Process markdown and upload images."""
    click.echo(f"Processing {file}...")
```

### Common Decorators

```python
# Required argument
@click.argument("name")

# File path that must exist
@click.argument("file", type=click.Path(exists=True))

# Optional flag
@click.option("--verbose", "-v", is_flag=True)

# Option with default
@click.option("--count", "-c", default=1, type=int)

# Required option
@click.option("--token", required=True, envvar="API_TOKEN")

# Multiple values
@click.option("--tag", "-t", multiple=True)

# Choice option
@click.option("--format", type=click.Choice(["json", "yaml"]))
```

### Output Helpers

```python
# Regular output
click.echo("Message")

# Styled output
click.secho("Error!", fg="red", bold=True)
click.secho("Success!", fg="green")

# Progress bar
with click.progressbar(items) as bar:
    for item in bar:
        process(item)

# Prompt user
name = click.prompt("Enter name")
confirmed = click.confirm("Continue?")
```

### Error Handling

```python
# Exit with error
raise click.ClickException("Something went wrong")

# Exit with code
raise SystemExit(1)

# Abort
raise click.Abort()
```

## Project Patterns

### Current Commands in `omelet/cli.py`:
- `buildmarkdown` - Process markdown and upload images
- `public` - Publish markdown to webhook

### Adding New Command
1. Add function with `@main.command()` decorator
2. Add arguments and options as needed
3. Implement the logic
4. Test with `omelet --help` and `omelet command --help`

## Testing Click Commands

```python
from click.testing import CliRunner
from omelet.cli import main

def test_command():
    runner = CliRunner()
    result = runner.invoke(main, ["buildmarkdown", "test.md"])
    assert result.exit_code == 0
```
