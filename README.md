# python-hilo

[![GitHub Release][releases-shield]][releases]
[![License][license-shield]](LICENSE)

[![Build Status][build-shield]][build]
[![Open in Dev Containers][devcontainer-shield]][devcontainer]

`python-hilo` (aka `pyhilo`) is a Python 3.11, `asyncio`-driven interface to the unofficial
Hilo API from Hydro Quebec. This is meant to be integrated into Home Assistant but can also
be used as a standalone library.

Home assistant integration is available [here](https://github.com/dvd-dev/hilo)

## TODO
- Type everything: almost done, got a few "type: ignore" to fix

## Later?
- Full docstrings and doc generation
- Unit testing
- Functional testing

If anyone wants to contribute, feel free to submit a PR. If you'd like to sync up first, you can
fire me an email me@dvd.dev

## Setting up development environment

The easiest way to start, is by opening a CodeSpace here on GitHub, or by using
the [Dev Container][devcontainer] feature of Visual Studio Code.

[![Open in Dev Containers][devcontainer-shield]][devcontainer]

This Python project is fully managed using the [Poetry][poetry] dependency
manager. But also relies on the use of NodeJS for certain checks during
development.

You need at least:

- Python 3.11+
- [Poetry][poetry-install]
- NodeJS 20+ (including NPM)

To install all packages, including all development requirements:

```bash
npm install
poetry install
```

As this repository uses the [pre-commit][pre-commit] framework, all changes
are linted and tested with each commit. You can run all checks and tests
manually, using the following command:

```bash
poetry run pre-commit run --all-files
```

To run just the Python tests:

```bash
poetry run pytest
```

## Authors & contributors

The original setup of this repository is by [David Vallée Delisle][dvd-dev].

Credits to [@frenck][frenck] for the base container configuration.
The license of python-wled can be found in
[third_party/python-wled/LICENSE](third_party/python-wled/LICENSE).

For a full list of all authors and contributors,
check [the contributor's page][contributors].



[build-shield]: https://github.com/dvd-dev/python-hilo/actions/workflows/tests.yaml/badge.svg
[build]: https://github.com/dvd-dev/python-hilo/actions/workflows/tests.yaml
[releases-shield]: https://img.shields.io/github/release/dvd-dev/python-hilo.svg
[releases]: https://github.com/dvd-dev/python-hilo/releases
[license-shield]: https://img.shields.io/github/license/dvd-dev/python-hilo.svg
[devcontainer-shield]: https://img.shields.io/static/v1?label=Dev%20Containers&message=Open&color=blue&logo=visualstudiocode
[devcontainer]: https://vscode.dev/redirect?url=vscode://ms-vscode-remote.remote-containers/cloneInVolume?url=https://github.com/dvd-dev/python-hilo
[poetry-install]: https://python-poetry.org/docs/#installation
[poetry]: https://python-poetry.org
[pre-commit]: https://pre-commit.com/
[dvd-dev]: https://github.com/dvd-dev
[frenck]: https://github.com/frenck
[contributors]: https://github.com/dvd-dev/python-hilo/graphs/contributors