#!/bin/bash

# ============================================================
# Pravaah OS — Multi-Agent Tmux Launcher
# Splits one terminal into 6 panes, one per agent
# ============================================================

SESSION="pravaah"
PROJECT_DIR="${1:-$HOME/Projects/pravaah-os}"

# Kill existing session if running
tmux kill-session -t $SESSION 2>/dev/null

# ── Create session, first window ────────────────────────────
tmux new-session -d -s $SESSION -x "$(tput cols)" -y "$(tput lines)"

# ── Build the 6-pane layout ─────────────────────────────────
#
#  ┌─────────────────┬─────────────────┬─────────────────┐
#  │                 │                 │                 │
#  │   ORCHESTRATOR  │   ARCHITECT     │   PIPELINE      │
#  │   (pane 0)      │   (pane 1)      │   (pane 2)      │
#  │                 │                 │                 │
#  ├─────────────────┼─────────────────┼─────────────────┤
#  │                 │                 │                 │
#  │   BACKEND       │   FRONTEND      │  DEVOPS + QA    │
#  │   (pane 3)      │   (pane 4)      │  (pane 5)       │
#  │                 │                 │                 │
#  └─────────────────┴─────────────────┴─────────────────┘

# Start with pane 0 (full window)
# Split horizontally into top/bottom halves
tmux split-window -v -p 50 -t $SESSION

# Split top row into 3 columns
tmux select-pane -t $SESSION:0.0
tmux split-window -h -p 66 -t $SESSION:0.0
tmux split-window -h -p 50 -t $SESSION:0.1

# Split bottom row into 3 columns
tmux select-pane -t $SESSION:0.3
tmux split-window -h -p 66 -t $SESSION:0.3
tmux split-window -h -p 50 -t $SESSION:0.4

# ── Label each pane ─────────────────────────────────────────
label() {
  local pane=$1
  local title=$2
  local color=$3
  tmux send-keys -t $SESSION:0.$pane \
    "printf '\033]2;${title}\033\\\\' && echo -e '${color}'" Enter
}

# Colors using ANSI
RED='\033[0;31m'
CYAN='\033[0;36m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
MAGENTA='\033[0;35m'
NC='\033[0m'

# Print agent banners in each pane
tmux send-keys -t $SESSION:0.0 "clear && printf '\e[36m━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n  🎯 ORCHESTRATOR\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\e[0m\n'" Enter
tmux send-keys -t $SESSION:0.1 "clear && printf '\e[33m━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n  🏗️  ARCHITECT\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\e[0m\n'" Enter
tmux send-keys -t $SESSION:0.2 "clear && printf '\e[35m━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n  🎙️  PIPELINE ENGINEER\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\e[0m\n'" Enter
tmux send-keys -t $SESSION:0.3 "clear && printf '\e[32m━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n  ⚙️  BACKEND ENGINEER\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\e[0m\n'" Enter
tmux send-keys -t $SESSION:0.4 "clear && printf '\e[34m━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n  🎨 FRONTEND ENGINEER\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\e[0m\n'" Enter
tmux send-keys -t $SESSION:0.5 "clear && printf '\e[31m━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n  🚀 DEVOPS  |  🔍 QA REVIEWER\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\e[0m\n'" Enter

sleep 0.5

# ── cd into project dir in all panes ────────────────────────
for i in 0 1 2 3 4 5; do
  tmux send-keys -t $SESSION:0.$i "cd $PROJECT_DIR" Enter
done

sleep 0.3

# ── Launch claude in each pane ──────────────────────────────
# Pane 0: Orchestrator — this is the ONE you interact with
tmux send-keys -t $SESSION:0.0 "claude" Enter

# Panes 1-5: watch mode — these tail agent output files as they're created
# The orchestrator writes logs as subagents run; we tail PROGRESS.md + agent logs

tmux send-keys -t $SESSION:0.1 "echo 'Waiting for Architect...' && until [ -f ARCHITECTURE.md ]; do sleep 1; done && echo 'ARCHITECTURE.md created!' && tail -f ARCHITECTURE.md" Enter

tmux send-keys -t $SESSION:0.2 "echo 'Waiting for Pipeline...' && until grep -q 'PIPELINE: DONE' PROGRESS.md 2>/dev/null; do sleep 2; done || watch -n 1 'cat PROGRESS.md && echo \"---\" && ls pipeline/ 2>/dev/null'" Enter

tmux send-keys -t $SESSION:0.3 "echo 'Waiting for Backend...' && watch -n 2 'echo \"=== PROGRESS ===\"; cat PROGRESS.md 2>/dev/null; echo \"=== BACKEND FILES ===\"; ls backend/ 2>/dev/null || echo \"not started\"'" Enter

tmux send-keys -t $SESSION:0.4 "echo 'Waiting for Frontend...' && watch -n 2 'echo \"=== PROGRESS ===\"; cat PROGRESS.md 2>/dev/null; echo \"=== FRONTEND FILES ===\"; ls frontend/src/ 2>/dev/null || echo \"not started\"'" Enter

tmux send-keys -t $SESSION:0.5 "echo 'Waiting for DevOps + Review...' && watch -n 2 'echo \"=== PROGRESS ===\"; cat PROGRESS.md 2>/dev/null; echo \"=== REVIEW ===\"; cat REVIEW.md 2>/dev/null || echo \"not started\"'" Enter

# ── Focus on the Orchestrator pane ──────────────────────────
tmux select-pane -t $SESSION:0.0

# ── Attach ──────────────────────────────────────────────────
tmux attach-session -t $SESSION

