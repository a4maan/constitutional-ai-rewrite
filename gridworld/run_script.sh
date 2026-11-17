#!/usr/bin/env bash

set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCRIPTS_DIR="$ROOT_DIR/scripts"
VENV_DIR="$ROOT_DIR/.venv"
REQUIREMENTS_FILE="$ROOT_DIR/requirements.txt"
PYTHON_BIN="${PYTHON_BIN:-python3}"

if [ ! -d "$SCRIPTS_DIR" ]; then
  echo "error: scripts directory '$SCRIPTS_DIR' does not exist" >&2
  exit 1
fi

script_paths=()
while IFS= read -r path; do
  [ -z "$path" ] && continue
  script_paths+=("$path")
done < <(find "$SCRIPTS_DIR" -mindepth 1 -maxdepth 1 -type f -name "*.py" -print | sort)

if [ "${#script_paths[@]}" -eq 0 ]; then
  echo "No Python scripts found in $SCRIPTS_DIR" >&2
  exit 1
fi

echo "Available scripts:"
for idx in "${!script_paths[@]}"; do
  rel_path="${script_paths[$idx]#"$ROOT_DIR/"}"
  printf "  %2d) %s\n" "$((idx + 1))" "$rel_path"
done
echo

read -rp "Select a script to run [1-${#script_paths[@]}]: " selection

if ! [[ "$selection" =~ ^[0-9]+$ ]] || [ "$selection" -lt 1 ] || [ "$selection" -gt "${#script_paths[@]}" ]; then
  echo "error: selection must be an integer between 1 and ${#script_paths[@]}" >&2
  exit 1
fi

selected_script="${script_paths[$((selection - 1))]}"

read -r -p "Enter arguments (space-delimited, optional): " user_args_line || true
declare -a user_args=()
if [ -n "${user_args_line:-}" ]; then
  IFS=' ' read -r -a user_args <<< "$user_args_line"
fi

if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  echo "error: cannot find python interpreter '$PYTHON_BIN' in PATH" >&2
  exit 1
fi

if [ ! -d "$VENV_DIR" ]; then
  echo "Creating virtual environment in $VENV_DIR"
  "$PYTHON_BIN" -m venv "$VENV_DIR"
fi

# shellcheck disable=SC1090
source "$VENV_DIR/bin/activate"

python -m pip install --upgrade pip setuptools wheel

if [ -f "$REQUIREMENTS_FILE" ]; then
  pip install -r "$REQUIREMENTS_FILE"
fi

export PYTHONPATH="$ROOT_DIR/src${PYTHONPATH:+:$PYTHONPATH}"
export PYTHONUNBUFFERED=1

echo "Running $selected_script"
if [ "${#user_args[@]}" -gt 0 ]; then
  python "$selected_script" "${user_args[@]}"
else
  python "$selected_script"
fi

