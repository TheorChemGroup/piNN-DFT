#delete this in the future


import numpy as np
import torch
import random

from torch import nn

from reaction_energy_calculation import calculate_reaction_energy, get_local_energies
from prepare_data import load_chk
from predopt import true_constants_PBE


rung = 'LDA'
dft = 'XALPHA'

def set_random_seed(seed):
    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark = False
    torch.manual_seed(seed)
    torch.cuda.manual_seed(seed)
    np.random.seed(seed)
    random.seed(seed)

def exc_loss(reaction, pred_constants, dft="PBE", true_constants=true_constants_PBE):
    HARTREE2KCAL = 627.5095
    backsplit_ind = reaction["backsplit_ind"].to(torch.int32)
    indices = list(zip(torch.hstack((torch.tensor(0).to(torch.int32), backsplit_ind)), backsplit_ind))
    n_molecules = len(indices)
    loss = torch.tensor(0., requires_grad=True).to(device)
    predicted_local_energies = get_local_energies(reaction, pred_constants, device, rung=rung, dft=dft)[
        "Local_energies"]
    predicted_local_energies = [predicted_local_energies[start:stop] for start, stop in indices]
    true_local_energies = get_local_energies(reaction, true_constants.to(device), device, rung='GGA', dft='PBE')[
        "Local_energies"]
    true_local_energies = [true_local_energies[start:stop] for start, stop in indices]
    for i in range(n_molecules):
        loss += 1 / len(predicted_local_energies[i]) \
                *torch.sqrt(
                    torch.sum(
                        (predicted_local_energies[i] - true_local_energies[i]) ** 2
                    )
                )

    return loss*HARTREE2KCAL/n_molecules


set_random_seed(41)

data, data_train, data_test = load_chk(path='checkpoints')


from dataset import collate_fn


class Dataset(torch.utils.data.Dataset):
    def __init__(self, data):

        self.data = data
        
    def __getitem__(self, i):
        self.data[i].pop('Database', None)
        return self.data[i], self.data[i]['Energy']
    
    def __len__(self):
        return len(self.data.keys())


train_set = Dataset(data=data_train)
train_dataloader = torch.utils.data.DataLoader(train_set, 
                                               batch_size=1,
                                               num_workers=4,
                                               pin_memory=True,
                                               shuffle=True, 
                                               collate_fn=collate_fn)


test_set = Dataset(data=data_test)
test_dataloader = torch.utils.data.DataLoader(test_set, 
                                              batch_size=1,
                                              num_workers=4,
                                              pin_memory=True,
                                              shuffle=True, 
                                              collate_fn=collate_fn)

device = torch.device('cuda:0') if torch.cuda.is_available else torch.device('cpu')

mae = nn.L1Loss()

lst = []
local_lst = []
names = {
    0:'Train',
    1:'Test',
}
with torch.no_grad():
    for index, dataset in enumerate([train_dataloader, test_dataloader]):
        lst = []
        local_lst = []
        for batch_idx, (X_batch, y_batch) in enumerate(dataset):
            grid_size = len(X_batch["Grid"])
            constants = (torch.ones(grid_size)*1.05).view(grid_size, 1).to(device)
            local_loss = exc_loss(X_batch, constants, dft='XALPHA')
            energies = calculate_reaction_energy(X_batch, constants, device, rung='LDA', dft='XALPHA', dispersions=dict())
            lst.append(mae(energies, y_batch.to(device)).item())
            local_lst.append(local_loss.item())
        print(f"XAlpha {names[index]} MAE =", np.mean(np.array(lst)))
        print(f'XAlpha {names[index]} Local Loss =', np.mean(np.array(local_lst)))

# Train MAE = 16.477465228355207
# Train Local Loss = 0.20307233538045438
# Test MAE = 17.320202976465225
# Test Local Loss = 0.17312359494658616

with torch.no_grad():
    for index, dataset in enumerate([train_dataloader, test_dataloader]):
        lst = []
        local_lst = []
        for batch_idx, (X_batch, y_batch) in enumerate(dataset):
            grid_size = len(X_batch["Grid"])
            constants = (torch.ones(grid_size*24)).view(grid_size, 24)*true_constants_PBE
            constants = constants.to(device)
            energies = calculate_reaction_energy(X_batch, constants, device, rung='GGA', dft='PBE', dispersions=dict())
            lst.append(mae(energies, y_batch.to(device)).item())
        print(f"PBE {names[index]} MAE =", np.mean(np.array(lst)))

# Train MAE = 16.477465228355207
# Train Local Loss = 0.20307233538045438
# Test MAE = 17.320202976465225
# Test Local Loss = 0.17312359494658616


