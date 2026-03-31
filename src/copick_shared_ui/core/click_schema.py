"""Click command introspection for auto-generating UI from CLI definitions.

Walks Click command trees, extracts parameter schemas, and produces
normalized dataclass representations that can be used to generate Qt forms.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import click

# Import CopickURI type — optional, only needed for detection
try:
    from copick.cli.types import CopickURI as _CopickURIType
except ImportError:
    _CopickURIType = None


# Parameter names that should be auto-filled from project context (hidden from UI)
_HIDDEN_PARAMS = {"config", "debug"}

# Parameter name -> auto-fill type mapping
_AUTO_FILL_MAP = {
    "config": "config",
    "debug": "debug",
    "run": "run_names",
    "run_names": "run_names",
    "user_id": "user_id",
    "session_id": "session_id",
    "voxel_spacing": "voxel_spacing",
    "mesh_voxel_spacing": "voxel_spacing",
    "voxel_size": "voxel_spacing",
}

# Commands that don't make sense in a GUI context
UI_EXCLUDED_COMMANDS = {"browse", "info", "config", "stats", "deposit"}


@dataclass
class URIParamMeta:
    """Metadata for a URI parameter, extracted from CopickURI type."""

    object_type: str  # "picks", "mesh", "segmentation", "tomogram", "feature", "any"
    role: str  # "input", "output", "reference"


@dataclass
class ParamSchema:
    """Schema for a single Click parameter."""

    name: str
    param_type: str  # "string", "int", "float", "bool", "choice", "path", "uri"
    human_name: str
    help: str
    required: bool
    default: Any
    is_flag: bool
    multiple: bool
    choices: Optional[Tuple[str, ...]]
    group_name: Optional[str]
    is_argument: bool
    secondary_name: Optional[str]  # For flag pairs like --overwrite/--no-overwrite
    auto_fill_type: Optional[str]  # "config", "run_names", "user_id", "uri_*", etc.
    opt_strings: List[str] = field(default_factory=list)  # e.g. ["-r", "--run-names"]
    uri_meta: Optional[URIParamMeta] = None  # Set when param type is CopickURI


@dataclass
class ParamGroupSchema:
    """Schema for a group of related parameters (from click-option-group)."""

    name: str
    help: str
    params: List[ParamSchema] = field(default_factory=list)


@dataclass
class CommandSchema:
    """Schema for a single Click command."""

    name: str
    full_path: List[str]  # e.g. ["convert", "picks2seg"]
    help: str
    short_help: str
    params: List[ParamSchema]
    param_groups: List[ParamGroupSchema]
    category: str
    click_command: Any  # Reference to click.Command


def _humanize_name(name: str) -> str:
    """Convert parameter name to human-readable form."""
    return name.replace("_", " ").replace("-", " ").title()


def _normalize_type(param: click.Parameter) -> str:
    """Map Click parameter type to normalized type string."""
    ptype = param.type

    if _CopickURIType is not None and isinstance(ptype, _CopickURIType):
        return "uri"
    if isinstance(ptype, click.Choice):
        return "choice"
    if isinstance(ptype, click.Path):
        return "path"
    if isinstance(ptype, (click.types.FloatParamType, click.FloatRange)):
        return "float"
    if isinstance(ptype, (click.types.IntParamType, click.IntRange)):
        return "int"
    if isinstance(ptype, click.types.BoolParamType):
        return "bool"
    if isinstance(ptype, click.types.StringParamType):
        return "string"

    # Fallback
    return "string"


_PATH_NAME_SUFFIXES = ("_path", "_dir", "_directory", "_file", "_folder")
_PATH_EXACT_NAMES = {"output", "outdir", "target_dir", "output_dir", "output_file"}


def _looks_like_path(param: click.Parameter) -> bool:
    """Heuristic: does this string param likely represent a filesystem path?

    Checks metavar and parameter name for path-like patterns. Used as a
    fallback when the Click type is str but the param semantically takes a path.
    """
    metavar = getattr(param, "metavar", None)
    if metavar and metavar.upper() in ("PATH", "DIR", "DIRECTORY", "FILE"):
        return True
    name = param.name or ""
    if name in _PATH_EXACT_NAMES:
        return True
    return any(name.endswith(suffix) for suffix in _PATH_NAME_SUFFIXES)


def _get_option_group_name(param: click.Parameter) -> Optional[str]:
    """Extract option group name from click-option-group parameters."""
    # click-option-group attaches a `group` attribute to GroupedOption instances
    if hasattr(param, "group") and param.group is not None:
        group = param.group
        if hasattr(group, "name"):
            name = group.name
            # Strip leading whitespace/newlines from group names
            if isinstance(name, str):
                return name.strip()
    return None


def _is_group_title_fake_option(param: click.Parameter) -> bool:
    """Check if this is a sentinel parameter from click-option-group."""
    cls_name = type(param).__name__
    return cls_name == "_GroupTitleFakeOption"


def _extract_param_schema(param: click.Parameter) -> Optional[ParamSchema]:
    """Extract schema from a single Click parameter."""
    # Skip click-option-group sentinel params
    if _is_group_title_fake_option(param):
        return None

    # Skip the context parameter
    if param.name == "ctx" or param.human_readable_name == "CTX":
        return None

    is_argument = isinstance(param, click.Argument)
    is_flag = getattr(param, "is_flag", False)
    multiple = getattr(param, "multiple", False)

    # Get choices if applicable
    choices = None
    if isinstance(param.type, click.Choice):
        choices = tuple(param.type.choices)

    # Detect secondary name for flag pairs (e.g. --overwrite/--no-overwrite)
    secondary_name = None
    if is_flag and isinstance(param, click.Option) and param.secondary_opts:
        secondary_name = param.secondary_opts[0] if param.secondary_opts else None

    # Get option strings
    opt_strings = []
    if isinstance(param, click.Option):
        opt_strings = list(param.opts) + list(param.secondary_opts)

    # Determine auto-fill type
    auto_fill_type = _AUTO_FILL_MAP.get(param.name)

    # Determine param type, with heuristic promotion for path-like strings
    param_type = "bool" if is_flag else _normalize_type(param)
    if param_type == "string" and not is_argument and _looks_like_path(param):
        param_type = "path"

    # Extract URI metadata from CopickURI type
    uri_meta = None
    if _CopickURIType is not None and isinstance(param.type, _CopickURIType):
        uri_meta = URIParamMeta(
            object_type=param.type.object_type,
            role=param.type.role,
        )
        auto_fill_type = f"uri_{uri_meta.object_type}_{uri_meta.role}"

    return ParamSchema(
        name=param.name,
        param_type=param_type,
        human_name=_humanize_name(param.human_readable_name),
        help=getattr(param, "help", "") or "",
        required=param.required if not is_flag else False,
        default=param.default,
        is_flag=is_flag,
        multiple=multiple,
        choices=choices,
        group_name=_get_option_group_name(param),
        is_argument=is_argument,
        secondary_name=secondary_name,
        auto_fill_type=auto_fill_type,
        opt_strings=opt_strings,
        uri_meta=uri_meta,
    )


def _extract_command_schema(
    command: click.Command,
    path: List[str],
    category: str,
) -> CommandSchema:
    """Extract schema from a Click command."""
    params: List[ParamSchema] = []
    groups_dict: Dict[str, ParamGroupSchema] = {}
    default_group = ParamGroupSchema(name="Options", help="", params=[])

    for param in command.params:
        schema = _extract_param_schema(param)
        if schema is None:
            continue
        params.append(schema)

        # Organize into groups
        if schema.group_name:
            if schema.group_name not in groups_dict:
                # Try to get group help from the click-option-group
                group_help = ""
                if hasattr(param, "group") and param.group and hasattr(param.group, "help"):
                    group_help = param.group.help or ""
                groups_dict[schema.group_name] = ParamGroupSchema(
                    name=schema.group_name,
                    help=group_help,
                    params=[],
                )
            groups_dict[schema.group_name].params.append(schema)
        else:
            default_group.params.append(schema)

    # Build ordered group list
    param_groups: List[ParamGroupSchema] = list(groups_dict.values())
    if default_group.params:
        param_groups.append(default_group)

    help_text = command.help or ""
    short_help = command.short_help or command.get_short_help_str(limit=150)

    return CommandSchema(
        name=command.name or path[-1] if path else "unknown",
        full_path=path,
        help=help_text,
        short_help=short_help,
        params=params,
        param_groups=param_groups,
        category=category,
        click_command=command,
    )


def _get_category_for_command(name: str, categories: Dict[str, List[str]]) -> str:
    """Look up which category a command belongs to."""
    for cat, commands in categories.items():
        if name in commands:
            return cat
    return "Other"


def _has_visible_params(command: click.Command) -> bool:
    """Check if a command has any user-visible parameters.

    Commands with only hidden params (config, debug) or no params at all
    are likely placeholders and should not appear in the UI.
    """
    for param in command.params:
        if _is_group_title_fake_option(param):
            continue
        if param.name in _HIDDEN_PARAMS or param.name == "ctx":
            continue
        if param.human_readable_name == "CTX":
            continue
        return True
    return False


def _walk_command_tree(
    group: click.Group,
    categories: Dict[str, List[str]],
    path: Optional[List[str]] = None,
    parent_category: Optional[str] = None,
) -> List[CommandSchema]:
    """Recursively walk a Click command tree and extract schemas."""
    if path is None:
        path = []

    schemas: List[CommandSchema] = []

    for name, cmd in sorted(group.commands.items()):
        if name in UI_EXCLUDED_COMMANDS:
            continue

        current_path = path + [name]
        category = parent_category or _get_category_for_command(name, categories)

        if isinstance(cmd, click.MultiCommand):
            # Recurse into subgroups (covers click.Group and click.MultiCommand)
            sub_schemas = _walk_command_tree(cmd, categories, current_path, category)
            schemas.extend(sub_schemas)
        elif isinstance(cmd, click.Command):
            # Skip placeholder commands that have no visible parameters
            if not _has_visible_params(cmd):
                continue
            schema = _extract_command_schema(cmd, current_path, category)
            schemas.append(schema)

    return schemas


def discover_commands() -> List[CommandSchema]:
    """Discover all copick CLI commands and return their schemas.

    Uses the pre-built CLI object from copick which includes both
    core commands and plugin commands (from copick-utils, copick-torch, etc.).
    """
    try:
        from copick.cli.cli import COMMAND_CATEGORIES, cli
    except ImportError:
        return []

    return _walk_command_tree(cli, COMMAND_CATEGORIES)


def discover_commands_by_category() -> Dict[str, List[CommandSchema]]:
    """Discover commands and organize them by category."""
    schemas = discover_commands()
    by_category: Dict[str, List[CommandSchema]] = {}
    for schema in schemas:
        by_category.setdefault(schema.category, []).append(schema)
    return by_category


def get_applicable_commands(
    schemas: List[CommandSchema],
    object_type: str,
) -> List[CommandSchema]:
    """Return commands that accept the given object_type as input or reference.

    Used by the actions bar and context menu to show applicable tools
    for a selected tree item.

    Args:
        schemas: All discovered command schemas.
        object_type: The copick object type to match (e.g. "picks", "segmentation").

    Returns:
        Commands that have at least one URI param accepting this object type.
    """
    results = []
    for schema in schemas:
        for param in schema.params:
            if (
                param.uri_meta is not None
                and param.uri_meta.object_type in (object_type, "any")
                and param.uri_meta.role in ("input", "reference")
            ):
                results.append(schema)
                break
    return results
