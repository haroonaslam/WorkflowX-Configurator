# WorkflowX Configurator

![WorkflowX Configurator banner](docs/images/Generated%20image%201.png)

WorkflowX Configurator turns sprawling ComfyUI graphs into selectable workflow profiles: reuse the same key names in different groups, switch one config, and the right value or relay source is picked at queue time. Instead of duplicating samplers, rewiring LoRA chains, or fighting nodes that can only store one global value, WorkflowX lets fast drafts, quality renders, model variants, and LoRA experiments live side by side while one selector decides which path is active. It can be used for multiple scenarios where you want to have one workflow to easily switch values of any node by preconfigure once or to switch between different profiles instead of creating separate workflows.

![WorkflowX Configurator overview](docs/images/Screenshot%202026-05-17%20001702.png)

## What It Does

- Defines workflow-local values with typed `Set` nodes.
- Reads values anywhere else with matching typed `Get` nodes.
- Lets each `Group Configurator` describe how every named ComfyUI group should behave.
- Lets one `Config Selector` choose exactly one configuration at a time.
- Applies group modes immediately in the canvas.
- Materializes Get values just before queueing, so repeated config switches do not require a browser refresh.
- One variable name removes any if/else logic routing. Simply the active path feeds the variable.

The package appears in ComfyUI's add-node menu under:

```text
WorkflowX_Configurator
```

## Installation

WorkflowX Configurator is available through ComfyUI Manager. Open Manager, search for `WorkflowX Configurator`, install it, then restart ComfyUI.

You can also install it manually by cloning this repository into your ComfyUI `custom_nodes` directory, or by copying this folder there:

```text
ComfyUI/
  custom_nodes/
    WorkflowX-Configurator/
      __init__.py
      nodes.py
      web/js/key_config_tools.js
```

Restart ComfyUI, then hard refresh the browser.

## Nodes

### Typed Set/Get Nodes

WorkflowX uses separate typed nodes instead of one dynamic output node. This keeps ComfyUI socket validation predictable.

![Primitive Set nodes](docs/images/set%20primitive.png)

| Setter | Getter | Output type |
| --- | --- | --- |
| `Set Int` | `Get Int` | `INT` |
| `Set Float` | `Get Float` | `FLOAT` |
| `Set String` | `Get String` | `STRING` |
| `Set Text` | `Get Text` | `STRING` multiline value |
| `Set Boolean` | `Get Boolean` | `BOOLEAN` |
| `Set Sampler` | `Get Sampler` | ComfyUI sampler combo |
| `Set Scheduler` | `Get Scheduler` | ComfyUI scheduler combo |
| `Set Relay` | `Get Relay` | wildcard runtime value |

Each `Set` node has:

- `key`: the name to publish, for example `Steps` or `CFG`.
- `value`: the typed value.

Each `Get` node has:

- `key`: the name to read.
- hidden internal fields managed by the frontend extension.

`Set Sampler` and `Set Scheduler` use ComfyUI's native sampler and scheduler option lists, so their Get nodes can be connected to sampler/scheduler inputs after those widgets are converted to inputs.

![Sampler and scheduler nodes](docs/images/samper%20scheduler.png)

### Set Relay / Get Relay

`Set Relay` and `Get Relay` route live ComfyUI graph values by key. They are for runtime objects such as `MODEL`, `CLIP`, `VAE`, `LATENT`, `CONDITIONING`, `IMAGE`, or `MASK`.

![Relay nodes](docs/images/relay.png)

Relays are different from typed Set/Get nodes:

- typed Set/Get nodes store serialized widget values.
- Relay nodes route an actual graph connection into the queued prompt.
- one Relay carries one output value.

For checkpoint switching, use three relay keys:

- checkpoint `MODEL` output -> `Set Relay` key `base_model`
- checkpoint `CLIP` output -> `Set Relay` key `base_clip`
- checkpoint `VAE` output -> `Set Relay` key `base_vae`

Then use matching `Get Relay` nodes wherever those values are needed.

For LoRA switching, place the LoRA loader inside a configured group, then connect its `MODEL` output into `Set Relay` key `pLora`. A downstream `Get Relay` key `pLora` can feed another LoRA loader or a sampler model input. The LoRA loader's checkpoint, epoch, strength, and other settings are preserved because the relay routes the loader's output object.

Relay routing uses the same scope rules as typed values. The selected source is patched into the queued prompt only; visible canvas links are not changed.

### Group Configurator

`Group Configurator` defines one named profile, such as `Speed`, `Quality`, or `Realism`.

![Group Configurator nodes](docs/images/Group%20Configurator.png)

It shows:

- `config_name`: the profile name.
- `Refresh groups`: rescan ComfyUI group frames after adding, deleting, or renaming groups.
- one dropdown per named group, with `Active`, `Bypass`, and `Mute`.

Mode meanings:

- `Active`: nodes in the group are normal and eligible for config-scoped Set/Get values.
- `Bypass`: nodes in the group are bypassed in the canvas and ignored for config-scoped Set/Get values.
- `Mute`: nodes in the group are muted in the canvas and ignored for config-scoped Set/Get values.

### Config Selector

`Config Selector` lists all `Group Configurator` names as toggles. Turning one on turns the others off and applies that config immediately.

![Config Selector node](docs/images/config%20selector.png)

It shows:

- `Refresh configs`: rescan configurator nodes after adding, deleting, or renaming them.
- `console_output`: choose `yes` to log queue-time Set/Get and Relay resolution details in the browser console.
- one toggle per config name.

## Lookup Rules

WorkflowX uses a global-first scope model.

1. If a matching `Set` node is outside configured groups, it is treated as global and wins.
2. If no global Set exists, WorkflowX uses matching Set nodes inside groups marked `Active` by the selected config.
3. Set nodes inside groups marked `Mute` or `Bypass` are ignored.
4. If duplicates remain at the chosen priority, WorkflowX logs a warning and uses the Set node with the highest node id.

This means you can intentionally place a global `Set Int Steps` outside config groups to override every profile, or place separate `Set Int Steps` nodes inside groups to make each profile choose its own value.

## Queue-Time Resolution

ComfyUI canvas state and serialized workflow metadata can briefly disagree after switching configs. To avoid stale values, WorkflowX resolves every Get node immediately before queueing:

1. The frontend reads the currently selected Config Selector toggle.
2. It evaluates Set/Get candidates from the live graph.
3. It writes the resolved value into hidden fields on each Get node.
4. The backend validates those hidden fields and returns the materialized value.
5. If the frontend fields are missing, the backend falls back to workflow metadata lookup.

This is why you can run `Speed`, switch to `Quality`, then queue again without refreshing the browser.

Set `console_output` to `yes` on `Config Selector` when debugging large workflows. Queue-time logs include the Get key, selected Set node id, group/global scope, resolved value for typed Get nodes, and selected Relay source node id for Relay nodes.

## Example Scenarios

### Fast Draft vs Quality Render

Create two groups:

- `FasterConfig`
- `RealConfig`

Inside `FasterConfig`:

- `Set Int` key `Steps`, value `4`
- `Set Float` key `CFG`, value `1.0`
- `Set Sampler` key `Sampler`, value `euler`
- `Set Scheduler` key `Scheduler`, value `simple`

Inside `RealConfig`:

- `Set Int` key `Steps`, value `20`
- `Set Float` key `CFG`, value `2.5`
- `Set Sampler` key `Sampler`, value `dpmpp_2m`
- `Set Scheduler` key `Scheduler`, value `karras`

Create two Group Configurators:

- `Speed`: `FasterConfig = Active`, `RealConfig = Mute`
- `Quality`: `FasterConfig = Mute`, `RealConfig = Active`

Use:

- `Get Int` key `Steps`
- `Get Float` key `CFG`
- `Get Sampler` key `Sampler`
- `Get Scheduler` key `Scheduler`

Selecting `Speed` queues with `Steps = 4`, `CFG = 1.0`, `Sampler = euler`, and `Scheduler = simple`. Selecting `Quality` queues with `Steps = 20`, `CFG = 2.5`, `Sampler = dpmpp_2m`, and `Scheduler = karras`.

### LoRA On/Off Profiles

Create a group around a LoRA loader, for example `Speedup Lora`.

Then configure:

- `Speed`: `Speedup Lora = Active`
- `Quality`: `Speedup Lora = Bypass`

Switching configs changes whether the LoRA path is active while also changing any typed values defined in the selected groups.

### Global Override

If you place `Set Int` key `Steps`, value `12` outside all configured groups, that value wins over grouped `Steps` values. Remove or rename the global Set node to return to profile-specific values.

## Troubleshooting

### The node package imported, but nodes do not show

Hard refresh the browser after restarting ComfyUI. The Python package can import before the frontend menu cache updates.

### Group names or config names are stale

Use:

- `Refresh groups` on `Group Configurator`
- `Refresh configs` on `Config Selector`

Use these after adding, deleting, or renaming groups/configurator nodes.

### A Get node returns the wrong value

Check for:

- a global Set node with the same key outside groups
- duplicate active Set nodes with the same key and type
- a selector toggle still pointing at the old config
- a group name mismatch after renaming a group

### Duplicate key warnings

Warnings such as this mean more than one eligible Set node exists at the same priority:

```text
Multiple Set Int nodes found for key 'Steps'; using node id 123.
```

The result is deterministic, but the workflow is easier to maintain if each key/type appears once per active scope.

## Development

Run the dependency-free validation checks from this folder:

```powershell
python -m py_compile __init__.py nodes.py
@'
import tests.test_nodes as t
for name in sorted(dir(t)):
    if name.startswith('test_'):
        getattr(t, name)()
        print(f'{name}: ok')
'@ | python -
node --check web/js/key_config_tools.js
```

The tests cover typed lookup, selected config lookup, stale mode handling, global precedence, duplicate handling, and queue-time resolved values.

## Repository Notes

- GitHub repo: `WorkflowX-Configurator`
- ComfyUI category: `WorkflowX_Configurator`
- License: no license file included
