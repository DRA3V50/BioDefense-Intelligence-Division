# Frozen visual helper references

These byte-for-byte copies are provenance-preserving helper sources from the
approved recovery Subsystems #1 through #7. They are imported only by the
Subsystem #9 production renderer; their isolated main entry points are not
production entry points and must not be run by the workflow.

The production renderer derives masks and motion primitives from these helpers,
then supplies renderer-side adapters for the frozen Subsystem #8 state contract.
The copied approved masters live in assets/approved/.
