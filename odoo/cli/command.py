# Part of Odoo. See LICENSE file for full copyright and licensing details.
import logging
import pkgutil
import sys
from pathlib import Path

import odoo.cli
from odoo.modules import get_module_path, get_modules, initialize_sys_path

commands = {}
"""All loaded commands"""


class Command:
    name = None

    def __init_subclass__(cls):
        cls.name = cls.name or cls.__name__.lower()
        commands[cls.name] = cls


ODOO_HELP = """\
Odoo CLI, use '{odoo_bin} --help' for regular server options.

Available commands:
    {command_list}

Use '{odoo_bin} <command> --help' for individual command help."""


class Help(Command):
    """ Display the list of available commands """
    def run(self, args):
        commands = list_commands()
        padding = max(len(cmd) for cmd in commands) + 2
        command_list = "\n    ".join([
            "    {}{}".format(name.ljust(padding), (command.__doc__ or "").strip())
            for name in sorted(commands)
            if (command := find_command(name))
        ])
        print(ODOO_HELP.format(  # pylint: disable=bad-builtin  # noqa: T201
            odoo_bin=Path(sys.argv[0]).name,
            command_list=command_list
        ))


def list_commands(from_internal=True, from_addons=True) -> list[str]:
    """ List of the available commands. """
    if from_internal:
        for module in pkgutil.iter_modules(odoo.cli.__path__):
            __import__(f"odoo.cli.{module.name}")
    # TODO: find a way to properly discover addons subcommands without importing the world
    if from_addons:
        logging.disable(logging.CRITICAL)
        initialize_sys_path()
        for module in get_modules():
            if (Path(get_module_path(module)) / 'cli').is_dir():
                __import__('odoo.addons.' + module)
        logging.disable(logging.NOTSET)
    return list(commands)


def find_command(name: str) -> Command | None:
    """ Get command by name. """
    # check in the loaded commands
    if command := commands.get(name):
        return command
    # import from odoo.cli
    try:
        if "." not in name:
            __import__(f"odoo.cli.{name}")
    except ImportError:
        pass
    else:
        if command := commands.get(name):
            return command
    # last try, list all commands
    list_commands(from_internal=False)
    return commands.get(name)


def main():
    args = sys.argv[1:]

    # The only shared option is '--addons-path=' needed to discover additional
    # commands from modules
    if len(args) > 1 and args[0].startswith('--addons-path=') and not args[1].startswith("-"):
        # parse only the addons-path, do not setup the logger...
        odoo.tools.config._parse_config([args[0]])
        args = args[1:]

    # Default legacy command
    command_name = "server"

    # Subcommand discovery
    if len(args) and not args[0].startswith("-"):
        command_name = args[0]
        args = args[1:]

    if command := find_command(command_name):
        o = command()
        o.run(args)
    else:
        sys.exit('Unknown command %r' % (command,))
