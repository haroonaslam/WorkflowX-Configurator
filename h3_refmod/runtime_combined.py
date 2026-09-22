"""Join already compatible saved references; never resize or encode."""
import torch
from .optimization import visual_cost
MODE='Build combined video from selected references'
def plan(selected,settings):
    if not selected:raise ValueError('Select at least one source.')
    dimensions={tuple(e['shape'][3:]) for e in selected}
    if len(dimensions)!=1:raise ValueError('Combined sources must use one compatible saved combined profile.')
    shape=list(selected[0]['shape']);shape[2]=sum(e['shape'][2] for e in selected)
    return dict(shape=shape,sources=selected,dimensions=[shape[4]*16,shape[3]*16],tokens=visual_cost(shape),source_count=len(selected))
def assemble(description,vae=None,with_report=False):
    from .visual_processing import process
    pairs=[process(e['path'],e['shape'],e['indices']) for e in description['sources']]
    result=torch.cat([z.cpu() for z,_ in pairs],dim=2)
    return (result,[dict(report,source=e['name'],profile=e['profile_name']) for e,(_,report) in zip(description['sources'],pairs)]) if with_report else result
