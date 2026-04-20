#!/bin/bash
# watch-schema.sh

WEB_SCHEMA="apps/web/core/lib/schema.ts"
API_SCHEMA="apps/api/db/models.py"

WEB_STAGED=$(git diff --cached --name-only | grep "$WEB_SCHEMA")
API_STAGED=$(git diff --cached --name-only | grep "$API_SCHEMA")

if [ -n "$WEB_STAGED" ] || [ -n "$API_STAGED" ]; then
  if [ -n "$WEB_STAGED" ] && [ -z "$API_STAGED" ]; then
    echo "================================================================="
    echo "WARNING: $WEB_SCHEMA is staged, but $API_SCHEMA is not."
    echo "Did you forget to update the backend schema?"
    echo "================================================================="
  elif [ -z "$WEB_STAGED" ] && [ -n "$API_STAGED" ]; then
    echo "================================================================="
    echo "WARNING: $API_SCHEMA is staged, but $WEB_SCHEMA is not."
    echo "Did you forget to update the frontend schema?"
    echo "================================================================="
  else
    echo "================================================================="
    echo "INFO: Both schemas ($WEB_SCHEMA and $API_SCHEMA) are staged."
    echo "Please ensure they are synchronized before committing."
    echo "================================================================="
  fi
fi
