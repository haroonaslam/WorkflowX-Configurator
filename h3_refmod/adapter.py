"""Output adapters for resolved picker selections; never writes character packages."""
from comfy_execution.graph import ExecutionBlocker
from .reference_plan import build_plan
from .generation import prepare_saved, prepare_combined
from .vendor.py.refmod_core import H3RefMod

MODES = ['Original RefMod', 'Video frames']

class RefModXAdapter:
    @classmethod
    def INPUT_TYPES(cls):
        return {'required': {'character': ('H3RC_CHARACTER',), 'compatibility_mode': (MODES, {'tooltip': 'Original RefMod preserves selected encodings for Apply RefMod. Video frames decodes a combined selection for the native H3 ref_video IMAGE input, which encodes it again.'})}, 'optional': {'vae': ('VAE', {'tooltip': 'Full H3 visual VAE. Required only for Video frames; Original RefMod does not use it.'})}}
    RETURN_TYPES = ('IMAGE', 'H3_REF_MODS')
    RETURN_NAMES = ('reference_frames', 'refmods')
    FUNCTION = 'adapt'
    CATEGORY = 'WorkflowX/Video/H3 Refmod'
    DESCRIPTION = 'Uses the connected character picker selections, profiles, order and video budget. No files are changed. Tags and retain/change prompt instructions are not compiled by this adapter.'

    def adapt(self, character, compatibility_mode='Original RefMod', vae=None):
        if not character:
            raise ValueError('Connect a character picker with a selected character.')
        if compatibility_mode not in MODES:
            raise ValueError('Choose a supported compatibility mode.')
        _, rows = build_plan('', characters={'character_0': character})
        visuals = [r for r in rows if not r['is_voice']]
        if compatibility_mode == 'Video frames':
            if character.get('visual_references') not in ('Saved combined video', 'Build combined video from selected references'):
                raise ValueError('Video frames requires Saved combined video or Build combined video from selected references in the character picker.')
            if len(visuals) != 1 or visuals[0]['kind'] != 'video':
                raise ValueError('Select one combined video reference in the character picker.')
            from comfy.ldm.minimax.vae import MiniMaxH3VideoVAE
            if not isinstance(getattr(vae, 'first_stage_model', None), MiniMaxH3VideoVAE):
                raise ValueError('Video frames requires the full H3 visual VAE.')
            rows = visuals
        prepared = []
        for row in rows:
            if row.get('runtime_combined'):
                result = prepare_combined(row['runtime_combined'], row['owner'], None, False)
            else:
                result = prepare_saved(row['path'], row['is_voice'], row['owner'], None,
                                       row.get('shape'), row.get('indices'), present=False)
            prepared.append(result['block'])
        if not prepared:
            raise ValueError('The picker selection contains no references to adapt.')
        if compatibility_mode == 'Video frames':
            frames = vae.decode(prepared[0]['latent'])
            if frames.ndim == 5 and frames.shape[0] == 1:
                frames = frames[0]
            if frames.ndim != 4 or frames.shape[-1] != 3:
                raise ValueError('H3 VAE returned an unsupported frame shape.')
            if len(frames) < 5:
                raise ValueError('This selection decodes to fewer than five frames. Native H3 ref_video requires at least five; use Original RefMod instead. Frames were not repeated.')
            return frames, ExecutionBlocker(None)
        mods = []
        for i, block in enumerate(prepared):
            audio = block['kind'] == 'audio'
            z = block['audio_latent'] if audio else block['latent']
            mod = H3RefMod(name=f"{character['alias']} {i+1}", kind=block['kind'], latent=z.clone(),
                           latent_t=z.shape[-1] if audio else z.shape[2],
                           latent_h=0 if audio else z.shape[3], latent_w=0 if audio else z.shape[4],
                           mode='encode', sample_rate=32000)
            mods.append((mod, 1.0))
        return ExecutionBlocker(None), mods
