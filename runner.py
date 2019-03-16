import os
import subprocess
import click
import toml


# TODO: logging
def run_command(command, config):
    if isinstance(command, str):  # command label
        command = get_command(command, config)
    if isinstance(command["command"], list):  # pipeline
        for cmd in command["command"]:
            # if we override settings of a command in a pipeline
            if cmd in command:
                config[cmd].update(command[cmd])
            run_command(cmd, config)  # have to resolve command labels
        return

    if "environment" in command:
        env = os.environ.copy()
        env.update(command["environment"])
    else:
        env = None

    if "options" in command:
        opts = " ".join(
            f"--{key}={val}" for (key, val) in command["options"].items()
        )
    else:
        opts = ""

    subprocess.run(
        "{} {}".format(command["command"], opts), env=env, shell=True
    )


def get_command(command, config):
    if command not in config:
        raise ValueError(f"Command {command} not found in configuration.")
    if (
        not isinstance(config[command], dict)
        or "command" not in config[command]
    ):
        raise ValueError(
            f"Command {command} must be a table, with the command value set."
        )
    return config[command]


def get_config(filename):
    try:
        with open(filename) as f:
            data = toml.load(f)
            if "base" in data:
                data = {**get_config(data["base"]), **data}
        return data
    except FileNotFoundError:
        raise click.BadOptionUsage(
            option_name="--config",
            message=f"Configuration file {filename} not found.",
        )


def get_overrides(ctx):
    def set_recursive(store, dotted_name, value):
        head, _, tail = dotted_name.partition(".")
        if tail:
            store.setdefault(head, {})
            set_recursive(store[head], tail, value)
        else:
            store[head] = value

    overrides = {}
    remaining = iter(ctx.args)
    for option in remaining:
        if not option.startswith("--"):  # only options are allowed
            raise click.BadParameter(option)
        if "=" in option:
            option, value = option.split("=", maxsplit=1)
        else:
            value = next(remaining)
        set_recursive(overrides, option[2:], value)
    return overrides


@click.command(
    context_settings={"ignore_unknown_options": True, "allow_extra_args": True}
)
@click.option("--config", "-c", type=click.Path(), default="project.toml")
@click.argument("command", type=str, required=False)
@click.pass_context
def cli(ctx, config, command):
    config = {**get_config(config), **get_overrides(ctx)}
    if not command:
        print("Available commands:")
        for key in config:
            if isinstance(config[key], dict):
                print(f"\t{key}")
        return
    try:
        run_command(command, config)
    except ValueError as e:
        print(e.args[0])
        return


if __name__ == "__main__":
    cli()  # pylint: disable=no-value-for-parameter
