# Neural Film Grain Rendering — Lesné, Gousseau, Ladjal, Newson.
# https://github.com/Gwilherm-LESNE/Neural_Film_Grain_Rendering
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#%%
import torch
import torch.nn as nn

#%%
 
class ResidualBlock(nn.Module):
    def __init__(self, channel, k_size = (3,3)):
        super().__init__()
        self.block = nn.Sequential(nn.Conv2d(channel,channel,kernel_size = k_size, stride=1, padding='same', padding_mode='reflect'),
                                   nn.LeakyReLU(),
                                   nn.InstanceNorm2d(channel),
                                   nn.Conv2d(channel,channel,kernel_size = k_size, stride=1, padding='same', padding_mode='reflect'),
                                   )
        self.relu_out = nn.LeakyReLU()
    def forward(self,x):
        return self.relu_out(self.block(x) + x)
    
class MyNorm(nn.Module):
    """
    Custom Adaptive Instance Normalization layer
    """
    def __init__(self, channel_size, insize = 1):
        super().__init__()
        self.insize = insize
        self.channel_size = channel_size
        self.std_weight = nn.Linear(insize, self.channel_size)
        self.mean_weight = nn.Linear(insize, self.channel_size)

    def forward(self, x, grain_type):
        
        std = self.std_weight(grain_type)
        mean = self.mean_weight(grain_type)
        
        x = x * std.view(*std.shape,1,1).repeat(1,1,*x.shape[-2:])
        x = x + mean.view(*mean.shape,1,1).repeat(1,1,*x.shape[-2:])        
        return x
        
class GrainNet(nn.Module):
    def __init__(self, activation = 'tanh', block_nb = 2):
        """
        Network which adds grain to a given image.

        Parameters
        ----------
        activation : bool, optional
            Tells if we put a sigmoid at the end of the network. The default is True.

        Returns
        -------
        None.

        """
        super(GrainNet, self).__init__()

        if not block_nb in [1,2,3]:
            raise ValueError('block_nb must be 1,2 or 3')
        self.block_nb = block_nb
        
        self.entry_conv = nn.Sequential(nn.Conv2d(2,16,kernel_size = (3,3), stride=1, padding='same', padding_mode='reflect'),
                                    nn.LeakyReLU())
        
        self.block1 = nn.Sequential(ResidualBlock(16),
                                    nn.InstanceNorm2d(16))
        self.mn1 = MyNorm(16)
        
        if self.block_nb == 3:

            self.augment = nn.Sequential(nn.Conv2d(16,32,kernel_size = (3,3), stride=1, padding='same', padding_mode='reflect'),
                                        nn.LeakyReLU())
            
            self.block2 = nn.Sequential(ResidualBlock(32),
                                        nn.InstanceNorm2d(32))
            self.mn2 = MyNorm(32)
                                    
            self.reduce = nn.Sequential(nn.Conv2d(32,16,kernel_size = (3,3), stride=1, padding='same', padding_mode='reflect'),
                                        nn.LeakyReLU())
            
        if self.block_nb > 1:
                
            self.block3 = nn.Sequential(ResidualBlock(16),
                                        nn.InstanceNorm2d(16))
            self.mn3 = MyNorm(16)

        self.out_conv = nn.Sequential(nn.Conv2d(16,1,kernel_size = (3,3), stride=1, padding='same', padding_mode='reflect'))
                

        self.activation = activation
        self.tanh = nn.Tanh()
        self.sigmoid = nn.Sigmoid()       
    
    def forward(self, img, grain_radius, seed=None):
        if not (seed is None):
            torch.manual_seed(seed)
            
        noise = torch.randn(img.shape)
        noise = noise.to(device=img.device, dtype=img.dtype)
        
        x = torch.cat((noise,img), dim=1)
        
        x0 = self.entry_conv(x)
        
        x1 = self.block1(x0)
        x1 = self.mn1(x1, grain_radius)

        if self.block_nb == 3:
            x2 = self.augment(x1)
            
            x3 = self.block2(x2)
            x3 = self.mn2(x3, grain_radius)
            
            x4 = self.reduce(x3)

            x5 = self.block3(x4 + x1)
            x5 = self.mn3(x5, grain_radius)
            x6 = self.out_conv(x5 + x0)

        if self.block_nb == 2:          
            x5 = self.block3(x1)
            x5 = self.mn3(x5, grain_radius)
            x6 = self.out_conv(x5 + x0)
        
        if self.block_nb == 1:
            x6 = self.out_conv(x1)

        if self.activation == 'tanh':
            x6 = self.tanh(x6)
            x6 = torch.clamp((0.5*x6 + 0.5), 0, 1) #Normalise images
        elif self.activation == 'sigmoid':
            x6 = self.sigmoid(x6)        
        return x6
    
