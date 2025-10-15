import sys
from pathlib import Path

import numpy as np
import torch

# Import from shared dft_functionals at project root
root_path = Path(__file__).parent.parent
sys.path.insert(0, str(root_path))
from DFT import PBE, SVWN3

F_PBE = PBE.F_PBE
F_XALPHA = SVWN3.F_XALPHA
f_svwn3 = SVWN3.f_svwn3


def get_local_energies(reaction, constants, device, rung="GGA", dft="PBE", enhancement=None):
    calc_reaction_data = {}
    densities = reaction["Densities"].to(device)
    if rung == "LDA":
        if dft == "SVWN3":
            local_energies = f_svwn3(densities, constants)
        if dft == "XALPHA":
            local_energies = F_XALPHA(densities, constants)
    elif rung == "GGA":
        gradients = (reaction["Gradients"]).to(device)
        if dft == "PBE":
            local_energies = F_PBE(densities, gradients, constants, device, enhancement=enhancement)

    calc_reaction_data["Local_energies"] = local_energies
    calc_reaction_data["Densities"] = densities
    calc_reaction_data["Weights"] = reaction["Weights"].to(device)
    del local_energies, densities
    return calc_reaction_data


def backsplit(reaction, calc_reaction_data):
    backsplit_ind = reaction["backsplit_ind"].type(torch.int)
    splitted_data = dict()
    stop = 0

    for i, component in enumerate(np.frombuffer(reaction["Components"], dtype="<U20")):
        splitted_data[component] = dict()
        start = stop
        stop = backsplit_ind[i]
        for elem in ("Local_energies", "Weights", "Densities"):
            splitted_data[component][elem] = calc_reaction_data[elem][start:stop]
    del backsplit_ind, start, stop
    return splitted_data


def integration(reaction, splitted_calc_reaction_data, dispersions=dict()):
    molecule_energies = dict()
    for i, component in enumerate(np.frombuffer(reaction["Components"], dtype="<U20")):
        molecule_energies[component + str(i)] = (
            torch.sum(
                splitted_calc_reaction_data[component]["Local_energies"]
                * (
                    splitted_calc_reaction_data[component]["Densities"][:, 0]
                    + splitted_calc_reaction_data[component]["Densities"][:, 1]
                )
                * (splitted_calc_reaction_data[component]["Weights"])
            )
            + reaction["HF_energies"][i]
        )
        if dispersions:
            molecule_energies[component + str(i)] += torch.Tensor(
                dispersions.get(component, 0)
            )
    del splitted_calc_reaction_data
    return molecule_energies


def get_energy_reaction(reaction, molecule_energies):
    slices = reaction.get("reaction_indices", [0, len(reaction["Components"])])
    hartree2kcal = 627.5095
    reaction_energy_kcal = []
    for i in range(len(slices) - 1):
        s = 0
        for coef, ener in list(
            zip(reaction["Coefficients"], molecule_energies.values())
        )[slices[i] : slices[i + 1]]:
            s += coef * ener
        reaction_energy_kcal.append(s * hartree2kcal)
    del ener, coef, s, slices

    return torch.stack(reaction_energy_kcal)


def calculate_reaction_energy(
    reaction, constants, device, rung, dft, dispersions=dict(), enhancement=None
):
    local_energies = get_local_energies(reaction, constants, device, rung, dft, enhancement=enhancement)
    if local_energies["Local_energies"].isnan().any():
        print(local_energies["Local_energies"].isnan().sum())
        torch.save(local_energies["Local_energies"], "local_energies.pt")
        raise Exception()
    splitted_calc_reaction_data = backsplit(reaction, local_energies)
    molecule_energies = integration(reaction, splitted_calc_reaction_data, dispersions)
    reaction_energy_kcal = get_energy_reaction(reaction, molecule_energies)
    del molecule_energies, splitted_calc_reaction_data
    return reaction_energy_kcal, local_energies["Local_energies"]


def test_energy_PBE(test_grid, constants):
    local_energies = F_PBE(test_grid["Densities"], test_grid["Gradients"], constants)
    local_scaled_energies = (
        local_energies
        * (test_grid["Densities"][:, 0] + test_grid["Densities"][:, 1])
        * (test_grid["Weights"])
    )
    return local_energies, local_scaled_energies
