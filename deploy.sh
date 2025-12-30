#!/bin/bash
gcloud run deploy ses-mock-server --source . --region europe-southwest1 --project idinterpreter --allow-unauthenticated
