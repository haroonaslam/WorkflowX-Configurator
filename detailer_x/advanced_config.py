"""Independent image processors and portable editor metadata."""
ADVANCED = {
    'rgb': dict(enabled=False, R=0, G=0, B=0),
    'gamma': dict(enabled=False, gamma=1.0),
    'color_balance': dict(enabled=False, adjust_type='midtones', cyan_red=0.0, magenta_green=0.0, yellow_blue=0.0, preserve_luminosity=True),
    'temperature': dict(enabled=False, kelvin=6500),
    'lens': dict(enabled=False, lens_shape='circle', lens_edge='around', lens_curvy=1.0, lens_zoom=1.0, lens_aperture=.5, blur_intensity=2),
    'pixel_perturb': dict(enabled=False, magnitude=.008, seed=0, seed_mode='random'),
    'neural_grain': dict(enabled=False, grain_size=.10, strength=.20, seed=0, seed_mode='random'),
    'lut': dict(enabled=False, lut='internal:luts/BlueArchitecture.cube', color_space='linear', lut_strength=100),
    'camera': dict(enabled=False, initial_jpeg_quality=98, vignette_strength=.10, chroma_aberr_strength=1.0, bayer_demosaic=True, iso_noise_scale=1.0, sensor_read_noise=2.0, hot_pixel_prob=.000001, banding_strength=0.0, motion_blur_kernel=3, seed=0, seed_mode='random'),
    'compression': dict(enabled=False, cycles=4, min_quality=75, max_quality=95, seed=0, seed_mode='random'),
}
CHOICES = {'adjust_type':['shadows','midtones','highlights'], 'lens_shape':['circle','square','rectangle','corners'], 'lens_edge':['around','symmetric'], 'color_space':['linear','log']}
RANGES = {'R':(-255,255,1),'G':(-255,255,1),'B':(-255,255,1),'gamma':(.1,10,.01),
    'cyan_red':(-100,100,1),'magenta_green':(-100,100,1),'yellow_blue':(-100,100,1),
    'kelvin':(2000,12000,1),'lens_curvy':(0,15,.1),'lens_zoom':(0,15,.1),'lens_aperture':(0,10,.1),'blur_intensity':(2,100,2),
    'magnitude':(0,.05,.001),'grain_size':(.01,.8,.01),'strength':(0,2,.01),'lut_strength':(0,100,1),
    'initial_jpeg_quality':(85,100,1),'vignette_strength':(0,1,.01),'chroma_aberr_strength':(0,10,.1),
    'iso_noise_scale':(0,16,.1),'sensor_read_noise':(0,50,.1),'hot_pixel_prob':(0,.001,.0000001),
    'banding_strength':(0,1,.001),'motion_blur_kernel':(1,51,1),'cycles':(1,10,1),'min_quality':(1,100,1),'max_quality':(1,100,1)}
