"""Saved reference access. Spatial transformations are creation-only."""
import torch

def require_vae(vae):
    from comfy.ldm.minimax.vae import MiniMaxH3VideoVAE
    if not isinstance(getattr(vae,'first_stage_model',None),MiniMaxH3VideoVAE):raise ValueError('Connect the full H3 visual VAE for creation. A preview-only VAE cannot encode references.')

def process(path,shape,indices=None,vae=None):
    from .generation import load_mod
    z=load_mod(path).latent
    if list(z.shape[3:])!=list(shape[3:]):raise ValueError('Runtime resizing is not supported. Choose an available saved profile.')
    ids=list(range(z.shape[2])) if indices is None else indices
    if not ids:raise ValueError('The saved reference selection is empty.')
    if ids!=list(range(z.shape[2])):z=z.index_select(2,torch.tensor(ids,dtype=torch.long,device=z.device))
    return z,dict(processing='Unchanged saved reference',dimensions=[z.shape[4]*16,z.shape[3]*16],retained_samples=z.shape[2])
