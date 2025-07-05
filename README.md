# copick-shared-ui

Shared UI components for copick visualization plugins.

This package provides reusable Qt-based UI components that can be used across different copick visualization plugins 
(napari-copick, chimerax-copick, etc.).

## Installation

```bash
uv pip install copick-shared-ui
```

## Usage

```python
from copick_shared_ui import EditObjectTypesDialog, validate_copick_name

# Use the object types editor
dialog = EditObjectTypesDialog(parent=None, existing_objects=my_objects)
if dialog.exec_() == QDialog.Accepted:
    updated_objects = dialog.get_objects()

# Validate copick names
is_valid, sanitized, error_msg = validate_copick_name("my-object-name")
```

## Components

### EditObjectTypesDialog

A dialog for managing copick PickableObject types with features:
- Add, edit, and delete object types
- Real-time validation with visual feedback
- Color selection and management
- Support for all `copick.PickableObject` properties (EMDB/PDB IDs, thresholds, etc.)

### Validation

Utilities for validating copick entity names according to copick naming conventions.
