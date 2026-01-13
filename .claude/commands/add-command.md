---
description: Add a new CLI command to omelet
allowed-tools: Read, Edit, Write
argument-hint: [command-name]
---

Add a new CLI command named `$ARGUMENTS` to the omelet CLI.

## Steps

1. Read `omelet/cli.py` to understand the existing command structure

2. Add a new Click command following this pattern:
   ```python
   @main.command()
   @click.argument("file", type=click.Path(exists=True))
   @click.option("--option", "-o", help="Option description")
   def command_name(file: str, option: Optional[str]) -> None:
       """Command description shown in --help."""
       # Implementation
       click.echo("Processing...")
   ```

3. Add any helper functions or classes needed

4. Update `omelet/__init__.py` if new exports are needed

5. Suggest tests to add for the new command

Ask the user for:
- What the command should do
- What arguments/options it needs
- Any special requirements
