from torch import nn
import torch


device = torch.device('cuda:0') if torch.cuda.is_available else torch.device('cpu')	
true_constants_PBE = torch.Tensor([[0.06672455,
                                    (1 - torch.log(torch.Tensor([2])))/(torch.pi**2),
                                    1.709921,
                                    7.5957, 14.1189, 10.357,
                                    3.5876, 6.1977, 3.6231,
                                    1.6382, 3.3662,  0.88026,
                                    0.49294, 0.62517, 0.49671,
                                    # 1,  1,  1,
                                    0.031091, 0.015545, 0.016887,
                                    0.21370,  0.20548,  0.11125,
                                    -3/8*(3/torch.pi)**(1/3)*4**(2/3),
                                    0.8040,
                                    0.2195149727645171]]).to(device)

"""
Define an nn.Module class for a simple residual block with equal dimensions
"""
class ResBlock(nn.Module):

    """
    Iniialize a residual block with two FC followed by (batchnorm + relu + dropout) layers 
    """
    def __init__(self, h_dim, dropout):
        super().__init__()
        self.fc = nn.Sequential(
            nn.Linear(h_dim, h_dim, bias=False),
            nn.BatchNorm1d(h_dim),
            nn.LeakyReLU(),
            nn.Dropout(p=dropout)) # default value was 0.2, trying 0.4 and 0.6
        
    def forward(self, x):
        residue = x

        return self.fc(self.fc(x)) + residue # skip connection 
#        return self.fc(self.fc(x))


class MLOptimizer(nn.Module):
    def __init__(self, num_layers, h_dim, nconstants, dropout, DFT=None):
        super().__init__()

        self.DFT = DFT
        
        modules = []
        modules.extend([nn.Linear(7, h_dim, bias=False),
                        nn.BatchNorm1d(h_dim),
                        nn.LeakyReLU(),
                        nn.Dropout(p=0.0)])
        
        for _ in range(num_layers // 2 - 1):
            modules.append(ResBlock(h_dim, dropout))
            
        modules.append(nn.Linear(h_dim, nconstants, bias=True))

        self.hidden_layers = nn.Sequential(*modules)
    
    def custom_sigmoid(self, x):
        # Custom sigmoid translates from [-inf, +inf] to [0, 4]
        # from 0 to 1
        result = (1+torch.e+(torch.e-3)/3)/(1 + (torch.e-3)/3 + torch.e**(-0.5*x+1))
        # result = torch.sigmoid(x) * 2
        return result

    def forward(self, x):
        x = self.hidden_layers(x)
        
        if self.DFT == 'SVWN': # constraint for VWN3's Q_vwn function to 4*c - b**2 > 0
            constants = []
            for b_ind, c_ind in zip((2, 3, 11, 12, 13),(4, 5, 14, 15, 16)):
                 constants.append(torch.abs(x[:, c_ind]) + (x[:, b_ind]**2)/4 + 1e-5) # torch.abs or nn.ReLU()?
            x = torch.cat([x[:,0:4], torch.stack(constants[0:2], dim=1), x[:,6:14], torch.stack(constants[2:], dim=1), x[:,17:]], dim=1)
            del constants
        if self.DFT == 'PBE':
            ''' Use sigmoid on predictions and multiply by known constants for easier predictions '''
            x = self.custom_sigmoid(x)
            # 4,5
            if x.shape[1]==2:
                x = torch.cat([torch.ones(x.shape[0], 4).to(device), x, torch.ones(x.shape[0],18).to(device)], dim=1)
            x = x * true_constants_PBE
        if self.DFT == 'XALPHA':
            x = x * 1.05
        return x


def NN_XALPHA_model(num_layers=32, h_dim=32, nconstants=1, dropout=0.4, DFT='XALPHA'):
    return MLOptimizer(num_layers, h_dim, nconstants, dropout, DFT)

def NN_PBE_model(num_layers=8, h_dim=32, nconstants=24, dropout=0.4,DFT='PBE'):
    return MLOptimizer(num_layers, h_dim, nconstants, dropout, DFT)