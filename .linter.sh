#!/bin/bash
cd /home/kavia/workspace/code-generation/tictactrack-61694-9b5139f2/tic_tac_toe_backend
source venv/bin/activate
flake8 .
LINT_EXIT_CODE=$?
if [ $LINT_EXIT_CODE -ne 0 ]; then
  exit 1
fi

