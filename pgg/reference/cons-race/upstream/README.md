## Constitutional Optimization

This repository maintains a living world where LLM-guided residents share limited resources, follow a constitution, and cooperatively decide whether to advance the Shelter or Market projects. Residents converse via tool calls, witness each other’s hunger levels, and leave behind stories when they fall.

### Included Experiment Data

This snapshot includes the current experiment outputs plus two populated pre-existing backups. The data covers fragility, co-evolution, awareness-ablation, public-goods-game, and pure-adversary runs. See [`RUN_LOGS_README.md`](RUN_LOGS_README.md) for inventory, file formats, run-status caveats, and inspection commands.

### World Structure
- **Configuration & Prompts**: `src/config.py` centralizes runtime knobs (grid size, hunger toggles, corpse persistence, default models) and loads the shared prompt library from `src/config_prompts.py`.
- **Constitution Model**: `src/core/constitution.py` stores moral rules (`MoralRule`) that feed directly into each resident’s prompt.
- **Environment**: `src/environment/game.py` runs the world loop—movement, gathering, deposits, communications, hunger depletion, and corpse tracking—while exposing hooks for tool-driven actions.
- **Tooling**: `src/core/tools/tool.py` + `src/core/tools/registry.py` expose tools such as `move_resident`, `gather_resources`, `deposit_resources`, `rest_and_recover`, `attack_resident`, `steal_resource`, `review_private_messages`, `review_public_broadcasts`, and `consult_memory` that align with OpenRouter’s [tool calling format](https://openrouter.ai/docs/features/tool-calling).
- **Resident Controllers & Logging**: `src/core/langchain_resident.py` wraps OpenRouter models via LangChain’s tool-calling interface, guaranteeing exactly one environment action per turn, while `src/core/logging.py` emits structured turn logs (`AgentTurnLog`) into `logs/<experiment>/residents/<name>.jsonl` via `util/logger.py`.
- **Live Visualizer**: `src/visualizer/` hosts a FastAPI app that mirrors the running world in real time. Experiments launch it by default—run `python scripts/experiment.py --preset baseline` and open the printed URL (defaults to `http://127.0.0.1:8000`, configurable via `VISUALIZER_HOST` / `VISUALIZER_PORT` or `--visualizer-host/--visualizer-port`; pass `--disable-visualizer` to opt out).

### Vital Systems & Conflict
- Set `HUNGER_ENABLED=true` (plus optional `HUNGER_MAX_ENERGY`, `HUNGER_COST_PER_TURN`, `HUNGER_FOOD_RECOVERY`, `HUNGER_REST_RECOVERY`, or per-action `HUNGER_COST_<ACTION>` overrides) to activate hunger. Starving residents collapse when energy hits zero. Use `HUNGER_LEAVE_CORPSE=true|false` to decide whether their bodies remain in the world after death (belongings always stay behind).
- Enable `ATTACK_ENABLED=true` with `ATTACK_SUCCESS_CHANCE=0.25` (default) to allow violent conflicts. Successful strikes eliminate the target immediately and generate notifications/log entries.
- Enable `STEAL_ENABLED=true` with `STEAL_SUCCESS_CHANCE=0.4` (default) to allow theft attempts that quietly transfer one unit of a named resource upon success.
  - The attack/steal tools are always exposed for planning consistency, but when the toggles are disabled the world rejects each attempt and records it in the logs for future auditing.

### Getting Started

#### Quick Start with Run Scripts
The easiest way to run experiments is with the interactive run scripts:

**On macOS/Linux:**
```bash
./run_script.sh
```

**On Windows:**
```cmd
run_script.bat
```

These scripts will:
1. Auto-create a virtual environment in `.venv` if it doesn't exist
2. Install/upgrade pip, setuptools, wheel
3. Install all dependencies from `requirements.txt`
4. Present an interactive menu of available scripts in the `scripts/` directory
5. Prompt for command-line arguments (optional)
6. Run your selected script with proper PYTHONPATH configuration

#### Direct Python Execution
If you prefer direct control, manually set up your environment:

```bash
# Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Set PYTHONPATH and run
export PYTHONPATH="$(pwd)/src:$PYTHONPATH"
python scripts/experiment.py --preset baseline
```

### Running Experiments

The `scripts/experiment.py` CLI provides presets and options for running society simulations.

**Automatic Configuration Logging:** Every experiment automatically creates an `experiment_config.json` file in its log directory containing all settings (residents, constitution, environment parameters, agent config, etc.) for full reproducibility.

#### Available Presets
- **`baseline`** (default): Balanced hunger enabled, corpses retained, 8×8 grid, 40 turns, 6 residents (3 shelter, 3 market)
- **`peaceful`**: Hunger disabled to focus on cooperation, same residents and constitution

#### Command-Line Options

```bash
# Run with default baseline preset and visualizer
python scripts/experiment.py --preset baseline

# Run peaceful preset without visualizer (headless)
python scripts/experiment.py --preset peaceful --disable-visualizer

# Override visualizer host/port
python scripts/experiment.py --preset baseline \
  --visualizer-host 0.0.0.0 \
  --visualizer-port 8080
```

**Arguments:**
- `--preset {baseline,peaceful}` – Select experiment preset (default: `baseline`)
- `--disable-visualizer` – Run without launching the live visualizer
- `--visualizer-host HOST` – Override visualizer bind address (default from config or env)
- `--visualizer-port PORT` – Override visualizer port (default from config or env)

#### Programmatic Use
The reusable harness under `src/experiments/base.py` lets you embed runs in other contexts (tests, services, batch jobs):

```python
from experiments.base import ExperimentConfig, ExperimentRunner, ResidentProfile
from core.constitution import MoralRule

config = ExperimentConfig(
    name="my-experiment",
    description="Custom society simulation",
    residents=[
        ResidentProfile("Alice", "shelter"),
        ResidentProfile("Bob", "market"),
    ],
    constitution_rules=[
        MoralRule(name="Cooperate", guidance="Help neighbors", summary="Be nice", priority=1),
    ],
    environment_overrides={"max_turns": 30, "hunger": {"enabled": True}},
)

runner = ExperimentRunner(config, enable_visualizer=True)
runner.run()
```

### Live Visualizer

The visualizer launches automatically with experiments (unless disabled) and provides real-time monitoring of:
- **Grid View**: Resident positions, resource tiles, corpses
- **Agent Status**: Energy levels, inventory, last actions
- **Event Log**: Turn-by-turn actions, communications, deaths
- **Constitution**: Active moral rules guiding behavior

**Access:** Open the URL printed to console (default: `http://127.0.0.1:8000`)

**Configuration:**
- Set via environment variables: `VISUALIZER_HOST`, `VISUALIZER_PORT`
- Override per-run with CLI flags: `--visualizer-host`, `--visualizer-port`
- Disable entirely with: `--disable-visualizer`

The visualizer uses FastAPI with server-sent events (SSE) to stream world state updates in real time.

### Configuration

All runtime behavior is controlled through environment variables. Create a `.env` file in the project root:

```bash
# Required: OpenRouter API key for LLM calls
OPENROUTER_API_KEY=your_key_here

# Agent Settings
DEFAULT_AGENT_MODEL=openai/gpt-4o          # Default: openai/gpt-oss-120b
AGENT_TEMPERATURE=1.0                       # Default: 1.0
AGENT_MAX_HISTORY=12                        # Max conversation turns retained (default: 12)
AGENT_MEMORY_REASONING_CHARS=400            # Thought snippet length cap (default: 400)
AGENT_MEMORY_MESSAGE_CHARS=160              # Chat snippet length cap (default: 160)
AGENT_MEMORY_NOTIFICATION_CHARS=160         # Alert snippet length cap (default: 160)
AGENT_ENABLE_MEMORY=true                    # Enable memory tool (default: true)

# Environment Settings
GRID_WIDTH=8                                # Grid width (default: 8)
GRID_HEIGHT=8                               # Grid height (default: 8)
MAX_TURNS=50                                # Simulation length (default: 50)
REVIEW_INTERVAL=5                           # Turns between message reviews (default: 5)
ENV_RANDOM_SEED=42                          # Fix RNG seed for reproducibility (default: none)

# Hunger System
HUNGER_ENABLED=true                         # Enable energy depletion (default: false)
HUNGER_MAX_ENERGY=100                       # Starting energy (default: 100)
HUNGER_COST_PER_TURN=5                      # Energy consumed per turn (default: 5)
HUNGER_REST_RECOVERY=20                     # Energy restored by rest action (default: 20)
HUNGER_FOOD_RECOVERY=20                     # Energy restored per food unit (default: 20)
HUNGER_STARVATION_THRESHOLD=0               # Death threshold (default: 0)
HUNGER_LEAVE_CORPSE=true                    # Leave corpse on death (default: true)
# Optional per-action depletion rates (defaults: 0). Provide uppercase action names:
# HUNGER_COST_MOVE, HUNGER_COST_GATHER, HUNGER_COST_DEPOSIT_WOOD, HUNGER_COST_DEPOSIT_STONE,
# HUNGER_COST_COMMUNICATE, HUNGER_COST_SEND_PRIVATE_MESSAGE, HUNGER_COST_REST,
# HUNGER_COST_CONSUME_FOOD, HUNGER_COST_GIVE_RESOURCE

# Conflict Systems
ATTACK_ENABLED=true                         # Enable violent attacks (default: false)
ATTACK_SUCCESS_CHANCE=0.25                  # Probability of successful attack (default: 0.25)
STEAL_ENABLED=true                          # Enable theft (default: false)
STEAL_SUCCESS_CHANCE=0.4                    # Probability of successful theft (default: 0.4)

# Tooling
TOOL_PARALLEL_CALLS=true                    # Allow parallel tool calls (default: true)
TOOL_AUTO_CHOICE=true                       # Auto tool selection (default: true)
MAX_TOOL_CALLS_PER_TURN=1                   # Max environment actions per turn (default: 1)

# Visualizer
VISUALIZER_HOST=127.0.0.1                   # Bind address (default: 127.0.0.1)
VISUALIZER_PORT=8000                        # Bind port (default: 8000)
```

**Note:** Experiment presets (in `scripts/experiment.py`) can override these defaults via `environment_overrides`.

### Constitutional Evolution with OpenEvolve

The `scripts/expirement_evolution.py` experiment uses [OpenEvolve](https://github.com/algorithmicsuperintelligence/openevolve) to automatically evolve agent constitutions that maximize market progress. This implements an evolutionary algorithm where LLMs generate mutations to constitution rules, and the best-performing variants are selected over multiple generations.

#### How It Works

1. **Initial Constitution**: Starts with a baseline set of rules in `scripts/evolution/initial_constitution.py`
2. **Simulation Evaluation**: Each constitution variant runs a 40-turn society simulation with 5 agents
3. **Fitness Scoring**: Market progress (0-100%) is the primary optimization target, with bonuses for agent survival and total contributions
4. **Evolution**: OpenEvolve uses LLMs to generate improved constitution variants based on top performers
5. **Selection**: MAP-Elites maintains diversity while converging on high-performing constitutions

#### Running the Evolution Experiment

```bash
# Ensure OpenRouter API key is set
export OPENROUTER_API_KEY=your_key_here

# Run with default settings (50 iterations)
python scripts/expirement_evolution.py

# Run with custom iteration count
python scripts/expirement_evolution.py --iterations 100

# Specify output directory
python scripts/expirement_evolution.py --output-dir ./my_evolution_run
```

#### Configuration

The evolution is configured via `openevolve_config.yaml` in the project root. Key settings:

```yaml
# LLM configuration - uses OpenRouter
llm:
  api_base: "https://openrouter.ai/api/v1"
  models:
    - name: "openai/gpt-4o-mini"
      weight: 0.7
    - name: "openai/gpt-4o"
      weight: 0.3
  temperature: 0.8  # Higher for creative mutations

# Evolution parameters
max_iterations: 50
early_stopping_patience: 15
checkpoint_interval: 5

# Evaluation settings
evaluator:
  timeout: 600  # 10 min per simulation
  cascade_evaluation: true  # Quick filtering of bad candidates
```

#### Output

Evolution results are saved to `logs/evolution-<timestamp>/`:
- `best_constitution.py` – The highest-scoring evolved constitution
- `checkpoints/` – Periodic snapshots of evolution state
- `evolution_trace.jsonl` – Detailed log of all mutations and scores

#### Dependencies

The evolution experiment requires OpenEvolve:

```bash
pip install openevolve
```

This is included in `requirements.txt` alongside other project dependencies.

### Project Structure & More Info
Refer to `PORTING_GUIDE.md` for the full description of world dynamics, metrics, and outer-loop expectations.
