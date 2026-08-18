# Legacy configurator migration

The following deprecated nodes remain registered only so older workflow JSON can load:

- Group Configurator (`KVGC_GroupConfigurator`)
- Group Scopes (`KVGC_GroupScopes`)
- Config Selector (`KVGC_ConfigSelector`)
- Config Selector Advanced (`KVGC_ConfigSelectorAdvanced`)

Do not add them to new workflows.

## Migrate to Config SelectorX

1. Load the old workflow and record its group-to-scope assignments and named configurations.
2. Add Config SelectorX (`KVGC_ConfigSelectorX`).
3. Recreate assignments with **Scopes** and named values with **Configs**.
4. Select each configuration and verify every typed Get and Relay consumer.
5. Delete the four legacy controller nodes only after the new state is stored in the workflow.
6. Save under a new filename and reload it once before retiring the original.

Typed Set/Get and Relay node IDs remain current; only the controller arrangement changes. See the [Config SelectorX guide](CONFIG_SELECTOR_X.md) and [advanced configured production example](../examples/07-advanced-configured-production.json).
