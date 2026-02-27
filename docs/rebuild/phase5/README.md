# Phase 5: Imports/Workflows Parity

## Overview
Phase 5 implements import job processing and workflow decision handling with:
- Import job CRUD with file format detection and mapping profile support
- Workflow decision CRUD with approval tracking
- Schema tables for import_job, workflow_decision, mapping_profile
- Permission enforcement for import.run and workflow.run
- UI pages for imports and workflows management

## Key Deliverables
1. [src/apps/imports/constants.py](constants.py) - import job status and file format enums
2. [src/apps/imports/models.py](models.py) - ImportJob and MappingProfile models
3. [src/apps/imports/views.py](views.py) - import job CRUD endpoints + UI pages
4. [src/apps/workflows/constants.py](constants.py) - workflow decision status enum
5. [src/apps/workflows/models.py](models.py) - WorkflowDecision model
6. [src/apps/workflows/views.py](views.py) - workflow decision CRUD endpoints + UI pages
7. Schema updates: vc_import_job, vc_mapping_profile, vc_workflow_decision
8. Permission mappings for import.run and workflow.run
9. Rebuild test coverage (imports + workflows)

## Architecture Notes
- Import jobs track submission, processing, and results
- Mapping profiles store source-to-target field configurations
- Workflow decisions track approval state and audit trail
- Both use consistent lifecycle/status validation patterns from Phase 4
- Permission model enforces import.run and workflow.run for mutations
