# Constitutional games

The two environments are independent projects:

* **[pgg/](pgg/README.md)** — newly implemented public goods game, including its Python package, CLI, documentation, and 20 tests.
* **[gridworld/](gridworld/README.md)** — the complete project imported from `C:/Users/armaa/constitutional-optimization-rewrite/constitutional-optimization-rewrite-main.zip`, with its source, scripts, tests, configuration examples, and visualizer. Archive contents were preserved, with the enclosing archive directory removed.

## Public Goods Game

From this workspace directory:

```powershell
cd pgg
python -m pgg --policy mixed
python -m unittest discover -s tests -v
```

The nested `pgg/pgg/` directory is the importable Python package; `pgg/` is the project root containing its tests and documentation. Run its commands from the project root.

## Gridworld

From this workspace directory:

```powershell
cd gridworld
.\run_script.bat
```

See the gridworld README and `.env.example` for dependencies and OpenRouter configuration. The gridworld launcher installs dependencies and runs experiments that can make model API calls. Importing the project does not run these experiments.
