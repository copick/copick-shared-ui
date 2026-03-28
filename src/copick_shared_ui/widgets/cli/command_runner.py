"""Background execution of Click commands via CliRunner.

Provides argument building from form values and background thread execution
using the unified thread_worker infrastructure (napari or superqt).
"""

from typing import Any, Dict, List, Optional

import click
from click.testing import CliRunner

from copick_shared_ui.core.click_schema import CommandSchema, ParamSchema, _HIDDEN_PARAMS

# Import thread_worker from napari or superqt
try:
    from napari.qt.threading import thread_worker
except ImportError:
    try:
        from superqt.utils._qthreading import thread_worker
    except ImportError:
        thread_worker = None


def build_args(
    schema: CommandSchema,
    values: Dict[str, Any],
    config_path: Optional[str] = None,
) -> List[str]:
    """Build CLI argument list from form values and schema.

    Args:
        schema: The command schema.
        values: Dict mapping param name -> value from form widgets.
        config_path: Config path to inject for the --config param.

    Returns:
        List of string arguments suitable for CliRunner.invoke().
    """
    args: List[str] = []
    arguments_by_name: Dict[str, ParamSchema] = {}

    # Inject hidden params
    if config_path:
        args.extend(["-c", config_path])

    for param in schema.params:
        name = param.name

        # Skip hidden params (already injected above or not needed in GUI)
        if name in _HIDDEN_PARAMS:
            continue

        if param.is_argument:
            arguments_by_name[name] = param
            continue

        value = values.get(name)

        if param.is_flag:
            if value is True:
                # Use the first opt string (e.g. "--overwrite")
                if param.opt_strings:
                    # For flag pairs, use the positive form
                    flag = param.opt_strings[0]
                    args.append(flag)
            elif value is False and param.default is True:
                # Explicitly set the negative form if default is True
                if param.secondary_name and len(param.opt_strings) > 1:
                    # Use secondary opt string (e.g. "--no-overwrite")
                    args.append(param.opt_strings[-1])
            continue

        if value is None or value == "":
            continue

        # Get the preferred option string (long form preferred)
        opt = None
        for o in param.opt_strings:
            if o.startswith("--"):
                opt = o
                break
        if opt is None and param.opt_strings:
            opt = param.opt_strings[0]
        if opt is None:
            opt = f"--{name.replace('_', '-')}"

        # Handle multiple values
        if param.multiple and isinstance(value, list):
            for v in value:
                args.extend([opt, str(v)])
        else:
            args.extend([opt, str(value)])

    # Append positional arguments in order
    for param in schema.params:
        if param.is_argument:
            value = values.get(param.name)
            if value is not None:
                args.append(str(value))

    return args


def _find_leaf_command(schema: CommandSchema) -> click.Command:
    """Get the leaf Click command object for invocation."""
    return schema.click_command


if thread_worker is not None:

    @thread_worker
    def run_click_command_worker(
        click_command: click.Command,
        args_list: List[str],
    ):
        """Run a Click command in a background thread via CliRunner.

        Yields progress messages and returns (exit_code, output) tuple.
        """
        yield f"Running: copick {' '.join(args_list)}"

        runner = CliRunner(mix_stderr=False)
        try:
            result = runner.invoke(click_command, args_list, catch_exceptions=False)
            exit_code = result.exit_code
            output = result.output or ""
            stderr = result.stderr if hasattr(result, "stderr") else ""
            if stderr:
                output = output + "\n" + stderr
        except SystemExit as e:
            exit_code = e.code if e.code is not None else 0
            output = ""
        except Exception as e:
            exit_code = 1
            output = f"Error: {e}"

        return exit_code, output

else:

    def run_click_command_worker(click_command, args_list):
        raise RuntimeError(
            "thread_worker not available. Install napari or superqt."
        )
