# SVOA Home Assistant integration

Custom Home Assistant integration for Stockholm Vatten och Avfall (SVOA),
starting with Returrundan collection locations and schedules.

## Current implementation slice

The first TDD slice implements the Returrundan response parser as a pure Python
module in `custom_components/svoa/returrundan.py`. It has no Home Assistant
runtime dependency and parses the supplied API snapshot into immutable,
typed dataclasses.

The parser currently:

- Parses all 11 areas and 89 locations in the supplied fixture.
- Splits each `heading` into a location name and address.
- Extracts Swedish date/time entries from the HTML in `text`.
- Ignores informational and empty HTML list items.
- Excludes entries marked with `<s>`, `<strike>`, or `<del>`.
- Assigns the explicitly supplied calendar year to each schedule date.
- Provides helpers to select the next visit strictly after an aware datetime.

The integration will supply the current `Europe/Stockholm` calendar year. It
will not roll an exhausted schedule into the next year or invent unpublished
visits.

## Development

```bash
python -m pip install pytest
pytest -q
```

Ruff is configured in `pyproject.toml`; install it and run:

```bash
ruff check .
ruff format --check .
```

The next implementation slices are the async HTTP client, Home Assistant
coordinator/config flow/entities, and their integration tests. The API client
will use Home Assistant's shared aiohttp session and conservative polling; the
fixture remains the primary parser regression test and live API requests will
not be part of the test suite.

## Development container (recommended)

The repository includes a VS Code Dev Container configured for Python 3.14.
The image build checks that the interpreter is at least Python 3.14.2, which
is the minimum required by current Home Assistant Core development metadata.

### Prerequisites

- Docker Engine (or Docker Desktop)
- Visual Studio Code
- The **Dev Containers** VS Code extension

### Start the environment

1. Open this repository folder in VS Code.
2. Run **Dev Containers: Reopen in Container** from the Command Palette.
3. Wait for the image build and dependency installation to finish. The setup
   creates a project-local `.venv` and installs the test and lint dependencies.
4. Open a new terminal and verify the interpreter:

   ```bash
   python --version
   .venv/bin/python --version
   ```

   VS Code is configured to use `.venv/bin/python` automatically.

### Common commands

```bash
# Run the test suite
.venv/bin/python -m pytest -q

# Lint and format checks
.venv/bin/ruff check .
.venv/bin/ruff format --check .

# Apply formatting
.venv/bin/ruff format .
```

The container forwards port `8123` for a local Home Assistant instance when
we add the runtime test configuration. The current setup is deliberately
focused on integration development and tests; it does not clone the full
Home Assistant Core repository or start a Home Assistant server automatically.

To rebuild after changing the Dockerfile or devcontainer configuration, run
**Dev Containers: Rebuild Container** from the Command Palette.
