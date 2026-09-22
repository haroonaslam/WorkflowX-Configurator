"""Explicit queued legacy preview generation; tensor files are read-only."""
import os
import tempfile
from pathlib import Path
from PIL import Image
from .characters import load_character, save_details, safe_path
from .generation import load_mod


class PrepareThumbnail:
    @classmethod
    def INPUT_TYPES(cls):
        return {'required': {'character_path': ('STRING', {'default':''}),
            'regenerate': ('BOOLEAN', {'default':False}), 'vae': ('VAE',)}}
    RETURN_TYPES = ('H3RC_CHARACTER', 'STRING')
    RETURN_NAMES = ('character', 'preview_path')
    FUNCTION = 'prepare'
    CATEGORY = 'WorkflowX/Video/H3 Refmod'
    OUTPUT_NODE = True
    @classmethod
    def IS_CHANGED(cls, **kwargs): return float('nan')

    def prepare(self, character_path, vae, regenerate=False):
        c=load_character(character_path)
        if not c['visuals']: return c, 'Audio-only character: no visual thumbnail.'
        if c.get('preview') and not regenerate: return c,c['preview']
        m=load_mod(c['visuals'][0])
        # Decode the complete saved visual so temporal VAE semantics are preserved.
        frames=vae.decode(m.latent)
        if frames.ndim==5: frames=frames[0]
        frame=frames[0].detach().cpu().clamp(0,1).numpy()
        image=Image.fromarray((frame*255).astype('uint8'))
        image.thumbnail((512,512))
        destination=safe_path(str(Path(c['manifest_path']).with_suffix(''))+'.preview.png',must_exist=False)
        fd,tmp=tempfile.mkstemp(dir=destination.parent,suffix='.png');os.close(fd)
        try:
            image.save(tmp);os.replace(tmp,destination)
        finally:
            if os.path.exists(tmp): os.unlink(tmp)
        c['preview']=str(destination);c=save_details(c)
        return {'ui':{'text':[f"Thumbnail saved for @{c['alias']}"]},'result':(c,c['preview'])}
