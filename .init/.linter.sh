#!/bin/bash
cd /home/kavia/workspace/code-generation/simple-to-do-list-app-302026-302055/backend_api
source venv/bin/activate
flake8 .
LINT_EXIT_CODE=$?
if [ $LINT_EXIT_CODE -ne 0 ]; then
  exit 1
fi

