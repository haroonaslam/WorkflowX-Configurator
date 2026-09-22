export const HELP = {
  "sample_frames": "Maximum source frames from EACH video. Start with 16 evenly spaced frames. 0 includes all frames in the chosen range. More frames can preserve more views and movement but cost more; FPS is not changed and frames are not repeated.",
  "voice_duration_limit": "Optional time limit shared across all included audio recordings, in displayed order. Off by default. It selects seconds before encoding and is independent of the token budget.",
  "video_duration_limit": "Optional time limit shared across all included videos, in displayed order. Off by default. It selects seconds from each original recording regardless of FPS; frame sampling is a separate choice.",
  "maximum_total_voice_duration": "Maximum voice time across ALL recordings together. Start with 10 seconds of clear speech from the intended speaker. With a 10-second limit, a first clip using 6 seconds leaves 4 seconds for later clips. Later recordings may be shortened or omitted; the creation report lists what was used.",
  "maximum_total_video_duration": "Maximum video time across ALL clips together, before frame sampling. Start with 15 seconds. With a 15-second limit, a first clip using 10 seconds leaves 5 seconds for later clips. Reorder sources to choose which clips get used first.",
  "video_fps": "How many pictures originally represent one second of a connected sequence of images. Enter the original frame rate, such as 24 or 30. A wrong value changes how long that sequence is treated as lasting. This is only needed for image sequences; actual video files supply their own frame rate.",
  "fps": "The original frames per second of the connected image sequence. Enter 24 only if the sequence was made at 24 fps; use 30 for a 30-fps sequence. This controls timing, not the total number of sampled frames. Video files supply their own frame rate, so this field is hidden for them.",
  "source": "Choose where this node gets its picture or recording. Load file uses the file picker and ignores connected media. Connected input uses the cable and ignores the file picker. For video, choose Connected video for a video cable or Connected frames for a sequence of images.",
  "descriptor": "Describe what is in the reference so H3 knows what the tag means. Example: the living room with a grey sofa. Use ordinary descriptive words, not a filename. Keep instructions about what should stay or change in the Retain and Change boxes.",
  "tag": "The name you will type in the scene prompt, such as room or my_voice. Enter it without @, then use @room or @my_voice in the prompt. Choose a different tag for each reference. Capital letters do not make a tag different.",
  "role": "Choose what you want H3 to take from this source. This tells H3 its purpose; it does not edit the source file. Then use Retain and Change to be more specific.",
  "retain": "Describe what should stay the same as this reference. Use concrete details, such as the grey sofa and room layout. Leave blank to use the normal instructions for the selected purpose.",
  "change": "Describe what should be different, or what H3 should not copy. Example: replace the sofa with a blue one; do not copy the people. These instructions guide generation and do not modify your saved reference.",
  "preservation": "Use Custom to specify what stays or changes in Retain and Change. Leave both blank to use the selected reference role. Follow reference closely hides and ignores custom changes. Use as loose inspiration asks for a broad resemblance rather than a close copy. These choices guide H3; they do not change file size or guarantee an exact match.",
  "start_seconds": "Where to begin in the recording, measured from its start. 0 begins at the beginning; 5 skips the first five seconds. For voice references, start at clear speech rather than silence or background noise.",
  "duration_seconds": "How many seconds to use AFTER the start time. Example: Start 5 and Duration 3 uses seconds 5 through 8. Duration 0 uses everything from Start to the end. For a voice reference, a short clean segment is a good starting point.",
  "use_soundtrack": "Turn this on to include sound from the selected part of the video. Leave it off if you want only the pictures or movement. If you supply a sequence of images instead of a video file, also connect its audio to the audio input.",
  "audio_tag": "A separate prompt name for this video's sound, for example room_sound. You can then mention @room_sound. It must differ from the video tag and from other character or reference tags.",
  "audio_role": "Choose how the video's sound should be used: a character voice, background ambience, music, a sound effect, or a complete soundtrack. Character voice also needs an associated character. Choose ambience for sounds such as rain or crowd noise.",
  "audio_mode": "Start with Reference to use the sound as a guide for newly generated audio. Weak reference asks for only a broad resemblance and is less suitable for a close voice match. Partial reuse asks to copy a specific sound or interval; describe which one. Complete-track reuse asks to copy the whole soundtrack and cannot be combined with automatically managed new dialogue.",
  "audio_instructions": "Describe what to keep from this video's sound and what to leave out. For Partial reuse, name the sound or time interval, for example keep the rain from seconds 0 to 3 and remove the speech.",
  "associated_character": "Choose which connected character this reference belongs to. For a voice, this is the character who should speak with that voice. Leave unassigned for a room, scenery, music or general background sound. Turn off that character's saved voice before assigning an external voice.",
  "audio_character": "Choose who should speak with the voice from this video's sound. Leave unassigned for ambience or music. Turn off the selected character's saved voice if this recording is supplying their voice instead.",
  "use_saved_voice": "Use the voice recording saved with this character. Turn it off if you are connecting a separate voice recording for the same character. This control is unavailable when the character has no saved voice.",
  "batch_selection": "Choose which images to use when the connected cable contains several images. Leave all to use every image. Enter 1,3 to use only the first and third images, in that order. This option is not needed for a single loaded picture.",
  "display_name": "The name shown on the character card, for example Shumaila - red outfit. It can differ from the prompt tag. Give different versions recognizable names so they are easy to pick.",
  "prompt_alias": "The name you will type after @ in your scene prompt, for example shumaila. Enter it without @. Different saved versions may share a tag, but you cannot use conflicting characters with that same tag in one generation.",
  "package_name": "The folder and filenames to create on disk. Leave blank to use Display name. This is separate from the @tag, so you can save different character versions. If that folder already exists, a numbered folder is created instead of overwriting it.",
  "folder": "The folder containing the pictures, videos and voice recordings for this character. Use Edit source media to choose their order, exclude files and select recording ranges before creation.",
  "description": "Optional notes to help you recognize this character in the browser, such as how it was created or which version it is. These notes are not instructions for H3.",
  "character_path": "Choose a saved character using Browse characters. The selected card shows the name and @tag you can use in the scene prompt.",
  "source_ranges": "Use Edit source media to arrange and include sources and choose recording start/duration. Earlier sources use the total time allowance first. Image sources use the whole picture.",
  "budget_mode": "Automatic uses all connected reference information and has no imposed token limit. Start here unless you need to enforce a specific limit. Manual stops generation when references exceed your chosen limit; it does not automatically make them smaller.",
  "manual_reference_budget": "Maximum reference information allowed for this generation, measured in tokens. Compare it with the calculated total shown under Reference details. If the total is too high, increase this limit, remove a reference, or choose a smaller-reference option on the character picker. This does not reserve or guarantee GPU memory.",
  "width": "Output video width in pixels. Larger videos take more time and memory. Start with the example workflow's value; change width and height together to choose the picture proportions.",
  "height": "Output video height in pixels. Larger videos take more time and memory. Start with the example workflow's value; change width and height together to choose the picture proportions.",
  "length": "How many frames the generated video contains. At 24 frames per second, about 120 frames is five seconds. H3 accepts specific frame counts, so the final duration may differ slightly. Longer videos take more time and memory.",
  "ref_image_size": "How regular reference pictures are resized for generation. Match uses the output picture size. A larger setting can retain more detail but increases reference processing and memory use. This does not resize your original files or saved characters.",
  "prompt": "Write the scene, actions and dialogue here. Use the @tags displayed on connected references. Use @character: before that character's dialogue. Retain and Change belong on the reference nodes; this box describes the video you want to create.",
  "regenerate": "Off keeps an existing thumbnail and creates one only if missing. On replaces the thumbnail by making a new preview from the saved character. The character file itself is not changed.",
  "vae": "Connect the H3 picture/video VAE loader. This component reads and writes H3 visual references; use the H3 VAE from the example workflow.",
  "audio_vae": "Connect the H3 audio VAE loader when processing a new voice or soundtrack recording. It converts the recording into the format H3 uses. Use the H3 audio VAE from the example workflow.",
  "clip": "Connect the H3 text encoder from the example workflow. It processes the scene prompt together with the references."
};
export const LABELS = {
  "sample_frames": "Maximum source frames per video (0 = all)",
  "voice_duration_limit": "Limit total voice time",
  "video_duration_limit": "Limit total video time",
  "maximum_total_voice_duration": "Voice time across all clips (seconds)",
  "maximum_total_video_duration": "Video time across all clips (seconds)",
  "video_fps": "Original frame rate (fps)",
  "fps": "Original frame rate (fps)",
  "duration_seconds": "Seconds to use (0 = to the end)",
  "start_seconds": "Start at (seconds)",
  "budget_mode": "Budget mode",
  "manual_reference_budget": "Maximum reference information (tokens)",
  "length": "Output length (frames)",
  "ref_image_size": "Reference picture size",
  "retain": "Retain",
  "change": "Change"
};
export const OPTIONS = {
  "Unlimited": "No duration limit",
  "Limited": "Limit total time",
  "weak_reference": "Weak reference - broad resemblance",
  "Full": "Follow reference closely",
  "Custom": "Custom - choose what stays or changes",
  "Weak reference": "Use as loose inspiration"
};

export function helpFor(name,nodeType){
 if(name==='descriptor'&&nodeType==='H3RCCreateFromFolder')return "Describe the character, for example a South Asian woman. This becomes the character identity description in H3 prompts. Keep filenames and catalog notes out of this field.";
 const byNode={
  H3RCAudioReference:{
   retain:'Describe what should stay the same in the sound. For a voice: the same sounding speaker and accent. For ambience: the rain or crowd noise. For music: the instruments or mood. Leave blank to use the selected audio purpose.',
   change:'Describe what should sound different or should not be copied. For a voice: new dialogue, a happier delivery, or no background noise. For ambience: remove the speech but keep the rain. Write the actual spoken words in the main scene prompt.',
   role:'Choose Character voice to use this recording as a speaker voice, Ambience for background sounds, Music for music, Sound effect for an individual sound, or Complete soundtrack for the whole recording. Choosing a role tells H3 how to use the sound; it does not remove speech or separate music from the recording.'
  },
  H3RCVideoReference:{
   retain:'Describe what to keep from the video: the dance steps, walking movement, camera path, room layout or other visible details. Leave blank to use the selected purpose. These instructions concern the pictures; sound has its own controls under Video soundtrack.',
   change:'Describe what should be different from the reference video. Examples: use my selected character instead of the dancer; change the location to a beach; keep the camera still. Write the full scene and actions in the main prompt.',
   descriptor:'Describe what the video shows, for example a dancer turning slowly or a camera moving through a room. H3 uses this description when you mention the tag. Put what to keep or replace in Retain and Change.',
   role:'Choose Motion for body movement, Performance for how an action is performed, Camera for camera movement and framing, or Scene for the location shown. Then use Retain and Change to say what matters. Start with the single purpose you most want to copy.'
  },
  H3RCCharacterPicker:{
   retain:'Describe which parts of the character should stay the same, such as the face, hairstyle or outfit. Leave both Retain and Change blank to ask H3 to keep the character as shown. These instructions apply only to this generation.',
   change:'Describe changes to the character, such as a red jacket, loose hair, different makeup or a new expression. Leave blank if no changes are wanted. This does not edit the saved character; write scene actions and spoken words in the main prompt.',
   descriptor:'Describe who this reference shows, for example a South Asian woman with fair skin. This may be filled from the character details. H3 uses it to identify the character; put outfit and hairstyle changes in Change.'
  },
  H3RCImageReference:{role:'Choose Character appearance for the person shown, Wardrobe for clothing, Scene for a location, Prop for an object, or Style for the overall look. For a room reference, start with Scene, then use Retain and Change to name the details to keep or replace.'}
 };
 return byNode[nodeType]?.[name]||HELP[name];
}
